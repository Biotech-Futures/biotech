"""The meetings REST API: who may do what, and what a bad request gets back."""

from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.audit.models import AuditLog
from apps.events.models import EventRsvp
from apps.meetings import services
from apps.meetings.models import GroupMeeting, MeetingSummary

from .support import LIST_URL, MeetingGroupMixin, detail_url


def _future(days=1):
    return timezone.now() + timedelta(days=days)


class ScheduleMeetingTests(MeetingGroupMixin, APITestCase):
    def payload(self, **overrides):
        data = {
            "group": self.group.pk,
            "title": "Project kickoff",
            "start_datetime": _future().isoformat(),
            "duration_minutes": 45,
            "join_link": "https://meet.google.com/abc-defg-hij",
            "timezone_name": "Australia/Sydney",
        }
        data.update(overrides)
        return data

    def test_a_mentor_of_the_group_can_schedule_a_meeting(self):
        self.client.force_login(self.mentor)
        response = self.client.post(LIST_URL, self.payload(), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        meeting = GroupMeeting.objects.get(pk=response.data["id"])
        self.assertEqual(meeting.organiser, self.mentor)
        self.assertEqual(response.data["title"], "Project kickoff")
        self.assertEqual(response.data["provider"], "google_meet")
        self.assertEqual(response.data["timezone_name"], "Australia/Sydney")
        self.assertTrue(response.data["can_manage"])
        self.assertEqual(
            meeting.event.ends_datetime - meeting.event.start_datetime,
            timedelta(minutes=45),
        )
        self.assertTrue(
            AuditLog.objects.filter(entity_type="group_meeting", action="create").exists()
        )

    def test_a_supervisor_and_an_admin_can_schedule_too(self):
        for user in (self.supervisor, self.admin):
            self.client.force_login(user)
            response = self.client.post(LIST_URL, self.payload(), format="json")
            self.assertEqual(response.status_code, 201, (user.email, response.data))

    def test_a_student_cannot_schedule_a_meeting(self):
        self.client.force_login(self.student)
        response = self.client.post(LIST_URL, self.payload(), format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(GroupMeeting.objects.exists())

    def test_a_mentor_of_another_group_cannot_schedule_for_this_one(self):
        self.client.force_login(self.other_mentor)
        response = self.client.post(LIST_URL, self.payload(), format="json")
        self.assertEqual(response.status_code, 403)

    def test_signed_out_visitors_are_refused(self):
        response = self.client.post(LIST_URL, self.payload(), format="json")
        self.assertIn(response.status_code, (401, 403))

    def test_an_explicit_end_time_is_kept(self):
        start = _future()
        self.client.force_login(self.mentor)
        payload = self.payload(
            start_datetime=start.isoformat(),
            ends_datetime=(start + timedelta(hours=2)).isoformat(),
        )
        del payload["duration_minutes"]
        response = self.client.post(LIST_URL, payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        meeting = GroupMeeting.objects.get(pk=response.data["id"])
        self.assertEqual(meeting.event.ends_datetime - meeting.event.start_datetime, timedelta(hours=2))

    def test_neither_an_end_time_nor_a_duration_is_a_400(self):
        self.client.force_login(self.mentor)
        payload = self.payload()
        del payload["duration_minutes"]
        response = self.client.post(LIST_URL, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("duration_minutes", response.data["fields"])

    def test_an_end_before_the_start_is_a_400_not_a_crash(self):
        start = _future()
        self.client.force_login(self.mentor)
        response = self.client.post(
            LIST_URL,
            self.payload(
                start_datetime=start.isoformat(),
                ends_datetime=(start - timedelta(minutes=5)).isoformat(),
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("ends_datetime", response.data["fields"])

    def test_a_meeting_in_the_past_is_refused(self):
        self.client.force_login(self.mentor)
        response = self.client.post(
            LIST_URL,
            self.payload(start_datetime=(timezone.now() - timedelta(hours=1)).isoformat()),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("start_datetime", response.data["fields"])

    def test_duration_is_held_between_5_minutes_and_8_hours(self):
        self.client.force_login(self.mentor)
        for minutes, expected in ((4, 400), (5, 201), (480, 201), (481, 400)):
            response = self.client.post(
                LIST_URL, self.payload(duration_minutes=minutes), format="json"
            )
            self.assertEqual(response.status_code, expected, (minutes, response.data))

    def test_the_join_link_must_be_a_web_address(self):
        self.client.force_login(self.mentor)
        response = self.client.post(
            LIST_URL, self.payload(join_link="javascript:alert(1)"), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("join_link", response.data["fields"])

    def test_a_deleted_group_cannot_be_booked(self):
        self.group.deleted_at = timezone.now()
        self.group.save()
        self.client.force_login(self.admin)
        response = self.client.post(LIST_URL, self.payload(), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("group", response.data["fields"])


class ListMeetingsTests(MeetingGroupMixin, APITestCase):
    def ids(self, response):
        self.assertEqual(response.status_code, 200, response.data)
        return [row["id"] for row in response.data["results"]]

    def test_group_members_see_their_meetings_and_outsiders_do_not(self):
        meeting = self.book()
        for user in (self.student, self.mentor, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.ids(self.client.get(LIST_URL)), [meeting.pk], user.email)

        self.client.force_login(self.outsider)
        self.assertEqual(self.ids(self.client.get(LIST_URL)), [])

    def test_upcoming_and_past_are_split_by_the_end_time(self):
        upcoming = self.book()
        past = self.book()
        services.reschedule_meeting(
            past,
            start=timezone.now() - timedelta(days=2),
            end=timezone.now() - timedelta(days=2) + timedelta(minutes=30),
        )
        self.client.force_login(self.student)
        self.assertEqual(self.ids(self.client.get(LIST_URL, {"when": "upcoming"})), [upcoming.pk])
        self.assertEqual(self.ids(self.client.get(LIST_URL, {"when": "past"})), [past.pk])

    def test_upcoming_meetings_come_soonest_first(self):
        later = self.book(start_in=timedelta(days=3))
        sooner = self.book(start_in=timedelta(days=1))
        self.client.force_login(self.student)
        self.assertEqual(
            self.ids(self.client.get(LIST_URL, {"when": "upcoming"})), [sooner.pk, later.pk]
        )

    def test_the_group_filter_narrows_the_list(self):
        here = self.book()
        there = self.book(group=self.other_group, organiser=self.other_mentor)
        self.client.force_login(self.admin)
        self.assertEqual(self.ids(self.client.get(LIST_URL, {"group": self.group.pk})), [here.pk])
        self.assertEqual(
            self.ids(self.client.get(LIST_URL, {"group": self.other_group.pk})), [there.pk]
        )

    def test_cancelled_meetings_are_hidden_unless_asked_for(self):
        meeting = self.book()
        services.cancel_meeting(meeting)
        self.client.force_login(self.student)
        self.assertEqual(self.ids(self.client.get(LIST_URL)), [])
        response = self.client.get(LIST_URL, {"include_cancelled": "true"})
        self.assertEqual(self.ids(response), [meeting.pk])
        self.assertIsNotNone(response.data["results"][0]["cancelled_at"])

    def test_an_outsider_gets_404_on_the_detail(self):
        meeting = self.book()
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(detail_url(meeting)).status_code, 404)

    def test_a_student_is_told_they_cannot_manage_it(self):
        meeting = self.book()
        self.client.force_login(self.student)
        response = self.client.get(detail_url(meeting))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["can_manage"])
        self.assertEqual(response.data["provider"], "zoom")


class ChangeMeetingTests(MeetingGroupMixin, APITestCase):
    def test_the_organiser_can_rename_and_reschedule(self):
        meeting = self.book()
        start = _future(days=2)
        self.client.force_login(self.mentor)
        response = self.client.patch(
            detail_url(meeting),
            {
                "title": "Moved check-in",
                "start_datetime": start.isoformat(),
                "ends_datetime": (start + timedelta(hours=1)).isoformat(),
                "agenda": "1. Progress",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        meeting.refresh_from_db()
        meeting.event.refresh_from_db()
        self.assertEqual(meeting.event.event_name, "Moved check-in")
        self.assertEqual(meeting.event.start_datetime, start)
        self.assertEqual(meeting.agenda, "1. Progress")
        log = AuditLog.objects.get(entity_type="group_meeting", action="update")
        self.assertEqual(log.after_state["event_name"], "Moved check-in")

    def test_a_co_mentor_who_did_not_book_it_can_still_edit_it(self):
        meeting = self.book()
        self.client.force_login(self.supervisor)
        response = self.client.patch(detail_url(meeting), {"title": "Renamed"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_a_student_cannot_edit_or_cancel(self):
        meeting = self.book()
        self.client.force_login(self.student)
        self.assertEqual(
            self.client.patch(detail_url(meeting), {"title": "Mine now"}, format="json").status_code,
            403,
        )
        self.assertEqual(self.client.delete(detail_url(meeting)).status_code, 403)
        meeting.event.refresh_from_db()
        self.assertEqual(meeting.event.event_name, "Weekly check-in")
        self.assertIsNone(meeting.event.deleted_at)

    def test_half_a_reschedule_is_refused(self):
        meeting = self.book()
        self.client.force_login(self.mentor)
        response = self.client.patch(
            detail_url(meeting), {"start_datetime": _future(days=5).isoformat()}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_a_reschedule_that_ends_before_it_starts_is_refused(self):
        meeting = self.book()
        start = _future(days=2)
        self.client.force_login(self.mentor)
        response = self.client.patch(
            detail_url(meeting),
            {
                "start_datetime": start.isoformat(),
                "ends_datetime": (start - timedelta(minutes=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("ends_datetime", response.data["fields"])

    def test_a_full_put_goes_through_the_same_path(self):
        meeting = self.book()
        self.client.force_login(self.mentor)
        response = self.client.put(
            detail_url(meeting), {"title": "Put title", "join_link": "https://teams.microsoft.com/l/x"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["provider"], "microsoft_teams")

    def test_cancelling_is_a_soft_delete_on_the_event(self):
        meeting = self.book()
        self.client.force_login(self.mentor)
        self.assertEqual(self.client.delete(detail_url(meeting)).status_code, 204)
        meeting.event.refresh_from_db()
        self.assertIsNotNone(meeting.event.deleted_at)
        self.assertTrue(GroupMeeting.objects.filter(pk=meeting.pk).exists())
        self.assertTrue(AuditLog.objects.filter(entity_type="group_meeting", action="cancel").exists())


class NoteAndSummaryApiTests(MeetingGroupMixin, APITestCase):
    def test_any_member_can_read_the_note_and_an_outsider_cannot(self):
        meeting = self.book()
        note = meeting.note
        note.body = "Agenda: progress"
        note.save()

        self.client.force_login(self.student)
        response = self.client.get(detail_url(meeting, "note/"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["body"], "Agenda: progress")

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(detail_url(meeting, "note/")).status_code, 404)

    def test_there_is_no_summary_until_the_mentor_writes_one(self):
        meeting = self.book()
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(detail_url(meeting, "summary/")).status_code, 404)

    def test_a_draft_summary_is_hidden_from_students_until_published(self):
        meeting = self.book()
        self.client.force_login(self.mentor)
        response = self.client.put(
            detail_url(meeting, "summary/"), {"body": "Draft thoughts"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["is_published"])
        self.assertEqual(self.client.get(detail_url(meeting, "summary/")).status_code, 200)
        self.assertEqual(self.client.get(detail_url(meeting)).data["summary"]["body"], "Draft thoughts")

        self.client.force_login(self.student)
        self.assertEqual(self.client.get(detail_url(meeting, "summary/")).status_code, 404)
        self.assertIsNone(self.client.get(detail_url(meeting)).data["summary"])

        self.client.force_login(self.mentor)
        self.client.put(
            detail_url(meeting, "summary/"), {"body": "Final notes", "publish": True}, format="json"
        )
        self.client.force_login(self.student)
        response = self.client.get(detail_url(meeting, "summary/"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["body"], "Final notes")
        self.assertEqual(self.client.get(detail_url(meeting)).data["summary"]["body"], "Final notes")

    def test_a_student_cannot_write_the_summary(self):
        meeting = self.book()
        self.client.force_login(self.student)
        response = self.client.put(
            detail_url(meeting, "summary/"), {"body": "I wrote this", "publish": True}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(MeetingSummary.objects.exists())

    def test_sync_attendees_adds_a_member_who_joined_late(self):
        meeting = self.book()
        from apps.groups.models import GroupMembership

        GroupMembership.objects.create(
            group=self.group, user=self.outsider,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        self.client.force_login(self.mentor)
        response = self.client.post(detail_url(meeting, "sync-attendees/"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"added": 1})
        self.assertTrue(EventRsvp.objects.filter(event=meeting.event, user=self.outsider).exists())
