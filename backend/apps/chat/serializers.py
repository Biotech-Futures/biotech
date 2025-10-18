from rest_framework import serializers
from .models import Messages, MessageAttachments, MessageResource
from apps.resources.models import Resources
from apps.chat.management.azure_storage import generate_sas_url

class MessageAttachmentSerializer(serializers.ModelSerializer):
    # signed_url is what FE uses to download (expires ~5 min)
    signed_url = serializers.SerializerMethodField()

    class Meta:
        model = MessageAttachments
        fields = ["id", "attachment_filename", "signed_url"]

    def get_signed_url(self, obj):
        return generate_sas_url(obj.attachment_url)

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
            "resources",
            "attachments",
        ]
        read_only_fields = ["id", "group", "sender_user", "sent_datetime"]

    def create(self, validated_data):
        resources_data = validated_data.pop("resources", [])
        message = Messages.objects.create(**validated_data)
        if resources_data:
            MessageResource.objects.bulk_create(
                [MessageResource(message=message, resource=r["resource"]) for r in resources_data]
            )
        return message

    def validate(self, attrs):
        message = attrs.get("message_text", "").strip()
        resources_data = self.initial_data.get("resources", [])
        if not message and not resources_data:
            raise serializers.ValidationError(
                "Message must include text, a resource, or at least one attachment."
            )
    