"""Tests for the RSVP reminder dispatcher."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

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
    """Event sitting in the default 24h reminder window (24h–25h ahead)."""
    defaults = {
        "event_name": "Test Event",
        "description": "A test event.",
        "start_datetime": timezone.now() + timedelta(hours=24, minutes=30),
        "ends_datetime": timezone.now() + timedelta(hours=26),
        "location": "Sydney",
        "event_format": "in_person",
    }
    defaults.update(overrides)
    return Events.objects.create(**defaults)


def _make_event_in_1h_window(**overrides):
    """Event sitting in the 1h reminder window (1h–2h ahead)."""
    defaults = {
        "event_name": "Imminent Event",
        "start_datetime": timezone.now() + timedelta(hours=1, minutes=15),
        "ends_datetime": timezone.now() + timedelta(hours=3),
        "location": "Sydney",
    }
    defaults.update(overrides)
    return Events.objects.create(**defaults)


def _rsvp(event, user, status_value=EventRsvp.RsvpStatus.ACCEPTED):
    return EventRsvp.objects.create(event=event, user=user, rsvp_status=status_value)


class Reminder24hWindowTests(TestCase):
    """Window filter + idempotency invariants for the 24h kind."""

    def setUp(self):
        self.attendee = User.objects.create_user(
            email="alice@example.com", password="pw", first_name="Alice"
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
        self.assertEqual(event.reminder_24h_sent_for_start, event.start_datetime)
        self.assertIsNone(event.reminder_1h_sent_for_start)

    def test_event_under_24h_not_sent(self):
        # 23h away — past the 24h window, not yet inside the 1h window.
        event = _make_event(
            start_datetime=timezone.now() + timedelta(hours=23),
            ends_datetime=timezone.now() + timedelta(hours=25),
        )
        _rsvp(event, self.attendee)

        events, sent, _ = send_due_rsvp_reminders()

        self.assertEqual((events, sent), (0, 0))
        self.assertEqual(mail.outbox, [])
        event.refresh_from_db()
        self.assertIsNone(event.reminder_24h_sent_for_start)

    def test_event_over_25h_not_sent(self):
        # 26h away — past the 24h window. Will be caught one hour later.
        event = _make_event(
            start_datetime=timezone.now() + timedelta(hours=26),
            ends_datetime=timezone.now() + timedelta(hours=28),
        )
        _rsvp(event, self.attendee)

        events, sent, _ = send_due_rsvp_reminders()

        self.assertEqual((events, sent), (0, 0))
        self.assertEqual(mail.outbox, [])

    def test_already_stamped_event_skipped(self):
        event = _make_event()
        event.reminder_24h_sent_for_start = event.start_datetime
        event.save(update_fields=["reminder_24h_sent_for_start"])
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
        self.assertIsNone(event.reminder_24h_sent_for_start)

    def test_running_twice_does_not_double_send(self):
        event = _make_event()
        _rsvp(event, self.attendee)

        send_due_rsvp_reminders()
        send_due_rsvp_reminders()

        self.assertEqual(len(mail.outbox), 1)
        event.refresh_from_db()
        self.assertEqual(event.reminder_24h_sent_for_start, event.start_datetime)


class Reminder1hWindowTests(TestCase):
    """The 1h-kind reminder fires in its own window with its own stamp."""

    def setUp(self):
        self.attendee = User.objects.create_user(
            email="bob@example.com", password="pw", first_name="Bob"
        )

    def test_event_in_1h_window_sends_final_reminder(self):
        event = _make_event_in_1h_window()
        _rsvp(event, self.attendee)

        events, sent, failed = send_due_rsvp_reminders()

        self.assertEqual((events, sent, failed), (1, 1, 0))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Starting soon", mail.outbox[0].subject)
        event.refresh_from_db()
        self.assertEqual(event.reminder_1h_sent_for_start, event.start_datetime)
        self.assertIsNone(event.reminder_24h_sent_for_start)

    def test_1h_window_skips_pending_status(self):
        # The 1h kind only emails confirmed attendees — no nudge.
        pending = User.objects.create_user(email="pending@example.com", password="pw")
        event = _make_event_in_1h_window()
        _rsvp(event, pending, EventRsvp.RsvpStatus.PENDING)

        events, sent, _ = send_due_rsvp_reminders()

        self.assertEqual((events, sent), (1, 0))
        self.assertEqual(mail.outbox, [])

    def test_kind_24h_does_not_touch_1h_field(self):
        # Run only the 24h kind explicitly. Even if a candidate event
        # would also match the 1h window, the 1h field must remain
        # unset because that kind never ran.
        event = _make_event()
        _rsvp(event, self.attendee)

        send_due_rsvp_reminders(kind="24h")

        event.refresh_from_db()
        self.assertEqual(event.reminder_24h_sent_for_start, event.start_datetime)
        self.assertIsNone(event.reminder_1h_sent_for_start)


class RescheduleReArmTests(TestCase):
    """Moving start_datetime forward must re-arm a previously-fired
    reminder. The whole point of stamping the *start_datetime* (rather
    than a boolean True) is so the dispatcher knows whether the stamp
    is for the *current* schedule."""

    def setUp(self):
        self.attendee = User.objects.create_user(
            email="reschedule@example.com", password="pw"
        )

    def test_24h_reminder_re_arms_after_reschedule(self):
        event = _make_event()
        _rsvp(event, self.attendee)

        send_due_rsvp_reminders()
        self.assertEqual(len(mail.outbox), 1)
        event.refresh_from_db()
        self.assertEqual(event.reminder_24h_sent_for_start, event.start_datetime)

        # Admin reschedules: bump start by 24h. Run dispatcher again —
        # the stamp now != start_datetime so we re-fire.
        new_start = event.start_datetime + timedelta(days=1)
        Events.objects.filter(pk=event.pk).update(
            start_datetime=new_start,
            ends_datetime=new_start + timedelta(hours=2),
        )

        # Fast-forward "now" so the rescheduled event lands in the
        # 24h window again. We do this by patching timezone.now in
        # the service module.
        with patch("apps.events.services.timezone.now") as fake_now:
            fake_now.return_value = new_start - timedelta(hours=24, minutes=30)
            send_due_rsvp_reminders()

        self.assertEqual(len(mail.outbox), 2)
        event.refresh_from_db()
        self.assertEqual(event.reminder_24h_sent_for_start, new_start)


class DryRunTests(TestCase):
    def test_dry_run_neither_sends_nor_stamps(self):
        event = _make_event()
        user = User.objects.create_user(email="dry@example.com", password="pw")
        _rsvp(event, user)

        events, sent, failed = send_due_rsvp_reminders(dry_run=True)

        # Dry run reports the count it *would* have sent...
        self.assertEqual((events, sent, failed), (1, 1, 0))
        # ...but does not touch the outbox or the stamp.
        self.assertEqual(mail.outbox, [])
        event.refresh_from_db()
        self.assertIsNone(event.reminder_24h_sent_for_start)


class Status24hAudienceTests(TestCase):
    """The 24h kind has two audiences: ACCEPTED reminder + PENDING nudge."""

    def setUp(self):
        self.event = _make_event()

    def test_accepted_and_pending_receive_reminders_tentative_and_declined_do_not(self):
        accepted = User.objects.create_user(email="accepted@example.com", password="pw")
        tentative = User.objects.create_user(email="tentative@example.com", password="pw")
        declined = User.objects.create_user(email="declined@example.com", password="pw")
        pending = User.objects.create_user(email="pending@example.com", password="pw")
        _rsvp(self.event, accepted, EventRsvp.RsvpStatus.ACCEPTED)
        _rsvp(self.event, tentative, EventRsvp.RsvpStatus.TENTATIVE)
        _rsvp(self.event, declined, EventRsvp.RsvpStatus.DECLINED)
        _rsvp(self.event, pending, EventRsvp.RsvpStatus.PENDING)

        events, sent, _ = send_due_rsvp_reminders()

        # ACCEPTED gets the reminder, PENDING gets the nudge, the
        # other two statuses are silent.
        self.assertEqual((events, sent), (1, 2))
        sent_to = sorted(m.to[0] for m in mail.outbox)
        self.assertIn("accepted@example.com", sent_to)
        self.assertIn("pending@example.com", sent_to)
        self.assertNotIn("tentative@example.com", sent_to)
        self.assertNotIn("declined@example.com", sent_to)


class ReminderBodyTests(TestCase):
    """Plain-text body covers virtual / in-person / null-location cases.

    The HTML alternative is exercised in :class:`HtmlAlternativeTests`.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="body@example.com", password="pw", first_name="Bob"
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
        event = _make_event(
            event_format="virtual",
            location=None,
            location_link="https://zoom.example/abc",
        )
        _rsvp(event, self.user)

        send_due_rsvp_reminders()

        body = mail.outbox[0].body
        self.assertIn("Join online: https://zoom.example/abc", body)

    def test_virtual_event_without_link_has_fallback_copy(self):
        event = _make_event(event_format="virtual", location=None, location_link=None)
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


