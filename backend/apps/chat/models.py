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
    attachment_filename = models.CharField(max_length=255)
    attachment_url = models.URLField()

    class Meta:
        db_table = 'message_attachments'
        verbose_name = "Message Attachment"
        verbose_name_plural = "Message Attachments"
        constraints = [
            models.UniqueConstraint(
                fields=['message', 'attachment_filename'],
                name='unique_filename_per_message'
            ),
            models.UniqueConstraint(
                fields=['message', 'attachment_url'],
                name='unique_url_per_message'
            ),
        ]
        indexes = [models.Index(fields=['message'])]

    def __str__(self):
        return f"Attachment {self.id} for Message {self.message.id}"

class Messages(models.Model):
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    group = models.ForeignKey("groups.Groups", on_delete=models.CASCADE)
    message_text = models.CharField(max_length=255)
    sent_datetime = models.DateTimeField(default=timezone.now)
    deleted_flag = models.BooleanField(default=False)

    class Meta:
        db_table = "messages"
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["sent_datetime"]
        constraints = [
            models.UniqueConstraint(
                fields=["sender_user", "group", "sent_datetime"],
                name="unique_message_per_user_per_time",
            ),
            models.CheckConstraint(
                condition=models.Q(deleted_flag__in=[True, False]),
                name="deleted_flag_boolean",
            ),
        ]
        indexes = [
            models.Index(fields=["group", "sent_datetime"]),
            models.Index(fields=["sender_user"]),
        ]

    def __str__(self):
        return f"{self.sender_user} -> {self.group}: {self.message_text[:20]}"
    

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
        verbose_name = "Message Resource"
        verbose_name_plural = "Message Resource"
        unique_together = ("message", "resource")
        indexes = [
            models.Index(fields=["message"]),
            models.Index(fields=["resource"]),
        ]

    def __str__(self):
        return f"Resource {self.resource_id} linked to Message {self.message_id}"