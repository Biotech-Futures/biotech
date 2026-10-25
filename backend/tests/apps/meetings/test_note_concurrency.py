"""Two members typing into the same shared meeting note at the same moment."""

import threading
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from pycrdt import Doc, Text

from apps.groups.models import Groups
from apps.meetings import services
from apps.meetings.models import MeetingNote


def _browser(state=None):
    """A browser's copy of the note, as the page builds it on connect."""
    doc = Doc()
    doc["note"] = text = Text()
    if state:
        doc.apply_update(state)
    return doc, text


def _type(doc, text, words):
    """What the page sends over the socket after typing ``words`` at the end."""
    before = doc.get_state()
    text += words
    return doc.get_update(before)


@skipUnlessDBFeature("has_select_for_update")
class SimultaneousNoteEditsTests(TransactionTestCase):
    """The row lock in ``apply_note_update`` is what keeps both edits.

    Skipped on SQLite: Django drops ``FOR UPDATE`` there silently, so this
    would pass without testing anything. It runs against local Postgres.
    """

    def setUp(self):
        self.mentor = get_user_model().objects.create_user(
            email="mentor@example.com", password="pw"
        )
        self.student = get_user_model().objects.create_user(
            email="student@example.com", password="pw"
        )
        start = timezone.now() + timedelta(days=1)
        self.meeting = services.schedule_meeting(
            organiser=self.mentor,
            group=Groups.objects.create(group_name="Notes group"),
            name="Weekly check-in",
            start=start,
            end=start + timedelta(minutes=30),
            join_link="https://zoom.us/j/1",
        )
        doc, text = _browser()
        services.apply_note_update(
            self.meeting.pk, self.mentor.pk, _type(doc, text, "Agenda: ")
        )
        self.saved = bytes(MeetingNote.objects.get(meeting=self.meeting).ydoc_state)

    def test_two_members_typing_at_once_both_keep_their_text(self):
        mentor_doc, mentor_text = _browser(self.saved)
        student_doc, student_text = _browser(self.saved)
        from_mentor = _type(mentor_doc, mentor_text, "Mentor's point. ")
        from_student = _type(student_doc, student_text, "Student's point. ")

        both_read = threading.Barrier(2)
        real_load = services._load_note_doc

        def load_then_wait_for_the_other(note):
            loaded = real_load(note)
            # Without the lock both writers stop here holding the same old
            # note, and whichever saves second wipes out the other. With it,
            # the second writer is still queued on the row, so this wait
            # times out and the first carries on alone.
            try:
                both_read.wait(timeout=1)
            except threading.BrokenBarrierError:
                pass
            return loaded

        failures = []

        def save(update, user):
            try:
                services.apply_note_update(self.meeting.pk, user.pk, update)
            except Exception as exc:  # surfaced below so the assert explains itself
                failures.append(exc)
            finally:
                connection.close()

        with patch.object(services, "_load_note_doc", load_then_wait_for_the_other):
            threads = [
                threading.Thread(target=save, args=(from_mentor, self.mentor)),
                threading.Thread(target=save, args=(from_student, self.student)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)

        self.assertEqual(failures, [])
        note = MeetingNote.objects.get(meeting=self.meeting)
        self.assertTrue(note.body.startswith("Agenda: "), note.body)
        self.assertIn("Mentor's point. ", note.body)
        self.assertIn("Student's point. ", note.body)
        self.assertEqual(note.revision, 3)

        # Both pages, once sent the stored note, show exactly what was saved.
        for doc, text in ((mentor_doc, mentor_text), (student_doc, student_text)):
            doc.apply_update(bytes(note.ydoc_state))
            self.assertEqual(str(text), note.body)
