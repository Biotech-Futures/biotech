from django.conf import settings
from django.db import models
from django.utils import timezone


class MessageScreeningStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SAFE = "safe", "Safe"
    FLAGGED = "flagged", "Flagged"
    FAILED = "failed", "Failed"


class MessageScreening(models.Model):
    message = models.ForeignKey(
        "chat.Messages",
        on_delete=models.CASCADE,
        related_name="screenings",
    )
    group = models.ForeignKey(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="message_screenings",
    )
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="message_screenings",
    )
    status = models.CharField(
        max_length=20,
        choices=MessageScreeningStatus.choices,
        default=MessageScreeningStatus.PENDING,
    )
    text_hash = models.CharField(max_length=64)
    message_snapshot = models.TextField(blank=True, default="")
    risk_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    category = models.CharField(max_length=80, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    provider = models.CharField(max_length=80, blank=True, default="local_stub")
    error_message = models.TextField(blank=True, default="")
    screened_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "message_screenings"
        verbose_name = "Message Screening"
        verbose_name_plural = "Message Screenings"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["message", "text_hash"],
                name="message_screening_once_per_text_hash",
            ),
        ]
        indexes = [
            models.Index(fields=["message", "text_hash"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["group", "status"]),
            models.Index(fields=["sender_user", "created_at"]),
        ]

    @property
    def is_flagged(self):
        return self.status == MessageScreeningStatus.FLAGGED

    def __str__(self):
        return f"Screening {self.id} for message {self.message_id}: {self.status}"
