"""Tests covering this session's behavioural changes to the events app.

* N+1 regression on the list endpoint (queries stay flat as event count grows).
* ``rsvp_status=pending`` filter treats "no row" as pending too.
* ``EventInviteListHTMLView`` scopes through ``visible_events_queryset`` so a
  caller can't fish for rosters of events they can't see.
* Capacity: incoming ACCEPTED coerces to WAITLISTED when the cap is met.
* Capacity: a freed slot auto-promotes the oldest waitlisted user.
* iCal export returns a well-formed VEVENT response.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import (
    EventRsvp,
    EventTargetGroup,
    Events,
)
from apps.groups.models import Groups

User = get_user_model()


def _make_event(name, *, days=2, dur_hours=2, **kwargs):
    now = timezone.now()
    defaults = dict(
        description="",
        start_datetime=now + timedelta(days=days),
        ends_datetime=now + timedelta(days=days, hours=dur_hours),
        event_format="virtual",
    )
    defaults.update(kwargs)
    return Events.objects.create(event_name=name, **defaults)


class NPlusOneRegressionTests(APITestCase):
    """Query count for GET /events/v1/ stays constant as event count grows.

    Asserts that adding more events doesn't multiply the queries the
    prefetch_related is supposed to flatten.
    """

    def setUp(self):
        self.user = User.objects.create_user(email="np@test.com", password="x")
        self.client.force_authenticate(user=self.user)

    def _list_query_count(self, n_events):
        Events.objects.all().delete()
        for i in range(n_events):
            _make_event(f"NPlusOne {i}")
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get("/events/v1/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        return len(ctx.captured_queries)

    def test_query_count_does_not_scale_with_event_count(self):
        q3 = self._list_query_count(3)
        q12 = self._list_query_count(12)
        # Allow a small slack for things like pagination COUNT; the
        # essential point is queries don't grow proportional to N.
        self.assertLess(q12, q3 + 4, f"query count grew from {q3} -> {q12}")


class PendingFilterTests(APITestCase):
    """``?rsvp_status=pending`` includes events with no RSVP row at all."""

    def setUp(self):
        self.user = User.objects.create_user(email="pf@test.com", password="x")
        self.other = User.objects.create_user(email="pf2@test.com", password="x")
        self.client.force_authenticate(user=self.user)

        self.untouched = _make_event("Untouched")
        self.invited = _make_event("Invited")
        EventRsvp.objects.create(
            event=self.invited,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.PENDING,
        )
        self.accepted = _make_event("Accepted")
        EventRsvp.objects.create(
            event=self.accepted,
            user=self.user,
            rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
            responded_at=timezone.now(),
        )
        # A different user's pending row should NOT widen the caller's view.
        self.other_pending = _make_event("OthersPending")
        EventRsvp.objects.create(
            event=self.other_pending,
            user=self.other,
            rsvp_status=EventRsvp.RsvpStatus.PENDING,
        )

    def _names(self, response):
        results = response.data.get("results", response.data)
        return {row["event_name"] for row in results}

    def test_pending_includes_explicit_and_no_row(self):
        response = self.client.get("/events/v1/?rsvp_status=pending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = self._names(response)
        self.assertIn("Untouched", names)        # no row → counts as pending
        self.assertIn("Invited", names)          # explicit pending
        self.assertIn("OthersPending", names)    # untouched for *me*
        self.assertNotIn("Accepted", names)      # explicitly accepted → excluded

    def test_accepted_filter_unchanged(self):
        response = self.client.get("/events/v1/?rsvp_status=accepted")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = self._names(response)
        self.assertEqual(names, {"Accepted"})


class InviteListScopeTests(APITestCase):
    """A non-host mentor can't fish for rosters outside their visibility."""

    def setUp(self):
        # An event targeted to a group the mentor doesn't belong to sits
        # outside their scope. Targeting is group + role only now, so a
        # non-member with no matching role can't see it — the surviving
        # equivalent of the old cross-track visibility boundary.
        self.group_b = Groups.objects.create(group_name="Group B")
        # A user with no group membership: can only see untargeted events.
        # visible_events_queryset narrows scope once IsNotStudent lets them
        # past the gate.
        self.mentor = User.objects.create_user(
            email="mentor@test.com", password="x"
        )

        # Force the IsNotStudent role check via mentor role assignment.
        from apps.resources.models import RoleAssignmentHistory, Roles
        role, _ = Roles.objects.get_or_create(role_name="mentor")
        RoleAssignmentHistory.objects.create(
            user=self.mentor,
            role=role,
            valid_from=timezone.now() - timedelta(days=1),
        )

        # An event targeted to Group B (out of the mentor's scope).
        self.event_b = _make_event("Group B Event")
        EventTargetGroup.objects.create(event=self.event_b, group=self.group_b)
        EventRsvp.objects.create(
            event=self.event_b,
            user=self.mentor,  # any non-target user — won't affect visibility
            rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
            responded_at=timezone.now(),
        )

    def test_mentor_outside_scope_gets_404_on_roster(self):
        # Drop the priming RSVP so the mentor truly has no claim on the event.
        EventRsvp.objects.filter(event=self.event_b, user=self.mentor).delete()
        self.client.force_authenticate(user=self.mentor)
        response = self.client.get(f"/events/v1/{self.event_b.id}/rsvps/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CapacityTests(APITestCase):
    """``max_attendees`` coerces over-cap RSVPs to WAITLISTED and auto-promotes."""

    def setUp(self):
        self.user_a = User.objects.create_user(email="a@cap.test", password="x")
        self.user_b = User.objects.create_user(email="b@cap.test", password="x")
        self.user_c = User.objects.create_user(email="c@cap.test", password="x")
        self.event = _make_event("Capped", max_attendees=2)

    def _rsvp(self, user, status_value):
        self.client.force_authenticate(user=user)
        return self.client.post(
            f"/events/v1/{self.event.id}/rsvp/",
            {"rsvp_status": status_value},
            format="json",
        )

    def test_over_cap_user_lands_on_waitlist(self):
        r_a = self._rsvp(self.user_a, "accepted")
        r_b = self._rsvp(self.user_b, "accepted")
        r_c = self._rsvp(self.user_c, "accepted")
        self.assertEqual(r_a.status_code, status.HTTP_200_OK)
        self.assertEqual(r_a.data["rsvp_status"], "accepted")
        self.assertEqual(r_b.data["rsvp_status"], "accepted")
        # Cap met; user C is coerced to waitlist.
        self.assertEqual(r_c.data["rsvp_status"], "waitlisted")

    def test_accepted_user_leaving_promotes_waitlisted(self):
        self._rsvp(self.user_a, "accepted")
        self._rsvp(self.user_b, "accepted")
        self._rsvp(self.user_c, "accepted")  # waitlisted
        self.assertEqual(
            EventRsvp.objects.get(event=self.event, user=self.user_c).rsvp_status,
            "waitlisted",
        )

        # User A leaves — user C should auto-promote.
        r = self._rsvp(self.user_a, "declined")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        c_row = EventRsvp.objects.get(event=self.event, user=self.user_c)
        self.assertEqual(c_row.rsvp_status, "accepted")


class IcalExportTests(APITestCase):
    """The .ics endpoint returns a parseable VEVENT for a visible event."""

    def setUp(self):
        self.user = User.objects.create_user(email="ical@test.com", password="x")
        self.event = _make_event(
            "ICS Test Event",
            location="University of Sydney",
            event_format="in_person",
            description="One; two, three\\nlines",
        )
        self.client.force_authenticate(user=self.user)

    def test_ical_response_shape(self):
        response = self.client.get(f"/events/v1/{self.event.id}/ical/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response["Content-Type"].startswith("text/calendar"))
        self.assertIn("attachment", response["Content-Disposition"])
        body = response.content.decode("utf-8")
        for required in (
            "BEGIN:VCALENDAR",
            "BEGIN:VEVENT",
            "SUMMARY:ICS Test Event",
            f"UID:event-{self.event.id}@biotechfutures",
            "END:VEVENT",
            "END:VCALENDAR",
        ):
            self.assertIn(required, body, f"missing line: {required}")
        # CRLF line endings per RFC 5545.
        self.assertIn("\r\n", body)

    def test_ical_serializes_non_utc_start_in_utc(self):
        # Australia/Sydney start at noon → 02:00 UTC in summer. Independent
        # of the host's tz settings, the .ics body must encode in UTC
        # with the trailing Z.
        from datetime import datetime
        from zoneinfo import ZoneInfo

        syd_tz = ZoneInfo("Australia/Sydney")
        start_local = datetime(2027, 1, 15, 12, 0, tzinfo=syd_tz)
        end_local = datetime(2027, 1, 15, 14, 0, tzinfo=syd_tz)
        tz_event = Events.objects.create(
            event_name="TZ Round-trip",
            description="",
            start_datetime=start_local,
            ends_datetime=end_local,
            event_format="virtual",
        )
        response = self.client.get(f"/events/v1/{tz_event.id}/ical/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.content.decode("utf-8")
        # 12:00 Sydney (UTC+11 in January) -> 01:00 UTC.
        self.assertIn("DTSTART:20270115T010000Z", body)
        self.assertIn("DTEND:20270115T030000Z", body)
