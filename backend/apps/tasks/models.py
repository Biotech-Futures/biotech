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
    # Added for Dashboard Progress Snapshot (#1):
    # start_date and due_date allow the API to report next_milestone.due_date and
    # to order milestones chronologically rather than by insertion order.
    # sort_order provides an explicit display/processing sequence when dates are absent.
    # All three are nullable so existing milestone rows are unaffected after migration.
    start_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'milestone'
        verbose_name = "Milestone"
        indexes = [
            models.Index(fields=['group']),
            models.Index(fields=['completed']),
            models.Index(fields=['deleted_flag']),
            models.Index(fields=['sort_order']),
            models.Index(fields=['due_date']),
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
    # Added for Dashboard Progress Snapshot (#1):
    # The frontend previously had no way to know whether a task was finished
    # because neither a boolean flag nor a status field existed on this model.
    # `completed` is the fast boolean used for COUNT queries in the progress endpoint.
    # `status` is the richer three-state value exposed in the task list response.
    # The two fields are kept in sync by TaskRetrieveUpdateView.patch().
    class Status(models.TextChoices):
        TODO = 'todo', 'To Do'
        IN_PROGRESS = 'in_progress', 'In Progress'
        DONE = 'done', 'Done'

    task_name = models.CharField(max_length=255)
    due_date = models.DateTimeField()
    deleted_flag = models.BooleanField(default=False)
    milestone = models.ForeignKey('Milestone', null=True, blank=True, on_delete=models.SET_NULL)
    task_description = models.CharField(max_length=255, blank=True, null=True)
    completed = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
    )

    class Meta:
        db_table = 'tasks'
        verbose_name = "Tasks"
        ordering = ["-due_date"]
        indexes = [
            models.Index(fields=['due_date']),
            models.Index(fields=['milestone']),
            models.Index(fields=['completed']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Task: {self.task_name} (Due: {self.due_date})"
