from django.conf import settings
from django.db import models


class SubmissionComponent(models.Model):
    code = models.CharField(unique=True, max_length=32)
    name = models.CharField(max_length=255)
    is_optional = models.BooleanField(default=False)
    accepts_file = models.BooleanField(default=True)
    accepts_text = models.BooleanField(default=False)
    accepts_link = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "submission_component"
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return self.name


class Submission(models.Model):
    group = models.ForeignKey("groups.Groups", on_delete=models.CASCADE, related_name="submissions")
    component = models.ForeignKey(SubmissionComponent, on_delete=models.PROTECT, related_name="submissions")
    # Default storage is Azure Blob (settings.DEFAULT_FILE_STORAGE); the
    # upload_to prefix keeps submission files out of the resource/chat prefixes
    # that other apps write into the same container.
    file = models.FileField(upload_to="submissions/", null=True, blank=True)
    text = models.TextField(blank=True)
    link = models.URLField(max_length=1024, blank=True)
    submitted_at = models.DateTimeField(auto_now=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    is_late = models.BooleanField(default=False)

    class Meta:
        db_table = "submission"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "component"],
                name="unique_submission_per_group_component",
            ),
        ]
        indexes = [
            models.Index(fields=["group", "component"]),
            models.Index(fields=["submitted_at"]),
        ]

    def __str__(self):
        return f"{self.group} — {self.component.code}"
