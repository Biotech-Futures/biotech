from django.conf import settings
from django.db import models


class GroupMeeting(models.Model):
    """A mentor-scheduled meeting for one group.

    Deliberately thin. The schedule itself lives on the linked
    ``events.Events`` row: start/end, timezone, ``location_link`` (the
    Zoom / Teams / Meet URL) and the two reminder stamps. Reusing Events
    is what makes the meeting appear in the in-app calendar and what gets
    it picked up by the existing 24h/1h reminder dispatcher -- neither
    behaviour needs any code in this app.

    What lives here is only what Events cannot express: which group owns
    the meeting, and who called it.
    """

    event = models.OneToOneField(
        "events.Events",
        on_delete=models.CASCADE,
        related_name="group_meeting",
    )
    group = models.ForeignKey(
        "groups.Groups",
        on_delete=models.CASCADE,
        related_name="meetings",
    )
    # Mirrored onto Events.host_user so the calendar and reminder emails can
    # name a host without joining through this table.
    organiser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organised_meetings",
    )
    agenda = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "group_meeting"
        verbose_name = "Group Meeting"
        verbose_name_plural = "Group Meetings"
        ordering = ["-event__start_datetime"]
        indexes = [
            models.Index(fields=["group"]),
            models.Index(fields=["organiser"]),
        ]

    def __str__(self):
        return f"Meeting for {self.group_id} (event {self.event_id})"

    # Passthroughs -- the schedule is authoritative on Events, never copied.
    @property
    def start_datetime(self):
        return self.event.start_datetime

    @property
    def join_link(self):
        return self.event.location_link

    @property
    def is_cancelled(self):
        return self.event.deleted_at is not None
