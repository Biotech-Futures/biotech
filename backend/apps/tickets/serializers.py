from rest_framework import serializers

from .models import TicketCategory

# Spelled out rather than taken from TicketCategory.choices so that an
# internal category added later (for tickets the platform raises itself)
# cannot quietly turn up in the requester's dropdown.
PUBLIC_TICKET_CATEGORIES = (
    TicketCategory.ACCOUNT_ACCESS,
    TicketCategory.PROGRAMS_GROUPS,
    TicketCategory.CERTIFICATES_RECORDS,
)

# The cap the client asked for. It lives here rather than on the model: a
# TextField(max_length=...) would be written into the initial migration, so
# tuning the number later would cost a schema migration.
MAX_BODY_LENGTH = 2000


class TicketCreateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=PUBLIC_TICKET_CATEGORIES)
    subject = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    body = serializers.CharField(max_length=MAX_BODY_LENGTH, allow_blank=False, trim_whitespace=True)


class TicketReplySerializer(serializers.Serializer):
    body = serializers.CharField(max_length=MAX_BODY_LENGTH, allow_blank=False, trim_whitespace=True)
