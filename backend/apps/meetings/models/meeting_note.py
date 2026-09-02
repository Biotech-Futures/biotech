from django.conf import settings
from django.db import models


class MeetingNote(models.Model):
    """Shared live note -- any active group participant may edit it.

    ``revision`` is an optimistic-concurrency counter, not a history. Every
    accepted write bumps it by one; a client PATCHing with a stale revision
    is rejected with 409 instead of silently overwriting whatever landed in
    between. Without it, two people typing at once lose each other's work.
    """

    meeting = models.OneToOneField(
        "meetings.GroupMeeting",
        on_delete=models.CASCADE,
        related_name="note",
    )
    body = models.TextField(blank=True, default="")
    revision = models.PositiveIntegerField(default=0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "meeting_note"
        verbose_name = "Meeting Note"
        verbose_name_plural = "Meeting Notes"

    def __str__(self):
        return f"Note for meeting {self.meeting_id} (rev {self.revision})"
