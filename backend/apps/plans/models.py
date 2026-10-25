"""One shared plan definition, with completion recorded per group/person."""

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from apps.groups.models import GroupMembership


class PlanStageQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)


class PlanStage(models.Model):
    objects = PlanStageQuerySet.as_manager()

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plan_stage"
        ordering = ["position", "id"]
        indexes = [models.Index(fields=["deleted_at", "position"])]

    def __str__(self):
        return self.name


class PlanTaskQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True, stage__deleted_at__isnull=True)

    def in_plan_order(self):
        """Display order only; leave distinct/grouped reporting queries unordered."""
        return self.order_by("stage__position", "stage_id", "position", "id")


class PlanTask(models.Model):
    class CompletionMode(models.TextChoices):
        PER_PERSON = "per_person", "Each person"
        PER_GROUP = "per_group", "Whole group"

    objects = PlanTaskQuerySet.as_manager()

    stage = models.ForeignKey(PlanStage, on_delete=models.PROTECT, related_name="tasks")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    resource_url = models.URLField(max_length=2048, blank=True)
    resource_label = models.CharField(max_length=255, blank=True)
    due_date = models.DateField(null=True, blank=True)
    audience_role = models.CharField(
        max_length=50, choices=GroupMembership.MembershipRoleChoices.choices
    )
    completion_mode = models.CharField(
        max_length=20,
        choices=CompletionMode.choices,
        default=CompletionMode.PER_PERSON,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_plan_tasks",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plan_task"
        indexes = [models.Index(fields=["stage", "deleted_at", "position"])]

    def __str__(self):
        return self.name

    @transaction.atomic
    def soft_delete(self):
        # The future edit/toggle services use the same task-row lock.
        task = type(self).objects.select_for_update().get(pk=self.pk)
        if task.deleted_at is None:
            task.deleted_at = timezone.now()
            task.save(update_fields=["deleted_at", "updated_at"])
        self.deleted_at = task.deleted_at
        self.updated_at = task.updated_at


class PlanTaskCompletion(models.Model):
    task = models.ForeignKey(
        PlanTask, on_delete=models.CASCADE, related_name="completions"
    )
    group = models.ForeignKey(
        "groups.Groups", on_delete=models.CASCADE, related_name="plan_completions"
    )
    # Null is the one shared record, not an anonymous person's completion.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="plan_completions",
    )
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plan_task_completion"
        constraints = [
            models.UniqueConstraint(
                fields=["task", "group", "user"],
                condition=Q(user__isnull=False),
                name="unique_plan_person_completion",
            ),
            models.UniqueConstraint(
                fields=["task", "group"],
                condition=Q(user__isnull=True),
                name="unique_plan_group_completion",
            ),
        ]
        indexes = [models.Index(fields=["task", "group"])]

    def __str__(self):
        return f"Task {self.task_id}, group {self.group_id}, user {self.user_id}"
