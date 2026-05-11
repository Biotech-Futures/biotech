"""Tests for the 24h RSVP reminder dispatcher.

Covers the service entry point, the management command, and the HTTP
trigger endpoint that the hourly GitHub Actions workflow hits.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.events.models import EventRsvp, Events
from apps.events.services import send_due_rsvp_reminders

User = get_user_model()


def _make_event(**overrides):
    defaults = {
        "event_name": "Test Event",
        "description": "A test event.",
        "start_datetime": timezone.now() + timedelta(hours=24, minutes=30),
        "ends_datetime": timezone.now() + timedelta(hours=26),
        "location": "Sydney",
        "is_virtual": False,
    }
    defaults.update(overrides)
    return Events.objects.create(**defaults)


def _rsvp(event, user, status_value=EventRsvp.RsvpStatus.ACCEPTED):
    return EventRsvp.objects.create(
        event=event, user=user, rsvp_status=status_value
    )


class SendDueRsvpRemindersTests(TestCase):
    """Window filter + idempotency invariants."""

    def setUp(self):
        self.attendee = User.objects.create_user(
            email="alice@example.com",
            password="pw",
            first_name="Alice",
        )

    def test_event_in_window_sends_reminder(self):
        event = _make_event()
        _rsvp(event, self.attendee)

        events, sent, failed = send_due_rsvp_reminders()

        self.assertEqual((events, sent, failed), (1, 1, 0))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Test Event", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["alice@example.com"])
        event.refresh_from_db()
        self.assertTrue(event.reminder_sent)

    def test_event_under_24h_not_sent(self):
        # 23h away — not yet in the window.
        event = _make_event(
            start_datetime=timezone.now() + timedelta(hours=23),
            ends_datetime=timezone.now() + timedelta(hours=25),
        )
        _rsvp(event, self.attendee)

        events, sent, _ = send_due_rsvp_reminders()

        self.assertEqual((events, sent), (0, 0))
        self.assertEqual(mail.outbox, [])
        event.refresh_from_db()
        self.assertFalse(event.reminder_sent)

    def test_event_over_25h_not_sent(self):
        # 26h away — past the window. Will be caught one hour later.
        event = _make_event(
            start_datetime=timezone.now() + timedelta(hours=26),
            ends_datetime=timezone.now() + timedelta(hours=28),
        )
        _rsvp(event, self.attendee)

        events, sent, _ = send_due_rsvp_reminders()

        self.assertEqual((events, sent), (0, 0))
        self.assertEqual(mail.outbox, [])

    def test_already_sent_event_skipped(self):
        event = _make_event(reminder_sent=True)
        _rsvp(event, self.attendee)

        events, sent, _ = send_due_rsvp_reminders()

        self.assertEqual((events, sent), (0, 0))
        self.assertEqual(mail.outbox, [])

    def test_soft_deleted_event_skipped(self):
        event = _make_event(deleted_at=timezone.now())
        _rsvp(event, self.attendee)

        events, sent, _ = send_due_rsvp_reminders()

        self.assertEqual((events, sent), (0, 0))
        self.assertEqual(mail.outbox, [])
        event.refresh_from_db()
        self.assertFalse(event.reminder_sent)

    def test_running_twice_does_not_double_send(self):
        event = _make_event()
        _rsvp(event, self.attendee)

        send_due_rsvp_reminders()
        send_due_rsvp_reminders()

        self.assertEqual(len(mail.outbox), 1)
        event.refresh_from_db()
        self.assertTrue(event.reminder_sent)


class RsvpStatusFilterTests(TestCase):
    """Only ACCEPTED RSVPs receive reminders — the codebase uses
    meeting-standard PARTSTAT wording, not 'going'/'maybe'."""

    def setUp(self):
        self.event = _make_event()

    def test_only_accepted_status_receives_reminder(self):
        accepted = User.objects.create_user(
            email="accepted@example.com", password="pw"
        )
        tentative = User.objects.create_user(
            email="tentative@example.com", password="pw"
        )
        declined = User.objects.create_user(
            email="declined@example.com", password="pw"
        )
        pending = User.objects.create_user(
            email="pending@example.com", password="pw"
        )
        _rsvp(self.event, accepted, EventRsvp.RsvpStatus.ACCEPTED)
        _rsvp(self.event, tentative, EventRsvp.RsvpStatus.TENTATIVE)
        _rsvp(self.event, declined, EventRsvp.RsvpStatus.DECLINED)
        _rsvp(self.event, pending, EventRsvp.RsvpStatus.PENDING)

        events, sent, _ = send_due_rsvp_reminders()

        self.assertEqual((events, sent), (1, 1))
        self.assertEqual([m.to for m in mail.outbox], [["accepted@example.com"]])


class ReminderBodyTests(TestCase):
    """Body template covers virtual / in-person / null-location cases."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="bob@example.com", password="pw", first_name="Bob"
        )

    def test_in_person_event_with_location_renders_location_line(self):
        event = _make_event(location="Building 10, UNSW")
        _rsvp(event, self.user)

        send_due_rsvp_reminders()

        body = mail.outbox[0].body
        self.assertIn("Location: Building 10, UNSW", body)
        self.assertNotIn("None", body)

    def test_in_person_event_with_null_location_omits_location_line(self):
        # The Events model allows location=NULL even when is_virtual=False;
        # the email must not render "Location: None".
        event = _make_event(location=None)
        _rsvp(event, self.user)

        send_due_rsvp_reminders()

        body = mail.outbox[0].body
        self.assertNotIn("None", body)
        self.assertNotIn("Location:", body)

    def test_virtual_event_uses_join_link(self):
        # The events check constraint requires location to be NULL when
        # is_virtual=True, so we don't set both.
        event = _make_event(
            is_virtual=True,
            location=None,
            location_link="https://zoom.example/abc",
        )
        _rsvp(event, self.user)

        send_due_rsvp_reminders()

        body = mail.outbox[0].body
        self.assertIn("Join online: https://zoom.example/abc", body)

    def test_virtual_event_without_link_has_fallback_copy(self):
        event = _make_event(is_virtual=True, location=None, location_link=None)
        _rsvp(event, self.user)

        send_due_rsvp_reminders()

        body = mail.outbox[0].body
        self.assertIn("virtual event", body.lower())

    def test_missing_first_name_falls_back_to_there(self):
        user = User.objects.create_user(
            email="noname@example.com", password="pw", first_name=""
        )
        event = _make_event()
        _rsvp(event, user)

        send_due_rsvp_reminders()

        self.assertIn("Hi there,", mail.outbox[0].body)


