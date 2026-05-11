from django.conf import settings
from django.db import models
from django.utils import timezone


class MessageReaction(models.Model):
    """One row per (message, user, emoji). Toggle semantics: re-reacting
    with the same emoji deletes the row. Aggregated into ``reactions``
    on the message payload by the serializer."""

    message = models.ForeignKey(
        "Messages",
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_reactions",
    )
    emoji = models.CharField(max_length=16)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "message_reactions"
        verbose_name = "Message Reaction"
        verbose_name_plural = "Message Reactions"
        unique_together = ("message", "user", "emoji")
        indexes = [
            models.Index(fields=["message", "emoji"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user_id} {self.emoji} -> Message {self.message_id}"