class HtmlAlternativeTests(TestCase):
    """Every reminder ships text/plain + text/html. The HTML alt must
    carry the brand chrome and the event info card."""

    def test_html_alt_present_and_contains_event_info(self):
        user = User.objects.create_user(
            email="html@example.com", password="pw", first_name="Hannah"
        )
        event = _make_event(event_name="Lab Tour", location="Building 10")
        _rsvp(event, user)

        send_due_rsvp_reminders()

        message = mail.outbox[0]
        self.assertEqual(len(message.alternatives), 1)
        html_body, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("BIOTech Futures", html_body)
        self.assertIn("Lab Tour", html_body)
        self.assertIn("Building 10", html_body)
        # Info-card uppercase labels distinguish HTML rendering from
        # the plain alt.
        self.assertIn("DATE", html_body.upper())


class TimezoneLocalizationTests(TestCase):
    """Per-user IANA timezone drives the event time/label in the email body."""

    def test_recipient_in_sydney_gets_local_time_and_tz_label(self):
        event = _make_event()
        sydney_user = User.objects.create_user(
            email="syd@example.com",
            password="pw",
            first_name="Syd",
            timezone="Australia/Sydney",
        )
        _rsvp(event, sydney_user)

        send_due_rsvp_reminders()

        body = mail.outbox[0].body
        local = event.start_datetime.astimezone(ZoneInfo("Australia/Sydney"))
        expected_hour = local.strftime("%I:%M %p")
        expected_label = local.tzname()  # AEDT in summer, AEST in winter

        self.assertIn(expected_hour, body)
        self.assertIn(expected_label, body)
        # Sydney recipient must never see the UTC label.
        self.assertNotIn("UTC", body)

    def test_recipient_with_utc_timezone_gets_utc_label(self):
        event = _make_event()
        utc_user = User.objects.create_user(
            email="utc@example.com",
            password="pw",
            first_name="Yu",
            timezone="UTC",
        )
        _rsvp(event, utc_user)

        send_due_rsvp_reminders()

        body = mail.outbox[0].body
        expected_hour = event.start_datetime.strftime("%I:%M %p")
        self.assertIn(expected_hour, body)
        self.assertIn("UTC", body)

    def test_invalid_timezone_falls_back_to_utc(self):
        # A bad DB value (manual edit, legacy import) must not block the send.
        event = _make_event()
        user = User.objects.create_user(
            email="bad-tz@example.com",
            password="pw",
            first_name="Bea",
            timezone="Not/A/Real/Zone",
        )
        _rsvp(event, user)

        send_due_rsvp_reminders()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("UTC", mail.outbox[0].body)

    def test_two_recipients_in_different_zones_see_different_times(self):
        # Same event, same instant — different localized strings.
        event = _make_event()
        sydney = User.objects.create_user(
            email="syd2@example.com", password="pw", timezone="Australia/Sydney"
        )
        london = User.objects.create_user(
            email="lon@example.com", password="pw", timezone="Europe/London"
        )
        _rsvp(event, sydney)
        _rsvp(event, london)

        send_due_rsvp_reminders()

        bodies = {m.to[0]: m.body for m in mail.outbox}
        self.assertNotEqual(bodies["syd2@example.com"], bodies["lon@example.com"])


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

        real_send = mail.EmailMultiAlternatives.send
        call_count = {"n": 0}

        def flaky_send(self_msg, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("simulated SMTP blowup")
            return real_send(self_msg, *args, **kwargs)

        with patch(
            "apps.events.services.EmailMultiAlternatives.send",
            new=flaky_send,
        ):
            events, sent, failed = send_due_rsvp_reminders()

        self.assertEqual((events, sent, failed), (1, 2, 1))
        # The two successful sends still hit the outbox.
        self.assertEqual(len(mail.outbox), 2)

    def test_event_stays_stamped_even_when_every_send_fails(self):
        # Once we claim the row we must NOT unstamp it on per-recipient
        # failure — a retry would re-spam anyone we did reach.
        event = _make_event()
        user = User.objects.create_user(email="x@example.com", password="pw")
        _rsvp(event, user)

        with patch(
            "apps.events.services._send_one_reminder",
            side_effect=RuntimeError("smtp down"),
        ):
            send_due_rsvp_reminders()

        event.refresh_from_db()
        self.assertEqual(event.reminder_24h_sent_for_start, event.start_datetime)


class ManagementCommandTests(TestCase):
    def test_command_runs_and_reports_counts(self):
        event = _make_event()
        user = User.objects.create_user(email="cmd@example.com", password="pw")
        _rsvp(event, user)

        out = StringIO()
        call_command("send_rsvp_reminders", stdout=out)

        output = out.getvalue()
        self.assertIn("events=1", output)
        self.assertIn("sent=1", output)
        self.assertEqual(len(mail.outbox), 1)

    def test_command_dry_run_does_not_send_or_stamp(self):
        event = _make_event()
        user = User.objects.create_user(email="cmd-dry@example.com", password="pw")
        _rsvp(event, user)

        out = StringIO()
        call_command("send_rsvp_reminders", "--dry-run", stdout=out)

        self.assertIn("dry-run", out.getvalue())
        self.assertEqual(mail.outbox, [])
        event.refresh_from_db()
        self.assertIsNone(event.reminder_24h_sent_for_start)

    def test_command_kind_flag_runs_only_that_kind(self):
        # Two events: one in the 24h window, one in the 1h window.
        # --kind 1h must email only the 1h-window event.
        attendee = User.objects.create_user(email="kind@example.com", password="pw")
        e_24h = _make_event(event_name="24h Event")
        e_1h = _make_event_in_1h_window(event_name="1h Event")
        _rsvp(e_24h, attendee)
        _rsvp(e_1h, attendee)

        out = StringIO()
        call_command("send_rsvp_reminders", "--kind", "1h", stdout=out)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("1h Event", mail.outbox[0].subject)
        e_24h.refresh_from_db()
        e_1h.refresh_from_db()
        self.assertIsNone(e_24h.reminder_24h_sent_for_start)
        self.assertEqual(e_1h.reminder_1h_sent_for_start, e_1h.start_datetime)


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

        response = self.client.post(self.url, HTTP_X_REMINDER_TOKEN="s3cret-token")

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
