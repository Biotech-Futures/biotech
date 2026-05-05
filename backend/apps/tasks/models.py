from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import Q
from django.db.models import Count, Q


class TaskQuerySet(models.QuerySet):
    def get_dashboard_tasks(self):
        """Canonical dashboard-scoped Tasks queryset.

        Returns active (non-soft-deleted) tasks with their milestone /
        group joined via ``select_related`` and ``assignments``
        prefetched, so any consumer that iterates rows avoids N+1.
        Designed to be chained: callers add ``.filter(...)`` for group
        scoping and then call ``.get_task_totals()`` for aggregates,
        which keeps the query construction inside the data-access layer
        per SRP.
        """
        return (
            self.filter(deleted_at__isnull=True)
            .select_related("milestone", "milestone__group")
            .prefetch_related("assignments")
        )

    def get_task_totals(self):
        """Aggregate ``total_tasks`` / ``completed_tasks`` on the
        current queryset. Chainable off ``get_dashboard_tasks()`` or any
        other scoped queryset.
        """
        return self.aggregate(
            total_tasks=Count("id"),
            completed_tasks=Count("id", filter=Q(completed=True)),
        )


class TaskManager(models.Manager):
    def get_queryset(self):
        return TaskQuerySet(self.model, using=self._db)

    def get_dashboard_tasks(self):
        return self.get_queryset().get_dashboard_tasks()

    def get_task_totals(self):
        return self.get_queryset().get_task_totals()


class Milestone(models.Model):
    group = models.ForeignKey("groups.Groups", on_delete=models.CASCADE)
    milestone_name = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'milestone'
        verbose_name = "Milestone"
        indexes = [
            models.Index(fields=['group']),
            models.Index(fields=['completed']),
            models.Index(fields=['deleted_at']),
        ]

    def __str__(self):
        return f"Milestone: {self.milestone_name} (Group: {self.group})"


class TaskAssignees(models.Model):
    task = models.ForeignKey('Tasks', on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_assignees")
    assigned_datetime = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'task_assignees'
        verbose_name = "Task Assignees"

        indexes = [
            models.Index(fields=['task']),
            models.Index(fields=['user']),
            models.Index(fields=['assigned_datetime']),
            models.Index(
                name='ta_active_by_task',
                fields=['task'],
                condition=Q(deleted_at__isnull=True)
            ),
            models.Index(
                name='ta_active_by_user',
                fields=['user'],
                condition=Q(deleted_at__isnull=True)
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


class TaskStatus(models.TextChoices):
    TODO = "todo", "To Do"
    IN_PROGRESS = "in_progress", "In Progress"
    DONE = "done", "Done"
    BLOCKED = "blocked", "Blocked"


class Tasks(models.Model):
    objects = TaskManager()

    task_name = models.CharField(max_length=255)
    due_date = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    status = models.CharField(max_length=50, choices=TaskStatus.choices, default=TaskStatus.TODO)
    milestone = models.ForeignKey('Milestone', null=True, blank=True, on_delete=models.SET_NULL)
    task_description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'tasks'
        verbose_name = "Tasks"
        ordering = ["-due_date"]
        indexes = [
            models.Index(fields=['due_date']),
            models.Index(fields=['milestone']),
            models.Index(fields=['deleted_at']),
        ]

    def __str__(self):
        return f"Task: {self.task_name} (Due: {self.due_date})"
