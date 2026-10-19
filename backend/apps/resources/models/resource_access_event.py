from django.conf import settings
from django.db import models
from django.utils import timezone


class ResourceAccessEvent(models.Model):
    """An authenticated user explicitly choosing to open or download a resource."""

    resource = models.ForeignKey(
        "Resources", on_delete=models.CASCADE, related_name="access_events"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resource_access_events",
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "resource_access_event"
        verbose_name = "Resource Access Event"
        verbose_name_plural = "Resource Access Events"
