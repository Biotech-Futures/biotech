from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# Window during which a sender can edit or delete their own message.
SELF_ACTION_WINDOW = timedelta(minutes=10)


class MessageType(models.TextChoices):
    TEXT = "text", "Text"
    ATTACHMENT = "attachment", "Attachment"
    RESOURCE = "resource", "Resource Link"
    SYSTEM = "system", "System Message"
    GIF = "gif", "GIF"

class Messages(models.Model):
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    group = models.ForeignKey("groups.Groups", on_delete=models.CASCADE)
    message_text = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT,
    )
    # Self-referential FK enables "quoted reply" threading. SET_NULL keeps
    # a reply visible if its parent is hard-deleted; soft-deletion of the
    # parent is handled at the serializer layer (text nulled, deleted=True)
    # so moderated content never leaks through children that quoted it.
    reply_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
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
            models.Index(fields=["reply_to"]),
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

    def restore(self):
        # Recovery is intentionally limited to clearing the tombstone.
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    def can_be_self_actioned_by(self, user) -> bool:
        """Sender's self-edit / self-delete window check. The 10-minute
        budget is shared by both edit and moderation paths so that the
        rule is defined once and stays consistent."""
        if not user or not getattr(user, "id", None):
            return False
        if self.sender_user_id != user.id:
            return False
        return timezone.now() <= self.sent_at + SELF_ACTION_WINDOW

    def __str__(self):
        preview = self.message_text[:40] if self.message_text else f"[{self.message_type}]"
        return f"{self.sender_user} -> {self.group}: {preview}"
