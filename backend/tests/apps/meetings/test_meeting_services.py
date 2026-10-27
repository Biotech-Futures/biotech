"""Scheduling, the stored note, the summary, and who counts as a mentor."""

from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.utils import timezone

from apps.events.models import EventRsvp, Events
from apps.groups.models import GroupMembership
from apps.meetings import services
from apps.meetings.models import MeetingNote
from apps.meetings.permissions import (
    can_manage_meeting,
    is_group_mentor,
    is_group_participant,
)
from apps.meetings.utils import detect_provider

from .support import MeetingGroupMixin, browser, typed


class ScheduleServiceTests(MeetingGroupMixin, TestCase):
    def test_a_meeting_is_a_virtual_group_meeting_event(self):
        meeting = self.book(timezone_name="Australia/Sydney", agenda="Intro")
        event = meeting.event
        self.assertEqual(event.event_type, Events.EventTypeChoices.GROUP_MEETING)
        self.assertEqual(event.event_format, Events.EventFormat.VIRTUAL)
        self.assertIsNone(event.location)
        self.assertEqual(event.location_link, "https://zoom.us/j/123")
        self.assertEqual(event.event_timezone, "Australia/Sydney")
        self.assertEqual(event.host_user, self.mentor)
        self.assertEqual(meeting.agenda, "Intro")
        self.assertTrue(MeetingNote.objects.filter(meeting=meeting).exists())

    def test_every_member_is_invited_and_the_organiser_has_already_said_yes(self):
        meeting = self.book()
        rsvps = {r.user_id: r for r in EventRsvp.objects.filter(event=meeting.event)}
        self.assertEqual(
            set(rsvps), {self.mentor.pk, self.supervisor.pk, self.student.pk, self.classmate.pk}
        )
        self.assertEqual(rsvps[self.mentor.pk].rsvp_status, EventRsvp.RsvpStatus.ACCEPTED)
        self.assertIsNotNone(rsvps[self.mentor.pk].responded_at)
        self.assertEqual(rsvps[self.student.pk].rsvp_status, EventRsvp.RsvpStatus.PENDING)
        self.assertIsNone(rsvps[self.student.pk].responded_at)

    def test_an_admin_who_is_not_in_the_group_is_still_invited_to_their_own_meeting(self):
        meeting = self.book(organiser=self.admin)
        self.assertTrue(EventRsvp.objects.filter(event=meeting.event, user=self.admin).exists())

    def test_syncing_again_never_resets_an_answer(self):
        meeting = self.book()
        rsvp = EventRsvp.objects.get(event=meeting.event, user=self.student)
        rsvp.rsvp_status = EventRsvp.RsvpStatus.DECLINED
        rsvp.responded_at = timezone.now()
        rsvp.save()

        self.assertEqual(services.sync_attendees(meeting), 0)
        rsvp.refresh_from_db()
        self.assertEqual(rsvp.rsvp_status, EventRsvp.RsvpStatus.DECLINED)

    def test_someone_who_left_the_group_is_not_invited(self):
        GroupMembership.objects.filter(user=self.classmate).update(left_at=timezone.now())
        meeting = self.book()
        self.assertFalse(EventRsvp.objects.filter(event=meeting.event, user=self.classmate).exists())

    def test_update_maps_each_field_onto_the_event(self):
        meeting = self.book()
        start = timezone.now() + timedelta(days=4)
        services.update_meeting(
            meeting,
            title="Renamed",
            description="New description",
            start_datetime=start,
            ends_datetime=start + timedelta(hours=1),
            join_link="https://meet.google.com/x",
            timezone_name="Asia/Shanghai",
            agenda=None,
        )
        event = Events.objects.get(pk=meeting.event_id)
        self.assertEqual(event.event_name, "Renamed")
        self.assertEqual(event.description, "New description")
        self.assertEqual(event.start_datetime, start)
        self.assertEqual(event.location_link, "https://meet.google.com/x")
        self.assertEqual(event.event_timezone, "Asia/Shanghai")
        meeting.refresh_from_db()
        self.assertEqual(meeting.agenda, "")

    def test_an_empty_update_writes_nothing(self):
        meeting = self.book()
        before = Events.objects.get(pk=meeting.event_id).event_name
        services.update_meeting(meeting)
        self.assertEqual(Events.objects.get(pk=meeting.event_id).event_name, before)

    def test_cancelling_twice_keeps_the_first_time(self):
        meeting = self.book()
        services.cancel_meeting(meeting)
        first = Events.objects.get(pk=meeting.event_id).deleted_at
        services.cancel_meeting(meeting)
        self.assertEqual(Events.objects.get(pk=meeting.event_id).deleted_at, first)
        self.assertTrue(meeting.is_cancelled)

    def test_the_meeting_passes_its_schedule_through_from_the_event(self):
        meeting = self.book()
        self.assertEqual(meeting.start_datetime, meeting.event.start_datetime)
        self.assertEqual(meeting.join_link, "https://zoom.us/j/123")
        self.assertFalse(meeting.is_cancelled)
        self.assertIn(str(meeting.group_id), str(meeting))
        self.assertIn("rev 0", str(meeting.note))


