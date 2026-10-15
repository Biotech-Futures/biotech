from django.conf import settings
from django.db import models


class MeetingNote(models.Model):
    """Shared live note -- any active group participant may edit it.

    Edited collaboratively over the meeting WebSocket (see consumers.py).
    ``ydoc_state`` is the source of truth: the encoded Yjs document that
    concurrent edits are merged into, so nobody's typing is lost.
    ``body`` is a plain-text snapshot of it, rewritten on every merge, for
    readers that don't speak Yjs (the REST GET, admin, summaries).

    ``revision`` is a plain edit counter, bumped once per merged update.
    It no longer guards concurrent writes -- the CRDT merge does that.
    """

    meeting = models.OneToOneField(
        "meetings.GroupMeeting",
        on_delete=models.CASCADE,
        related_name="note",
    )
    body = models.TextField(blank=True, default="")
    # Encoded Yjs document state; ``body`` is its plain-text snapshot.
    ydoc_state = models.BinaryField(null=True, blank=True)
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
