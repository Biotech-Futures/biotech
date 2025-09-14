# TASKS MODELS
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import Q


class Milestone(models.Model):
    group = models.ForeignKey("groups.Groups", on_delete=models.CASCADE)
    milestone_name = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    deleted_flag = models.BooleanField(default=False)

    class Meta:
        db_table = 'milestone'
        verbose_name = "Milestone"
        indexes = [
            # regular indexes
            models.Index(fields=['group']),
            models.Index(fields=['completed']),
            models.Index(fields=['deleted_flag']),
        ]
        
    def __str__(self):
        return f"Milestone: {self.milestone_name} (Group: {self.group})"

class TaskAssignees(models.Model):
    task = models.ForeignKey('Tasks', on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_assignees")
    assigned_datetime = models.DateTimeField(default=timezone.now)
    deleted_flag = models.BooleanField(default=False)

    class Meta:
        db_table = 'task_assignees'
        verbose_name = "Task Assignees"
    
        indexes = [
                # regular indexes
                models.Index(fields=['task']),
                models.Index(fields=['user']),
                models.Index(fields=['assigned_datetime']),

                # index by task active status
                models.Index(
                    name='ta_active_by_task',
                    fields=['task'],
                    condition=Q(deleted_flag=False)
                ),

                # index by user active status
                models.Index(
                    name='ta_active_by_user',
                    fields=['user'],
                    condition=Q(deleted_flag=False)
                ),
            ]
    
        constraints = [
            models.UniqueConstraint(
                fields=(['task', 'user']),
                name="unique_task_user"
            )
        ]

    def __str__(self):
        return f"TaskAssignee: {self.user} assigned to {self.task} at {self.assigned_datetime}"

class Tasks(models.Model):
    task_name = models.CharField(max_length=255)
    due_date = models.DateTimeField()
    deleted_flag = models.BooleanField(default=False)
    # maybe a task can exist without being attached to a milestone? and if milestne deleted then set null
    milestone = models.ForeignKey('Milestone', null=True, blank=True, on_delete=models.SET_NULL)
    task_description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'tasks'
        verbose_name = "Tasks"
        ordering = ["-due_date"]
        indexes = [
            # index for maybe grouping by due date?
            models.Index(fields=['due_date']),
            # index for grouping by milestone
            models.Index(fields=['milestone'])
        ]
    def __str__(self):
        return f"Task: {self.task_name} (Due: {self.due_date})"
        
