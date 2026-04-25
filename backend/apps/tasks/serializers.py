from rest_framework import serializers
from .models import Tasks, Milestone


class ProgressQuerySerializer(serializers.Serializer):
    group_id = serializers.IntegerField(required=False, allow_null=True)


class ProgressSnapshotSerializer(serializers.Serializer):
    completionRate = serializers.IntegerField()
    completedTasks = serializers.IntegerField()
    totalTasks = serializers.IntegerField()
    currentWeek = serializers.CharField(allow_null=True)
    nextMilestone = serializers.CharField(allow_null=True)
    nextMilestoneDate = serializers.DateTimeField(allow_null=True)


class MilestoneProgressSerializer(serializers.Serializer):
    milestone_id = serializers.IntegerField(source="milestone__id")
    milestone_name = serializers.CharField(source="milestone__milestone_name")
    group_id = serializers.IntegerField(source="milestone__group__id")
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tasks
        fields = ["id", "task_name", "due_date", "deleted_at", "milestone", "task_description"]

class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ["id", "group", "milestone_name", "completed", "deleted_at"]


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tasks
        fields = ["task_name", "due_date", "milestone", "task_description"]


class DeleteTaskResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tasks
        fields = ["id", "task_name", "due_date", "deleted_at", "milestone", "task_description"]
