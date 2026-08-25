"""Input validation for the support side.

Physically separate from serializers.py, which serves the requester. The two
audiences have opposite rules — one must never see internal notes, the other
works in them — and a shared module is how a field ends up on the wrong side
of that line during a refactor.
"""

from rest_framework import serializers

from .models import TicketMessageType, TicketPriority, TicketStatus
from .serializers import MAX_BODY_LENGTH
from .services.queue import support_capable_users


class TicketPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TicketStatus.choices, required=False)
    priority = serializers.ChoiceField(choices=TicketPriority.choices, required=False)
    # Restricted to people who can actually work the queue: assigning a ticket
    # to someone who cannot open it is a ticket nobody is looking at.
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=support_capable_users(), required=False
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Provide at least one of status, priority or assignee."
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
    body = serializers.CharField(max_length=MAX_BODY_LENGTH, allow_blank=False,
                                 trim_whitespace=True)


class BulkAssignSerializer(serializers.Serializer):
    ticketIds = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=200
    )
    assigneeId = serializers.PrimaryKeyRelatedField(queryset=support_capable_users())


class SupportScopeGrantSerializer(serializers.Serializer):
    userId = serializers.IntegerField()
