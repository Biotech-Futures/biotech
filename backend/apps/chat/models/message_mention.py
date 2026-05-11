from django.conf import settings
from django.db import models


class MessageMention(models.Model):
    """One row per (message, mentioned_user). Written when a message is
    created or edited and its text contains a ``<@user_id>`` token whose
    target is a member of the message's group.

    ``read_at`` is independent of ``MessageStatus.read_at``: scrolling a
    message into view in the chat panel does *not* clear the mention.
    The mentions inbox is a separate channel users explicitly triage —
    consistent with how Slack/Discord treat mentions vs. message reads.
    """

    message = models.ForeignKey(
        "Messages",
        on_delete=models.CASCADE,
        related_name="mentions",
    )
    mentioned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentions_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "message_mentions"
        verbose_name = "Message Mention"
        verbose_name_plural = "Message Mentions"
        unique_together = ("message", "mentioned_user")
        indexes = [
            # Covers the inbox query "unread mentions for user X, newest first".
            models.Index(fields=["mentioned_user", "read_at"]),
        ]

    def __str__(self):
        return f"@{self.mentioned_user_id} in message {self.message_id}"
