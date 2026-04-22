from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Tasks, Milestone, TaskAssignees


# Inline shape for a single assignee, used as the schema hint for TaskSerializer.get_assignees.
# Declared before TaskSerializer so it can be referenced in the @extend_schema_field decorator.
class TaskAssigneeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='user.id')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    email = serializers.EmailField(source='user.email')

    class Meta:
        model = TaskAssignees
        fields = ['id', 'first_name', 'last_name', 'email']


class TaskSerializer(serializers.ModelSerializer):
    # `status` is now the single source of truth for completion.
    # `completed` has been removed — consumers should treat status == 'done' as complete.
    # `deleted_at` replaces `deleted_flag`; null means active, a timestamp means deleted.
    # `assignees` and `group` were added for the Dashboard Progress Snapshot (#1).
    assignees = serializers.SerializerMethodField()
    group = serializers.SerializerMethodField()

    @extend_schema_field(TaskAssigneeSerializer(many=True))
    def get_assignees(self, obj):
        # Filters out soft-deleted assignments (TaskAssignees still uses deleted_flag).
        # Relies on prefetch_related('assignments__user') in TaskListHTMLView.get_queryset()
        # to avoid N+1 queries.
        active_assignments = [a for a in obj.assignments.all() if not a.deleted_flag]
        return [
            {
                'id': a.user.id,
                'first_name': a.user.first_name,
                'last_name': a.user.last_name,
                'email': a.user.email,
            }
            for a in active_assignments
        ]

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_group(self, obj):
        # milestone is nullable on Tasks; accessing .group_id avoids an extra JOIN
        # because it reads the FK integer column directly (no group object needed).
        if obj.milestone_id and obj.milestone:
            return obj.milestone.group_id
        return None

    class Meta:
        model = Tasks
        fields = [
            "id", "task_name", "task_description", "due_date",
            "deleted_at", "status",
            "milestone", "group", "assignees",
        ]


class MilestoneSerializer(serializers.ModelSerializer):
    # deleted_at replaces deleted_flag. start_date, due_date, sort_order were added
    # for the Dashboard Progress Snapshot (#1).
    class Meta:
        model = Milestone
        fields = [
            "id", "group", "milestone_name", "completed", "deleted_at",
            "start_date", "due_date", "sort_order",
        ]


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tasks
        fields = ["task_name", "due_date", "milestone", "task_description"]


class DeleteTaskResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tasks
        fields = ["id", "task_name", "due_date", "deleted_at", "milestone", "task_description"]
