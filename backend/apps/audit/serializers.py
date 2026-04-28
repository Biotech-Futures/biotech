from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor_user.email", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor_user",
            "actor_email",
            "entity_type",
            "entity_id",
            "action",
            "before_state",
            "after_state",
            "created_at",
        ]
        read_only_fields = fields

