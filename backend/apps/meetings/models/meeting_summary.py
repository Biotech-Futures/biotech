from django.conf import settings
from django.db import models


class MeetingSummary(models.Model):
    """Mentor-authored wrap-up.

    A separate table from :class:`MeetingNote` so "only the mentor writes
    this" is a model boundary the permission class can key on, rather than a
    per-field check inside a serializer shared with the group-writable note.

    ``published_at`` is the visibility switch: null means draft (author and
    admins only), set means the whole group can read it.
    """

    meeting = models.OneToOneField(
        "meetings.GroupMeeting",
        on_delete=models.CASCADE,
        related_name="summary",
    )
    body = models.TextField(blank=True, default="")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meeting_summary"
        verbose_name = "Meeting Summary"
        verbose_name_plural = "Meeting Summaries"

    def __str__(self):
        state = "published" if self.published_at else "draft"
        return f"Summary for meeting {self.meeting_id} ({state})"

    @property
    def is_published(self) -> bool:
        return self.published_at is not None
