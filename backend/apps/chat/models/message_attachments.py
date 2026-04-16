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
