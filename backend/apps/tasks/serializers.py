from rest_framework import serializers
from .models import Tasks, Milestone



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
