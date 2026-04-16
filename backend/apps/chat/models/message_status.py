from django.conf import settings
from django.db import models
from django.utils import timezone
from .messages import Messages

class MessageStatus(models.Model):
    class StatusChoices(models.TextChoices):
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        READ = "read", "Read"

    message = models.ForeignKey(
        Messages,
        on_delete=models.CASCADE,
        related_name="statuses",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_statuses",
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.SENT,
    )
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "message_status"
        verbose_name = "Message Status"
        verbose_name_plural = "Message Statuses"
        unique_together = [("message", "user")]
        indexes = [
            models.Index(fields=["message"]),
            models.Index(fields=["user", "status"]),
        ]

    def mark_delivered(self):
        if not self.delivered_at:
            self.delivered_at = timezone.now()
            self.status = self.StatusChoices.DELIVERED
            self.save(update_fields=["delivered_at", "status"])

    def mark_read(self):
        now = timezone.now()
        if not self.delivered_at:
            self.delivered_at = now
        if not self.read_at:
            self.read_at = now
        self.status = self.StatusChoices.READ
        self.save(update_fields=["delivered_at", "read_at", "status"])

    def __str__(self):
        return f"Message {self.message_id} -> {self.user}: {self.status}"
