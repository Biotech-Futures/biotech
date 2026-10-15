from django.conf import settings
from django.db import models


class SystemLogEntry(models.Model):
    """One log record the platform wrote, kept so admins can read it on the
    System Logs page instead of in Azure.

    Rows are written by ``apps.system_logs.handler.DatabaseLogHandler`` (already
    redacted) and removed after ``SYSTEM_LOG_RETENTION_DAYS`` by
    ``apps.system_logs.services.prune``.
    """

    created_at = models.DateTimeField()
    # The numeric level (30 = WARNING), so "WARNING and above" is a range query.
    level = models.PositiveSmallIntegerField()
    level_name = models.CharField(max_length=16)
    logger_name = models.CharField(max_length=200)
    message = models.TextField()
    traceback = models.TextField(blank=True, default="")

    request_id = models.CharField(max_length=64, blank=True, default="")
    request_method = models.CharField(max_length=10, blank=True, default="")
    # The path only: query strings can carry tokens, so they are never stored.
    request_path = models.CharField(max_length=500, blank=True, default="")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    # No database constraint: rows are written in batches from a background
    # thread, and a user deleted in between must not make the whole batch fail.
    # Django still nulls these when a user is deleted.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        db_constraint=False,
    )

    module = models.CharField(max_length=200, blank=True, default="")
    func_name = models.CharField(max_length=200, blank=True, default="")
    line_no = models.PositiveIntegerField(null=True, blank=True)
    # The record's ``extra`` fields, with sensitive keys redacted.
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "system_log"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["-created_at", "-id"], name="system_log_created_idx"),
            models.Index(fields=["level", "-created_at"], name="system_log_level_idx"),
            models.Index(fields=["logger_name", "-created_at"], name="system_log_logger_idx"),
            models.Index(fields=["request_id"], name="system_log_request_idx"),
        ]

    def __str__(self):
        return f"[{self.level_name}] {self.logger_name}: {self.message[:80]}"
