from django.conf import settings
from django.db import models, transaction
from django.db.models import Count, Q
from django.utils import timezone


class TaskType(models.TextChoices):
    GROUP = "group", "Group"
    INDIVIDUAL = "individual", "Individual"


class TaskStatus(models.TextChoices):
    TODO = "todo", "To Do"
    IN_PROGRESS = "in_progress", "In Progress"
    DONE = "done", "Done"
    BLOCKED = "blocked", "Blocked"


class CreatorRole(models.TextChoices):
    GLOBAL_ADMIN = "global_admin", "Administrator"
    MENTOR = "mentor", "Mentor"
    SUPERVISOR = "supervisor", "Supervisor"
    STUDENT = "student", "Student"


class TaskQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def get_dashboard_tasks(self):
        return (
            self.active()
            .select_related("group", "assigned_user", "parent", "created_by")
        )

    def get_task_totals(self):
        return self.aggregate(
            total_tasks=Count("id"),
            completed_tasks=Count("id", filter=Q(completed=True)),
        )


class TaskManager(models.Manager.from_queryset(TaskQuerySet)):
    pass


class Task(models.Model):
    objects = TaskManager()

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=TaskStatus.choices, default=TaskStatus.TODO)
    completed = models.BooleanField(default=False)

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )

    task_type = models.CharField(max_length=20, choices=TaskType.choices)
    group = models.ForeignKey(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="group_tasks",
        null=True,
        blank=True,
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assigned_tasks",
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_tasks",
        null=True,
    )
    creator_role = models.CharField(max_length=20, choices=CreatorRole.choices)

    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "task"
        verbose_name = "Task"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["group", "deleted_at"]),
            models.Index(fields=["assigned_user", "deleted_at"]),
            models.Index(fields=["parent"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["creator_role"]),
            models.Index(fields=["task_type", "deleted_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(task_type="group") & Q(group__isnull=False) & Q(assigned_user__isnull=True))
                    | (Q(task_type="individual") & Q(assigned_user__isnull=False) & Q(group__isnull=True))
                ),
                name="task_type_target_consistency",
            ),
        ]

    def __str__(self):
        return f"Task<{self.task_type}>: {self.name}"

    @transaction.atomic
    def soft_delete(self):
        # Iterative BFS over children — recursion would risk hitting the
        # interpreter limit on deep task trees.
        now = timezone.now()
        ids_to_mark = [self.id]
        frontier = [self.id]
        while frontier:
            children = list(
                Task.objects.filter(parent_id__in=frontier, deleted_at__isnull=True)
                .values_list("id", flat=True)
            )
            if not children:
                break
            ids_to_mark.extend(children)
            frontier = children
        Task.objects.filter(id__in=ids_to_mark, deleted_at__isnull=True).update(deleted_at=now)
        self.deleted_at = now

    @transaction.atomic
    def restore(self, *, cascade=True):
        deleted_marker = self.deleted_at
        ids_to_restore = [self.id]

        if cascade and deleted_marker is not None:
            # Restore only children deleted by the same cascade, not independently deleted tasks.
            frontier = [self.id]
            while frontier:
                children = list(
                    Task.objects.filter(
                        parent_id__in=frontier,
                        deleted_at=deleted_marker,
                    ).values_list("id", flat=True)
                )
                if not children:
                    break
                ids_to_restore.extend(children)
                frontier = children

        Task.objects.filter(id__in=ids_to_restore).update(deleted_at=None)
        self.deleted_at = None
