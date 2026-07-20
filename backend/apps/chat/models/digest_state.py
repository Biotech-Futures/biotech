from django.conf import settings
from django.db import models


class ChatDigestState(models.Model):
    """Per-user throttle state for the daily "unread messages" email digest.

    Sparse: a row exists only once a user has been notified at least once, so
    it stays tiny. ``last_notified_message_id`` is a high-water mark — the max
    unread ``Messages.id`` at the moment of the last send. The digest only
    re-notifies a user when they have an unread message with ``id`` above this
    mark (i.e. genuinely new content), which is what stops a daily reminder
    from repeating forever while they simply haven't opened the app yet.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_digest_state",
    )
    last_notified_at = models.DateTimeField(null=True, blank=True)
    last_notified_message_id = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_digest_state"
        verbose_name = "Chat Digest State"
        verbose_name_plural = "Chat Digest States"

    def __str__(self):
        return f"digest[{self.user_id}] hwm={self.last_notified_message_id}"
