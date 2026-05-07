from rest_framework import serializers

from .models import CreatorRole, Task, TaskType


class _UserMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()

    def get_name(self, user):
        if user is None:
            return None
        full = user.get_full_name() if hasattr(user, "get_full_name") else None
        return full or getattr(user, "email", None)


class TaskSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "name",
            "description",
            "due_date",
            "status",
            "completed",
            "parent",
            "task_type",
            "group",
            "assigned_user",
            "created_by",
            "creator_role",
            "deleted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @staticmethod
    def get_created_by(obj) -> dict | None:
        if obj.created_by is None:
            return None
        return _UserMiniSerializer(obj.created_by).data


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "name",
            "description",
            "due_date",
            "status",
            "parent",
            "task_type",
            "group",
            "assigned_user",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        task_type = attrs.get("task_type")
        group = attrs.get("group")
        assigned_user = attrs.get("assigned_user")

        if task_type == TaskType.GROUP:
            if group is None:
                raise serializers.ValidationError({"group": "Required for group tasks."})
            if assigned_user is not None:
                raise serializers.ValidationError(
                    {"assigned_user": "Must be empty for group tasks."}
                )
            if group.deleted_at is not None:
                raise serializers.ValidationError({"group": "Group is deleted."})
        elif task_type == TaskType.INDIVIDUAL:
            if assigned_user is None:
                raise serializers.ValidationError(
                    {"assigned_user": "Required for individual tasks."}
                )
            if group is not None:
                raise serializers.ValidationError(
                    {"group": "Must be empty for individual tasks."}
                )
        else:
            raise serializers.ValidationError({"task_type": "Required."})

        parent = attrs.get("parent")
        if parent is not None and parent.deleted_at is not None:
            raise serializers.ValidationError({"parent": "Parent task is deleted."})

        return attrs


class TaskUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["name", "description", "due_date", "status", "parent"]


class TaskToggleSerializer(serializers.Serializer):
    completed = serializers.BooleanField(required=False)
