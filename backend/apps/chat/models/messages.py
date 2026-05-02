from django.conf import settings
from django.db import models
from django.utils import timezone

class MessageType(models.TextChoices):
    TEXT = "text", "Text"
    RESOURCE = "resource", "Resource Link"
    SYSTEM = "system", "System Message"

class Messages(models.Model):
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    group = models.ForeignKey("groups.Groups", on_delete=models.CASCADE)
    parent_id = models.BigIntegerField(null=True, blank=True)
    message_text = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT,
    )

    class Meta:
        db_table = "messages"
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["sent_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(deleted_at__isnull=True)
                    | models.Q(deleted_at__gte=models.F("sent_at"))
                ),
                name="message_deleted_after_sent",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(edited_at__isnull=True)
                    | models.Q(edited_at__gte=models.F("sent_at"))
                ),
                name="message_edited_after_sent",
            ),
        ]
        indexes = [
            models.Index(fields=["group", "sent_at"]),
            models.Index(fields=["sender_user"]),
            models.Index(fields=["deleted_at"]),
        ]

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def is_edited(self):
        return self.edited_at is not None

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def __str__(self):
        preview = self.message_text[:40] if self.message_text else f"[{self.message_type}]"
        return f"{self.sender_user} -> {self.group}: {preview}"