class ResilienceTests(TestCase):
    """One bad recipient must not abort the rest of the run."""

    def test_one_failing_send_does_not_block_others(self):
        event = _make_event()
        users = [
            User.objects.create_user(email=f"u{i}@example.com", password="pw")
            for i in range(3)
        ]
        for u in users:
            _rsvp(event, u)

        # Fail only the middle recipient. send_due_rsvp_reminders should
        # log the failure but mail the other two.
        real_send_mail = mail.send_mail
        call_count = {"n": 0}

        def flaky_send_mail(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("simulated SMTP blowup")
            return real_send_mail(*args, **kwargs)

        with patch("apps.events.services.send_mail", side_effect=flaky_send_mail):
            events, sent, failed = send_due_rsvp_reminders()

        self.assertEqual((events, sent, failed), (1, 2, 1))
        # The two successful sends used real send_mail and hit the
        # in-memory outbox.
        self.assertEqual(len(mail.outbox), 2)

    def test_reminder_sent_flipped_even_when_all_sends_fail(self):
        # Once we claim the row we must NOT unclaim it on per-recipient
        # failure — otherwise a retry would re-spam anyone we did reach.
        event = _make_event()
        user = User.objects.create_user(email="x@example.com", password="pw")
        _rsvp(event, user)

        with patch(
            "apps.events.services.send_mail",
            side_effect=RuntimeError("smtp down"),
        ):
            send_due_rsvp_reminders()

        event.refresh_from_db()
        self.assertTrue(event.reminder_sent)


class ManagementCommandTests(TestCase):
    def test_command_runs_and_reports_counts(self):
        event = _make_event()
        user = User.objects.create_user(email="cmd@example.com", password="pw")
        _rsvp(event, user)

        out = StringIO()
        call_command("send_rsvp_reminders", stdout=out)

        self.assertIn("events=1", out.getvalue())
        self.assertIn("sent=1", out.getvalue())
        self.assertEqual(len(mail.outbox), 1)


@override_settings(RSVP_REMINDER_TOKEN="s3cret-token")
class RsvpReminderTriggerEndpointTests(TestCase):
    """HTTP endpoint guarded by X-Reminder-Token header."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("rsvp-reminder-trigger")

    def test_rejects_missing_token(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_wrong_token(self):
        response = self.client.post(self.url, HTTP_X_REMINDER_TOKEN="nope")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_accepts_correct_token_and_dispatches(self):
        event = _make_event()
        user = User.objects.create_user(email="api@example.com", password="pw")
        _rsvp(event, user)

        response = self.client.post(
            self.url, HTTP_X_REMINDER_TOKEN="s3cret-token"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["events_processed"], 1)
        self.assertEqual(response.data["emails_sent"], 1)
        self.assertEqual(len(mail.outbox), 1)


@override_settings(RSVP_REMINDER_TOKEN="")
class RsvpReminderTriggerUnconfiguredTests(TestCase):
    """If the env var is unset the endpoint must refuse — fail loud
    rather than exposing an unauthenticated trigger."""

    def test_returns_503_when_token_unset(self):
        client = APIClient()
        response = client.post(
            reverse("rsvp-reminder-trigger"),
            HTTP_X_REMINDER_TOKEN="anything",
        )
        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
