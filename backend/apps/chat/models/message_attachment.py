from django.db import models
from django.utils import timezone


class MessageAttachment(models.Model):
    message = models.ForeignKey(
        "Messages",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    storage_key = models.CharField(max_length=255)
    attachment_filename = models.CharField(max_length=255)
    attachment_mime_type = models.CharField(max_length=100, null=True, blank=True)
    attachment_size = models.BigIntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "message_attachments"
        verbose_name = "Message Attachment"
        verbose_name_plural = "Message Attachments"
        indexes = [
            models.Index(fields=["message"]),
            models.Index(fields=["uploaded_at"]),
        ]

    def __str__(self):
        return f"{self.attachment_filename} on Message {self.message_id}"
