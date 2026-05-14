from django.db import models
from django.utils import timezone


class MessageGif(models.Model):
    """Sidecar row attached 1:1 to a ``Messages`` row of type ``GIF``.

    Kept separate from ``Messages`` (rather than adding columns) so:
      * provider metadata stays out of the hot path table,
      * additional providers can be wired up later without another migration,
      * the ``MessageAttachment`` serializer's internal-download-URL logic
        does not get conflated with external GIF URLs.
    """

    message = models.OneToOneField(
        "Messages",
        on_delete=models.CASCADE,
        related_name="gif",
    )
    provider = models.CharField(max_length=32, default="tenor")
    provider_id = models.CharField(max_length=128)
    gif_url = models.URLField(max_length=500)
    preview_url = models.URLField(max_length=500, blank=True, default="")
    title = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "message_gifs"
        verbose_name = "Message GIF"
        verbose_name_plural = "Message GIFs"
        indexes = [
            models.Index(fields=["provider", "provider_id"]),
        ]

    def __str__(self):
        return f"{self.provider}:{self.provider_id} on Message {self.message_id}"
