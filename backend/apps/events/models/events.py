from django.conf import settings
from django.db import models


class Events(models.Model):
    class EventTypeChoices(models.TextChoices):
        WORKSHOP = "workshop", "Workshop"
        WEBINAR = "webinar", "Webinar"
        SYMPOSIUM = "symposium", "Symposium"
        NETWORKING = "networking", "Networking"
        SOCIAL = "social", "Social"
        OTHER = "other", "Other"

    event_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    track = models.ForeignKey("groups.Tracks", on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=100, choices=EventTypeChoices.choices, blank=True, null=True)
    start_datetime = models.DateTimeField()
    ends_datetime = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True, null=True)
    host_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    deleted_at = models.DateTimeField(default=None, blank=True, null=True)
    event_image = models.CharField(max_length=255, blank=True, null=True)
    location_link = models.URLField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Zoom URL when is_virtual=True, Google Maps URL otherwise.",
    )
    is_virtual = models.BooleanField(default=False)
    # Optional cap. Counts ACCEPTED rows only. When set and met, new
    # user-side ACCEPTED RSVPs are coerced to WAITLISTED; freed slots
    # auto-promote the oldest waitlisted user.
    max_attendees = models.PositiveIntegerField(blank=True, null=True)
    # Stamp == current start_datetime ⇒ already reminded for this schedule.
    # Reschedules auto-re-arm because the stamp no longer matches.
    reminder_24h_sent_for_start = models.DateTimeField(blank=True, null=True)
    reminder_1h_sent_for_start = models.DateTimeField(blank=True, null=True)


    class Meta:
        db_table = "events"
        verbose_name = "Event"
        verbose_name_plural = "Events"
        ordering = ["start_datetime"]
        indexes = [
            models.Index(fields=["start_datetime"]),
            models.Index(fields=["host_user"]),
            models.Index(fields=["track"]),
            # ``?when=upcoming|past`` on the list endpoint filters by
            # ends_datetime against now(); without this it falls back to
            # a heap scan once the events table grows.
            models.Index(fields=["ends_datetime"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_datetime__gt=models.F("start_datetime")),
                name="check_event_end_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(is_virtual=False) | models.Q(location__isnull=True),
                name="check_virtual_location_null",
            ),
        ]

    def __str__(self):
        return self.event_name
