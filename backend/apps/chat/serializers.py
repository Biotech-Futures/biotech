# Phase 2 update: updated serializers to reflect new Messages model fields.
# Added is_deleted, is_edited as read-only fields.
# Added MessageUpdateSerializer for edit operations that sets edited_at automatically.
# Added MessageStatusSerializer for read/delivery tracking.

from rest_framework import serializers
from .models import Messages, MessageResource, MessageStatus
from apps.resources.models import Resources


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


class MessageSerializer(serializers.ModelSerializer):
    resources = MessageResourceSerializer(many=True, required=False)
    sender_name = serializers.CharField(
        source="sender_user.get_full_name", read_only=True
    )
    is_deleted = serializers.BooleanField(read_only=True)
    is_edited = serializers.BooleanField(read_only=True)

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
            "parent_id"
        ]
        read_only_fields = [
            "id", "group", "sender_user",
            "sent_at", "edited_at", "deleted_at",
        ]

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
        return attrs


class MessageUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Messages
        fields = ["message_text"]

    def update(self, instance, validated_data):
        from django.utils import timezone
        instance.message_text = validated_data.get("message_text", instance.message_text)
        instance.edited_at = timezone.now()
        instance.save(update_fields=["message_text", "edited_at"])
        return instance