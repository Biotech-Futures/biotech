import uuid

from django.conf import settings
from django.db import models


class EmailCheckJob(models.Model):
    """One check of a registration's addresses before it's submitted
    (apps.users.email_precheck), for the page to show its progress.

    Holds counts only, never the addresses: those stay with the worker
    checking them, and each answer is kept as an EmailVerification. A job the
    worker stops updating (a restart, say) is reported as stalled, and the
    page submits without waiting. Jobs are deleted a day after they start."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    # Every address in the registration, each once.
    total = models.PositiveIntegerField(default=0)
    # Addresses accounted for: answered already, checked now, or skipped.
    done = models.PositiveIntegerField(default=0)
    # Answered already (a recent answer on file), so not looked up again.
    cached = models.PositiveIntegerField(default=0)
    # Left unchecked: over the hourly lookup budget.
    skipped = models.PositiveIntegerField(default=0)
    invalid = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    # Lookups made and the seconds they took, for the time-remaining estimate.
    lookups = models.PositiveIntegerField(default=0)
    lookup_seconds = models.FloatField(default=0)
    # A short hash of who started it (their IP), never the IP itself.
    client_tag = models.CharField(max_length=16, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # Moved on whenever the worker makes progress: a job that stops moving has stalled.
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_check_job"
        verbose_name = "Email Check Job"
        verbose_name_plural = "Email Check Jobs"

    def __str__(self):
        return f"{self.pk}: {self.status} {self.done}/{self.total}"
