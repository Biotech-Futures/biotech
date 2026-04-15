from django.conf import settings
from django.db import models
from django.utils import timezone

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
        verbose_name = "Message Resource Link"
        verbose_name_plural = "Message Resource Links"
        unique_together = ("message", "resource")
        indexes = [
            models.Index(fields=["message"]),
            models.Index(fields=["resource"]),
        ]

    def __str__(self):
        return f"Resource {self.resource_id} linked to Message {self.message_id}"
