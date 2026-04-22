from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Tasks, Milestone, TaskAssignees


class TaskAssigneeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='user.id')
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    email = serializers.EmailField(source='user.email')

    class Meta:
        model = TaskAssignees
        fields = ['id', 'first_name', 'last_name', 'email']


class TaskSerializer(serializers.ModelSerializer):
    assignees = serializers.SerializerMethodField()
    group = serializers.SerializerMethodField()

    @extend_schema_field(TaskAssigneeSerializer(many=True))
    def get_assignees(self, obj):
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
        if obj.milestone_id and obj.milestone:
            return obj.milestone.group_id
        return None

    class Meta:
        model = Tasks
        fields = [
            "id", "task_name", "task_description", "due_date",
            "deleted_flag", "completed", "status",
            "milestone", "group", "assignees",
        ]


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = [
            "id", "group", "milestone_name", "completed", "deleted_flag",
            "start_date", "due_date", "sort_order",
        ]


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tasks
        fields = ["task_name", "due_date", "milestone", "task_description"]


class DeleteTaskResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tasks
        fields = ["id", "task_name", "due_date", "deleted_flag", "milestone", "task_description"]