class StoredNoteTests(MeetingGroupMixin, TestCase):
    def test_edits_sent_one_after_another_all_land_in_the_note(self):
        meeting = self.book()
        doc, text = browser(services.get_note_state(meeting.pk))
        services.apply_note_update(meeting.pk, self.student.pk, typed(doc, text, "First. "))
        services.apply_note_update(meeting.pk, self.classmate.pk, typed(doc, text, "Second."))

        note = MeetingNote.objects.get(meeting=meeting)
        self.assertEqual(note.body, "First. Second.")
        self.assertEqual(note.revision, 2)
        self.assertEqual(note.updated_by, self.classmate)

    def test_a_newcomer_receives_everything_written_so_far(self):
        meeting = self.book()
        doc, text = browser()
        services.apply_note_update(meeting.pk, self.student.pk, typed(doc, text, "Hello"))

        _, newcomer_text = browser(services.get_note_state(meeting.pk))
        self.assertEqual(str(newcomer_text), "Hello")

    def test_a_note_written_before_live_editing_is_imported_once(self):
        meeting = self.book()
        MeetingNote.objects.filter(meeting=meeting).update(body="Old plain text", ydoc_state=None)

        first = services.get_note_state(meeting.pk)
        second = services.get_note_state(meeting.pk)
        _, text = browser(second)
        self.assertEqual(str(text), "Old plain text")
        self.assertEqual(first, second)
        self.assertIsNotNone(MeetingNote.objects.get(meeting=meeting).ydoc_state)

    def test_a_corrupt_update_is_refused_and_the_note_is_untouched(self):
        meeting = self.book()
        doc, text = browser()
        services.apply_note_update(meeting.pk, self.student.pk, typed(doc, text, "Safe"))
        with self.assertRaises(Exception):
            services.apply_note_update(meeting.pk, self.student.pk, b"not a yjs update")
        note = MeetingNote.objects.get(meeting=meeting)
        self.assertEqual(note.body, "Safe")
        self.assertEqual(note.revision, 1)

    def test_the_rest_reader_gets_a_note_even_if_none_was_stored(self):
        meeting = self.book()
        MeetingNote.objects.filter(meeting=meeting).delete()
        self.assertEqual(services.get_or_create_note(meeting).body, "")


class SummaryServiceTests(MeetingGroupMixin, TestCase):
    def test_publish_none_keeps_the_state_true_publishes_false_unpublishes(self):
        meeting = self.book()
        summary = services.upsert_summary(meeting, author=self.mentor, body="Draft")
        self.assertFalse(summary.is_published)
        self.assertIn("draft", str(summary))

        summary = services.upsert_summary(meeting, author=self.mentor, body="Done", publish=True)
        first_published = summary.published_at
        self.assertTrue(summary.is_published)
        self.assertIn("published", str(summary))

        summary = services.upsert_summary(meeting, author=self.supervisor, body="Edited")
        self.assertEqual(summary.published_at, first_published)
        self.assertEqual(summary.author, self.supervisor)

        summary = services.upsert_summary(meeting, author=self.mentor, body="Again", publish=True)
        self.assertEqual(summary.published_at, first_published)

        summary = services.upsert_summary(meeting, author=self.mentor, body="Back", publish=False)
        self.assertFalse(summary.is_published)


class WhoMayManageTests(MeetingGroupMixin, TestCase):
    def test_only_a_mentor_counts_as_a_mentor(self):
        # Not a supervisor since d67ff842 (#562).
        self.assertTrue(is_group_mentor(self.mentor, self.group.pk))
        self.assertFalse(is_group_mentor(self.supervisor, self.group.pk))
        self.assertFalse(is_group_mentor(self.student, self.group.pk))
        self.assertFalse(is_group_mentor(self.other_mentor, self.group.pk))

    def test_the_mentor_role_is_per_group(self):
        GroupMembership.objects.create(
            group=self.other_group, user=self.student,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        self.assertTrue(is_group_mentor(self.student, self.other_group.pk))
        self.assertFalse(is_group_mentor(self.student, self.group.pk))

    def test_someone_who_left_is_neither_mentor_nor_participant(self):
        GroupMembership.objects.filter(user=self.mentor).update(left_at=timezone.now())
        self.assertFalse(is_group_mentor(self.mentor, self.group.pk))
        self.assertFalse(is_group_participant(self.mentor, self.group.pk))

    def test_a_signed_out_visitor_is_nobody(self):
        meeting = self.book()
        anonymous = AnonymousUser()
        self.assertFalse(is_group_mentor(anonymous, self.group.pk))
        self.assertFalse(is_group_participant(anonymous, self.group.pk))
        self.assertFalse(can_manage_meeting(anonymous, meeting))
        self.assertFalse(can_manage_meeting(None, meeting))

    def test_who_can_manage_a_meeting(self):
        meeting = self.book()
        self.assertTrue(can_manage_meeting(self.mentor, meeting))
        self.assertFalse(can_manage_meeting(self.supervisor, meeting))
        self.assertTrue(can_manage_meeting(self.admin, meeting))
        self.assertFalse(can_manage_meeting(self.student, meeting))
        self.assertFalse(can_manage_meeting(self.other_mentor, meeting))

    def test_the_organiser_keeps_control_after_leaving_the_mentor_role(self):
        meeting = self.book()
        GroupMembership.objects.filter(user=self.mentor).update(
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT
        )
        self.assertTrue(can_manage_meeting(self.mentor, meeting))


class ProviderTests(TestCase):
    def test_known_providers_are_recognised_by_host(self):
        cases = {
            "https://zoom.us/j/1": "zoom",
            "https://us02web.zoom.us/j/1": "zoom",
            "https://meet.google.com/abc": "google_meet",
            "https://teams.microsoft.com/l/meetup": "microsoft_teams",
            "https://teams.live.com/meet/1": "microsoft_teams",
        }
        for url, provider in cases.items():
            self.assertEqual(detect_provider(url), provider, url)

    def test_look_alike_hosts_and_empty_links_are_other(self):
        for url in ("https://notzoom.us/j/1", "https://zoom.us.evil.com/", "", None, "not a url"):
            self.assertEqual(detect_provider(url), "other", url)
