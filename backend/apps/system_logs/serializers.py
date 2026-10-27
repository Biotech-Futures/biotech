from rest_framework import serializers

from .models import SystemLogEntry

# How much of a message the list shows; the detail has all of it.
MESSAGE_PREVIEW_CHARS = 300


def _user_payload(user):
    if user is None:
        return None
    return {"id": user.id, "email": user.email, "name": user.get_full_name()}


class SystemLogListSerializer(serializers.ModelSerializer):
    """A row of the System Logs table. Reads the ``message_preview``,
    ``message_truncated`` and ``has_traceback`` annotations from
    ``views.SystemLogListView``, so long text never leaves the database."""

    message = serializers.CharField(source="message_preview")
    message_truncated = serializers.BooleanField()
    has_traceback = serializers.BooleanField()
    user = serializers.SerializerMethodField()

    class Meta:
        model = SystemLogEntry
        fields = [
            "id", "created_at", "level", "level_name", "logger_name", "message", "message_truncated",
            "has_traceback", "request_id", "request_method", "request_path", "status_code", "user",
        ]

    def get_user(self, entry):
        return _user_payload(entry.user)


class SystemLogDetailSerializer(serializers.ModelSerializer):
    """One row in full, for an expanded row."""

    user = serializers.SerializerMethodField()

    class Meta:
        model = SystemLogEntry
        fields = [
            "id", "created_at", "level", "level_name", "logger_name", "message", "traceback",
            "request_id", "request_method", "request_path", "status_code", "user",
            "module", "func_name", "line_no", "extra",
        ]

    def get_user(self, entry):
        return _user_payload(entry.user)
