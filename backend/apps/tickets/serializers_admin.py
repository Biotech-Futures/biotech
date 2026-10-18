"""Input validation for the support side.

Physically separate from serializers.py, which serves the requester. The two
audiences have opposite rules — one must never see internal notes, the other
works in them — and a shared module is how a field ends up on the wrong side
of that line during a refactor.
"""

from rest_framework import serializers

from .bidi import BidiSafeCharField
from .models import TicketCategory, TicketMessageType, TicketPriority, TicketStatus
from .serializers import MAX_BODY_LENGTH
from .services.queue import support_capable_users

# What "not in support_capable_users()" means, said once for both fields that
# validate against it. DRF's default for a filtered queryset is 'Invalid pk
# "1" - object does not exist.', which is true of a deleted account and false
# of the case that actually happens: a real, present person who has no support
# access or whose account is switched off. An API caller that is not the admin
# app reads that message and goes looking for a missing row.
NOT_ASSIGNABLE = (
    'Cannot assign to user "{pk_value}". They need an active account with '
    'support queue access.'
)


class TicketPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TicketStatus.choices, required=False)
    priority = serializers.ChoiceField(choices=TicketPriority.choices, required=False)
    # Re-filing a ticket into the right category. The full list, not
    # PUBLIC_TICKET_CATEGORIES: an agent must be able to move a mis-screened
    # ticket out of "Flagged content", and must be able to put one back in.
    category = serializers.ChoiceField(choices=TicketCategory.choices, required=False)
    # Restricted to people who can actually work the queue: assigning a ticket
    # to someone who cannot open it is a ticket nobody is looking at.
    #
    # null is how a ticket goes back to the pool. Without it the owner control
    # was one-way: once a ticket had a name on it there was no way to say "this
    # is not mine after all", and the queue's own Unassigned count could only
    # ever go down.
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=support_capable_users(), required=False, allow_null=True,
        error_messages={"does_not_exist": NOT_ASSIGNABLE},
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Provide at least one of status, priority, category or assignee."
            )
        if "status" in attrs and "assignee" in attrs:
            # Each one runs a different lifecycle function, and whichever
            # order we picked would produce a wrong end state or silently
            # drop one of the two writes. The UI has these as separate
            # controls, so normal use never reaches this.
            raise serializers.ValidationError(
                "Change the status and the assignee in separate requests."
            )
        return attrs


class SupportMessageSerializer(serializers.Serializer):
    messageType = serializers.ChoiceField(
        choices=[TicketMessageType.SUPPORT_REPLY, TicketMessageType.INTERNAL_NOTE]
    )
    # BidiSafeCharField for the same reason the requester's fields use it: a
    # support reply is read by the student in the portal, an internal note is
    # read by the next agent, and neither should render in an order the stored
    # text does not have. See apps/tickets/bidi.py.
    body = BidiSafeCharField(max_length=MAX_BODY_LENGTH, allow_blank=False,
                             trim_whitespace=True)
    # "Reply and wait for their answer" as one action, so the email can say
    # which of the two it is. Optional, and the reply behaves exactly as
    # before when it is absent.
    moveToPending = serializers.BooleanField(required=False, default=False)
    # The status a reply leaves the ticket in, chosen beside the reply box
    # (C-19, the 8 October client meeting: "you put the status down here, and
    # it would default to pending user, but then it would allow the support
    # agent to change it to in progress or resolved"). Open is not offered:
    # an answered ticket is not new. Optional, so a caller that sends only
    # moveToPending, or nothing, behaves exactly as before; pending user is
    # the same action as moveToPending.
    nextStatus = serializers.ChoiceField(
        choices=[
            TicketStatus.IN_PROGRESS,
            TicketStatus.PENDING_USER,
            TicketStatus.RESOLVED,
        ],
        required=False,
    )

    def validate(self, attrs):
        is_note = attrs["messageType"] == TicketMessageType.INTERNAL_NOTE
        if attrs.get("moveToPending") and is_note:
            # An internal note is invisible to the requester, so moving the
            # ticket onto them would leave a status that says "your move"
            # with nothing on their timeline asking for anything.
            raise serializers.ValidationError(
                "An internal note cannot move the ticket to pending user."
            )
        if "nextStatus" in attrs and is_note:
            # The same reason, for every status: a change the requester can
            # see, made by a message they cannot.
            raise serializers.ValidationError(
                "An internal note cannot change the status."
            )
        if "nextStatus" in attrs and attrs.get("moveToPending"):
            # Two answers to one question. Picking one of them silently would
            # be guessing which the caller meant.
            raise serializers.ValidationError(
                "Send either nextStatus or moveToPending, not both."
            )
        return attrs


class ScreeningDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "delete"])


class BulkAssignSerializer(serializers.Serializer):
    ticketIds = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=200
    )
    # allow_null for the same reason the single-ticket PATCH above has it:
    # null is how a ticket goes back to the pool. Without it an agent who swept
    # twenty tickets onto themselves by mistake had to undo them one at a time,
    # even though bulk_assign hands the value straight to the same _assign_one
    # the PATCH uses and has always accepted None.
    assigneeId = serializers.PrimaryKeyRelatedField(
        queryset=support_capable_users(), allow_null=True,
        error_messages={"does_not_exist": NOT_ASSIGNABLE},
    )


class SupportScopeGrantSerializer(serializers.Serializer):
    userId = serializers.IntegerField()
