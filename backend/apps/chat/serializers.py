# Phase 2 update: updated serializers to reflect new Messages model fields.
# Added is_deleted, is_edited as read-only fields.
# Added MessageUpdateSerializer for edit operations that sets edited_at automatically.
# Added MessageStatusSerializer for read/delivery tracking.

from django.conf import settings
from rest_framework import serializers
from rest_framework.reverse import reverse

from apps.resources.models import Resources

from .models import (
    MessageAttachment,
    MessageResource,
    MessageStatus,
    Messages,
    MessageType,
)
from .services.storage import save_uploaded_chat_file
from .utils import sanitize_text


class MessageResourceSerializer(serializers.ModelSerializer):
    resource_id = serializers.PrimaryKeyRelatedField(
        queryset=Resources.objects.all(),
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


class MessageAttachmentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = MessageAttachment
        fields = [
            "id",
            "attachment_filename",
            "attachment_mime_type",
            "attachment_size",
            "download_url",
        ]
        read_only_fields = fields

    def get_download_url(self, obj):
        request = self.context.get("request")
        path = reverse(
            "group-messages-attachment-download",
            kwargs={
                "group_pk": obj.message.group_id,
                "pk": obj.message_id,
                "attachment_pk": obj.id,
            },
            request=request,
        )
        # List/detail serializers can build absolute URLs when DRF has a request, but
        # tests and non-request code paths still need a stable fallback.
        if request is not None or not getattr(settings, "BACKEND_URL", ""):
            return path
        return f"{settings.BACKEND_URL.rstrip('/')}{path}"


class MessageSerializer(serializers.ModelSerializer):
    resources = MessageResourceSerializer(many=True, required=False)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    sender_name = serializers.CharField(
        source="sender_user.get_full_name", read_only=True
    )
    # These aliases preserve compatibility with both the older frontend message shape and the
    # newer conversation-oriented socket payload shape.
    sender_id = serializers.IntegerField(source="sender_user_id", read_only=True)
    conversation_id = serializers.IntegerField(source="group_id", read_only=True)
    created_at = serializers.DateTimeField(source="sent_at", read_only=True)
    body = serializers.CharField(source="message_text", read_only=True)
    text = serializers.CharField(source="message_text", read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    resource_ids = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    read_by = serializers.SerializerMethodField()

    class Meta:
        model = Messages
        fields = [
            "id",
            "group",
            "conversation_id",
            "sender_user",
            "sender_id",
            "sender_name",
            "message_text",
            "text",
            "body",
            "message_type",
            "sent_at",
            "created_at",
            "edited_at",
            "deleted_at",
            "is_deleted",
            "is_edited",
            "attachments",
            "resources",
            "resource_ids",
            "reactions",
            "read_by",
        ]
        read_only_fields = [
            "id", "group", "sender_user",
            "sent_at", "edited_at", "deleted_at",
        ]

    def get_resource_ids(self, obj):
        return [link.resource_id for link in obj.resources.all()]

    def get_reactions(self, obj):
        # Keep reactions as a simple emoji->count map so clients do not need to understand the
        # underlying row model when rendering chips or reconciling websocket updates.
        reactions = {}
        for reaction in obj.reactions.all():
            reactions[reaction.emoji_string] = reactions.get(reaction.emoji_string, 0) + 1
        return reactions

    def get_read_by(self, obj):
        return sorted(
            status.user_id
            for status in obj.statuses.all()
            if status.status == MessageStatus.StatusChoices.READ
        )

    def create(self, validated_data):
        resources_data = validated_data.pop("resources", [])
        message = Messages.objects.create(**validated_data)
        for r in resources_data:
            MessageResource.objects.create(
                message=message, resource=r["resource"]
            )
        return message

    def validate(self, attrs):
        msg = attrs.get("message_text", "").strip()
        resources_data = self.initial_data.get("resources", [])
        if not msg and not resources_data:
            raise serializers.ValidationError(
                "Message must include text or at least one resource."
            )
        # Sanitise BEFORE serializer.save() so the moderated text is what
        # gets persisted. Doing this here keeps the rule decoupled from
        # the view and ensures every write path goes through the same filter.
        if "message_text" in attrs:
            attrs["message_text"] = sanitize_text(attrs["message_text"])
        return attrs


class MessageAttachmentUploadSerializer(serializers.Serializer):
    message_text = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    uploaded_file = serializers.FileField(required=True)

    def validate_message_text(self, value):
        return sanitize_text((value or "").strip())

    def create(self, validated_data):
        uploaded_file = validated_data.pop("uploaded_file")
        attachment_data = save_uploaded_chat_file(uploaded_file)
        # Chat uploads persist the message row first so attachment downloads can stay
        # scoped to the same message permission checks as text messages.
        message = Messages.objects.create(
            **validated_data,
            message_type=MessageType.ATTACHMENT,
        )
        MessageAttachment.objects.create(message=message, **attachment_data)
        return message


class MessageReactionToggleSerializer(serializers.Serializer):
    emoji_string = serializers.CharField(max_length=64)

    def validate_emoji_string(self, value):
        # Reactions are sent one emoji at a time; normalization here keeps the toggle endpoint
        # tolerant of whitespace without letting empty values through.
        emoji = (value or "").strip()
        if not emoji:
            raise serializers.ValidationError("emoji_string is required.")
        return emoji


class MessageUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Messages
        fields = ["message_text"]

    def validate_message_text(self, value):
        return sanitize_text(value)

    def update(self, instance, validated_data):
        from django.utils import timezone
        instance.message_text = validated_data.get("message_text", instance.message_text)
        instance.edited_at = timezone.now()
        instance.save(update_fields=["message_text", "edited_at"])
        return instance
