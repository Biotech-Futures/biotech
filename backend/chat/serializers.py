from __future__ import annotations

from rest_framework import serializers

from users.models import User

from .models import Message, MessageAttachment
from .permissions import user_can_moderate_group_chat


class AuthorSerializer(serializers.ModelSerializer):
    """
    Slim serializer returning only the details required by the client.
    """

    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name"]

    def get_name(self, obj: User) -> str:
        display_name = obj.get_full_name()
        return display_name if display_name else obj.email


class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = [
            "file_url",
            "filename",
            "file_size",
            "mime_type",
        ]


class MessageSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    attachments = serializers.SerializerMethodField()
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)
    text = serializers.SerializerMethodField()
    isDeleted = serializers.SerializerMethodField()
    deletedAt = serializers.DateTimeField(source="deleted_at", read_only=True)
    deletedBy = serializers.IntegerField(source="deleted_by_id", read_only=True)
    moderation = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "author",
            "text",
            "timestamp",
            "attachments",
            "isDeleted",
            "deletedAt",
            "deletedBy",
            "moderation",
        ]

    def get_text(self, obj: Message) -> str:
        if self._can_view_content(obj):
            return obj.text
        return "This message is no longer available."

    def get_attachments(self, obj: Message) -> list[dict]:
        if not self._can_view_content(obj):
            return []
        return MessageAttachmentSerializer(obj.attachments.all(), many=True).data

    def get_isDeleted(self, obj: Message) -> bool:
        return obj.is_deleted or obj.moderation_status == Message.ModerationStatus.REJECTED

    def get_moderation(self, obj: Message) -> dict | None:
        data = {
            "status": obj.moderation_status,
        }

        user = self._context_user
        include_sensitive = False
        if user is not None:
            if user_can_moderate_group_chat(user, obj.group) or obj.author_id == getattr(user, "id", None):
                include_sensitive = True

        if include_sensitive and obj.moderation_note:
            data["note"] = obj.moderation_note
        if obj.moderated_at:
            data["moderatedAt"] = obj.moderated_at
        if obj.moderated_by_id:
            data["moderatedBy"] = obj.moderated_by_id
        return data

    @property
    def _context_user(self):
        user = self.context.get("user")
        if user is not None:
            return user
        request = self.context.get("request")
        if request is not None:
            return getattr(request, "user", None)
        return None

    def _can_view_content(self, obj: Message) -> bool:
        if not obj.is_deleted and obj.moderation_status != Message.ModerationStatus.REJECTED:
            return True

        user = self._context_user
        if user is None:
            return not (obj.is_deleted or obj.moderation_status == Message.ModerationStatus.REJECTED)
        return user_can_moderate_group_chat(user, obj.group)
