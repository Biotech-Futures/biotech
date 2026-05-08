# Serializers for chat write paths.
#
# - MessageResourceSerializer / MessageStatusSerializer: nested DTOs.
# - MessageSerializer: read shape + create (POST /chat/groups/<gid>/messages/).
#   Sender, group, message lifecycle fields, and message_type are all
#   read-only — they're set server-side or are not user-editable.
# - MessageUpdateSerializer: edit shape (PATCH /chat/messages/<id>/).
#   Only message_text is mutable. Empty edits are rejected.

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.resources.models import Resources

from .models import Messages, MessageResource, MessageStatus
from .utils import sanitize_text


# Maximum allowed length for any message body. Messages.message_text is a
# TextField (unbounded at the DB layer); without this cap a single client
# could push arbitrarily large payloads through the chat pipe.
MESSAGE_TEXT_MAX_LENGTH = 4000


class MessageResourceSerializer(serializers.ModelSerializer):
    resource_id = serializers.PrimaryKeyRelatedField(
        # Don't surface soft-deleted rows for attachment.
        queryset=Resources.objects.filter(deleted_at__isnull=True),
        source="resource",
        write_only=True,
    )
    resource_name = serializers.CharField(
        source="resource.name", read_only=True
    )

    class Meta:
        model = MessageResource
        fields = ["id", "resource_id", "resource_name"]


class MessageStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageStatus
        fields = ["id", "user", "status", "delivered_at", "read_at"]
        read_only_fields = ["id", "delivered_at", "read_at"]


class MessageSerializer(serializers.ModelSerializer):
    resources = MessageResourceSerializer(many=True, required=False)
    sender_name = serializers.CharField(
        source="sender_user.get_full_name", read_only=True
    )
    is_deleted = serializers.BooleanField(read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    message_text = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=MESSAGE_TEXT_MAX_LENGTH,
        # Trim leading/trailing whitespace so an "all-spaces" body is treated
        # as empty by the resource-or-text validation below.
        trim_whitespace=True,
    )

    class Meta:
        model = Messages
        fields = [
            "id",
            "group",
            "sender_user",
            "sender_name",
            "message_text",
            "message_type",
            "sent_at",
            "edited_at",
            "deleted_at",
            "is_deleted",
            "is_edited",
            "resources",
        ]
        read_only_fields = [
            "id",
            "group",
            "sender_user",
            # message_type is server-controlled (e.g. "system" messages must
            # not be writable through the public API). Defaults to "text".
            "message_type",
            "sent_at",
            "edited_at",
            "deleted_at",
        ]

    def validate(self, attrs):
        # Use ``attrs`` (post-`to_internal_value`) rather than ``self.initial_data``
        # so the validation sees the cleaned representation.
        text = (attrs.get("message_text") or "").strip()
        resources = attrs.get("resources", [])
        if not text and not resources:
            raise serializers.ValidationError(
                "Message must include text or at least one resource."
            )
        if "message_text" in attrs:
            attrs["message_text"] = sanitize_text(attrs["message_text"])
        return attrs

    def create(self, validated_data):
        resources_data = validated_data.pop("resources", [])
        # Atomic: a half-created message with a partial resource set is
        # worse than a clean failure.
        with transaction.atomic():
            message = Messages.objects.create(**validated_data)
            MessageResource.objects.bulk_create(
                [
                    MessageResource(message=message, resource=r["resource"])
                    for r in resources_data
                ]
            )
        return message


class MessageUpdateSerializer(serializers.ModelSerializer):
    """
    Body for PATCH /chat/messages/<id>/. Authorization is enforced by
    ``apps.chat.management.permissions.CanEditMessage`` on
    ``MessageDetailView`` (sender-only, within ``SELF_ACTION_WINDOW``).
    This serializer only validates and persists ``message_text`` + ``edited_at``.
    """

    message_text = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=MESSAGE_TEXT_MAX_LENGTH,
        trim_whitespace=True,
    )

    class Meta:
        model = Messages
        fields = ["message_text"]

    def validate_message_text(self, value):
        # ``allow_blank=False`` + ``trim_whitespace=True`` already rejects an
        # empty / whitespace-only edit; sanitise the surviving text here.
        return sanitize_text(value)

    def update(self, instance, validated_data):
        instance.message_text = validated_data.get(
            "message_text", instance.message_text
        )
        instance.edited_at = timezone.now()
        instance.save(update_fields=["message_text", "edited_at"])
        return instance