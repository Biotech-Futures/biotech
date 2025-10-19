from rest_framework import serializers
from .models import Tasks, Milestone

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tasks
        fields = ["id", "task_name", "due_date", "deleted_flag", "milestone", "task_description"]

class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ["id", "group", "milestone_name", "completed", "deleted_flag"]

class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tasks
        fields = ["task_name", "due_date", "milestone", "task_description"]