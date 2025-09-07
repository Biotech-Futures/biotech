# CHAT MODELS

from django.db import models
from django.utils import timezone

class MessageAttachments(models.Model):
    message = models.ForeignKey('Messages',on_delete=models.CASCADE)
    attachment_filename = models.CharField(max_length=255)

    class Meta:
        db_table = 'message_attachments'
        verbose_name = "Message Attachment"
        verbose_name_plural = "Message Attachments"
        constraints = [
            models.UniqueConstraint(
                fields=['attachment_id', 'message'],
                name='unique_attachment_per_message'
            ),
            models.UniqueConstraint(
                fields=['message', 'attachment_filename'],
                name='unique_filename_per_message'
            ), # Ensure each filename is unique per message
        ] # Composite unique constraint to ensure each attachment_id is unique per message, as composite keys aren't natively supported
        indexes = [
            models.Index(fields=['message']),
        ]

    def __str__(self):
        return f"Attachment {self.id} for Message {self.message.id}"

class Messages(models.Model):
    sender_user = models.ForeignKey('users.Users', on_delete=models.PROTECT) # Protect to prevent deletion if referenced by messages
    group = models.ForeignKey('groups.Groups', on_delete=models.CASCADE)
    # group = models.ForeignKey(
    #     'groups.Groups', on_delete=models.SET_NULL, null=True, blank=True
    #      ) 
    # Set null to allow messages to persist if group is deleted 
    # - *this is a consideration if we want to have historical messages*
    # for now I've left it as cascade to delete messages if group is deleted
    message_text = models.CharField(max_length=255)
    sent_datetime = models.DateTimeField(default=timezone.now)
    deleted_flag = models.BooleanField(default=False)

    class Meta:
        db_table = 'messages'
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['sent_datetime']  # default order: oldest first
        constraints = [
            # Avoid duplicate messages from the same user in the same group at the exact same time
            models.UniqueConstraint(
                fields=['sender_user', 'group', 'sent_datetime'],
                name='unique_message_per_user_per_time'
            ),
            # Ensure deleted_flag is always either True or False
            models.CheckConstraint(
                condition=models.Q(deleted_flag__in=[True, False]),
                name='deleted_flag_boolean'
            ),
        ]
        indexes = [
            models.Index(fields=['group', 'sent_datetime']),
            models.Index(fields=['sender_user']),
        ]

    def __str__(self):
        return f"{self.sender_user} -> {self.group}: {self.message_text[:20]}" # String representation for easier for messages