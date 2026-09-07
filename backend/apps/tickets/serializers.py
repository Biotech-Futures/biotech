from rest_framework import serializers

from .models import TicketCategory, TicketPriority

# Spelled out rather than taken from TicketCategory.choices so that an
# internal category added later (for tickets the platform raises itself)
# cannot quietly turn up in the requester's dropdown.
#
# Order is the client's own, and the portal renders it in this order, so
# "Other" stays last where a person expects to find it.
PUBLIC_TICKET_CATEGORIES = (
    TicketCategory.ACCOUNT_ACCESS,
    TicketCategory.REGISTRATION,
    TicketCategory.HELP_STUDENT_GROUP,
    TicketCategory.HELP_MENTOR,
    TicketCategory.TECHNICAL_ISSUE,
    TicketCategory.CERTIFICATES_RECORDS,
    TicketCategory.GENERAL_QUESTION,
    TicketCategory.OTHER,
)

# The cap the client asked for. It lives here rather than on the model: a
# TextField(max_length=...) would be written into the initial migration, so
# tuning the number later would cost a schema migration.
MAX_BODY_LENGTH = 2000


class TicketCreateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=PUBLIC_TICKET_CATEGORIES)
    subject = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    body = serializers.CharField(max_length=MAX_BODY_LENGTH, allow_blank=False, trim_whitespace=True)
    # The requester's own answer to "how urgent is this?". The client settled
    # on 2026-09-04 that the person raising the enquiry sets it and a support
    # agent may change it afterwards.
    #
    # Optional, defaulting to Normal, for two reasons. A form posted without
    # the field keeps working, which is what an older client or a script does.
    # And "they did not say" and "they said Normal" deserve the same answer:
    # inventing a separate unset state would put a fourth value in front of
    # support with no meaning behind it.
    #
    # The full choice list, not a public subset: unlike category there is no
    # internal priority, so what a requester may pick is what exists.
    priority = serializers.ChoiceField(
        choices=TicketPriority.choices,
        required=False,
        default=TicketPriority.NORMAL,
    )


class TicketReplySerializer(serializers.Serializer):
    body = serializers.CharField(max_length=MAX_BODY_LENGTH, allow_blank=False, trim_whitespace=True)
