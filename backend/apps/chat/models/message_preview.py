from django.db import models
from django.utils import timezone


class MessagePreview(models.Model):
    """Persisted OpenGraph preview for a single chat message.

    The Redis cache (``cache:og:<md5(url)>``) deduplicates *fetches* across
    users for 24h, but we still write the unfurled metadata into the database
    so:

    1. Reloading the chat history doesn't require a Redis round-trip per
       message — the preview ships inside the message payload.
    2. Cache eviction (memory pressure, restart) doesn't blank historical
       previews. Redis is the *acceleration*, Postgres is the source of truth.

    One preview per message is enough for the current product spec; if we
    later decide to unfurl every URL in a message, we'd swap the OneToOne for
    a ForeignKey + ordering field.
    """

    message = models.OneToOneField(
        "chat.Messages",
        on_delete=models.CASCADE,
        related_name="preview",
    )
    url = models.TextField()
    title = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    image_url = models.TextField(blank=True, default="")
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "message_previews"
        verbose_name = "Message Preview"
        verbose_name_plural = "Message Previews"
        indexes = [
            models.Index(fields=["message"]),
        ]

    def to_payload(self) -> dict[str, str]:
        """Wire shape for the websocket ``message.preview_ready`` event.

        The contract is fixed by the spec — three keys, all strings — so the
        front end can render with no null checks. Empty strings represent
        "missing" rather than ``null``.
        """
        return {
            "title": self.title or "",
            "desc": self.description or "",
            "img": self.image_url or "",
        }

    def __str__(self) -> str:
        return f"Preview<msg={self.message_id} url={self.url[:40]}>"
