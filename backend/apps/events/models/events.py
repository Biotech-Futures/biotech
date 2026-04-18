from django.conf import settings
from django.db import models


class Events(models.Model):
    event_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    track = models.ForeignKey("groups.Tracks", on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=100, blank=True, null=True)
    start_datetime = models.DateTimeField()
    ends_datetime = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True, null=True)
    humanitix_link = models.URLField(max_length=255, blank=True, null=True)
    host_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    deleted_flag = models.BooleanField(default=False)
    deleted_datetime = models.DateTimeField(default=None, blank=True, null=True)
    event_image = models.CharField(max_length=255, blank=True, null=True)
    is_virtual = models.BooleanField(default=False)

    class Meta:
        db_table = "events"
        verbose_name = "Event"
        verbose_name_plural = "Events"
        ordering = ["start_datetime"]
        indexes = [
            models.Index(fields=["start_datetime"]),
            models.Index(fields=["host_user"]),
            models.Index(fields=["track"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_datetime__gt=models.F("start_datetime")),
                name="check_event_end_after_start",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(deleted_flag=False)
                    | (models.Q(deleted_flag=True) & models.Q(deleted_datetime__isnull=False))
                ),
                name="check_deleted_flag_and_datetime",
            ),
            models.CheckConstraint(
                condition=models.Q(is_virtual=False) | models.Q(location__isnull=True),
                name="check_virtual_location_null",
            ),
        ]

    def __str__(self):
        return self.event_name
