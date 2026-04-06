# CHAT MODELS
from django.conf import settings
from django.db import models
from django.utils import timezone

class MessageAttachments(models.Model):
    message = models.ForeignKey(
        'Messages',
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    attachment_id = models.CharField(max_length=255, unique=True)
    attachment_filename = models.CharField(max_length=255)

    class Meta:
        db_table = 'message_attachments'
        verbose_name = "Message Attachment"
        verbose_name_plural = "Message Attachments"
        constraints = [
            models.UniqueConstraint(
                fields=['message', 'attachment_filename'],
                name='unique_filename_per_message'
            ),
        ]
        indexes = [models.Index(fields=['message'])]

    def __str__(self):
        return f"Attachment {self.id} for Message {self.message.id}"

# Phase 2 update: expanded Messages model with lifecycle fields.
# Changes: message_text CharField(255) → TextField (no limit),
# sent_datetime → sent_at, deleted_flag (bool) → deleted_at (timestamp),
# added edited_at, message_type, soft_delete() method, and is_deleted/is_edited properties.
class MessageType(models.TextChoices):
    TEXT = "text", "Text"
    ATTACHMENT = "attachment", "Attachment"
    RESOURCE = "resource", "Resource Link"
    SYSTEM = "system", "System Message"


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
    

class MessageResource(models.Model):
    """Link chat messages to global resources (apps.resources.Resources)."""

    message = models.ForeignKey(
        "Messages",
        on_delete=models.CASCADE,
        related_name="resources",
    )
    resource = models.ForeignKey(
        "resources.Resources",
        on_delete=models.CASCADE,
        related_name="chat_links",
    )

    class Meta:
        db_table = "message_resources"
        verbose_name = "Message Resource Link"
        verbose_name_plural = "Message Resource Links"
        unique_together = ("message", "resource")
        indexes = [
            models.Index(fields=["message"]),
            models.Index(fields=["resource"]),
        ]

    def __str__(self):
        return f"Resource {self.resource_id} linked to Message {self.message_id}"

# Phase 2 addition: tracks per-user delivery and read state for each message.
# Provides the foundation for unread counts and read receipts on the frontend.
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