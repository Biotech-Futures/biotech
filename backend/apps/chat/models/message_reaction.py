from django.conf import settings
from django.db import models


class MessageReaction(models.Model):
    message = models.ForeignKey(
        'Messages',
        on_delete=models.CASCADE,
        related_name='reactions',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_reactions',
    )
    emoji_string = models.CharField(max_length=64)

    class Meta:
        db_table = 'message_reactions'
        verbose_name = 'Message Reaction'
        verbose_name_plural = 'Message Reactions'
        unique_together = [('message', 'user', 'emoji_string')]
        indexes = [
            models.Index(fields=['message']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user} reacted {self.emoji_string} to message {self.message_id}"