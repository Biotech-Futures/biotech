from rest_framework import serializers
from .models import Messages, MessageAttachments, MessageResource
from apps.resources.serializers import RoleSerializer  # optional reuse
from apps.resources.models import Resources


class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachments
        fields = ["id", "attachment_id", "attachment_filename"]


class MessageResourceSerializer(serializers.ModelSerializer):
    resource_id = serializers.PrimaryKeyRelatedField(
        queryset=Resources.objects.all(),
        source="resource",
        write_only=True,
    )
    resource_name = serializers.CharField(
        source="resource.resource_name", read_only=True
    )

    class Meta:
        model = MessageResource
        fields = ["id", "resource_id", "resource_name"]


class MessageSerializer(serializers.ModelSerializer):
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    resources = MessageResourceSerializer(many=True, required=False)
    sender_name = serializers.CharField(
        source="sender_user.get_full_name", read_only=True
    )

    class Meta:
        model = Messages
        fields = [
            "id",
            "group",
            "sender_user",
            "sender_name",
            "message_text",
            "sent_datetime",
            "attachments",
            "resources",
        ]
        read_only_fields = ["id", "sender_user", "sent_datetime"]

    def create(self, validated_data):
        resources_data = validated_data.pop("resources", [])
        message = Messages.objects.create(**validated_data)
        for r in resources_data:
            MessageResource.objects.create(
                message=message, resource=r["resource"]
            )
        return message
