from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.events.models import EventRsvp, Events
from apps.events.services import send_due_event_rsvp_reminders
from apps.users.models import User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@test.biotechfutures.org",
)
class EventRsvpReminderTests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        self.accepted_user = User.objects.create_user(
            email="accepted@test.com",
            password="pw",
            first_name="Accepted",
        )
        self.tentative_user = User.objects.create_user(
            email="tentative@test.com",
            password="pw",
            first_name="Tentative",
        )
        self.declined_user = User.objects.create_user(
            email="declined@test.com",
            password="pw",
            first_name="Declined",
        )
        self.pending_user = User.objects.create_user(
            email="pending@test.com",
            password="pw",
            first_name="Pending",
        )
        self.no_email_user = User.objects.create_user(
            email="no-email@test.com",
            password="pw",
            first_name="NoEmail",
        )
        self.no_email_user.email = ""
        self.no_email_user.save(update_fields=["email"])
        self.event = Events.objects.create(
            event_name="Reminder Event",
            description="Bring your questions.",
            start_datetime=self.now + timezone.timedelta(hours=24, minutes=30),
            ends_datetime=self.now + timezone.timedelta(hours=26, minutes=30),
            location="Sydney Campus",
        )
        EventRsvp.objects.create(
            event=self.event,
            user=self.accepted_user,
            rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
            responded_at=self.now,
        )
        EventRsvp.objects.create(
            event=self.event,
            user=self.tentative_user,
            rsvp_status=EventRsvp.RsvpStatus.TENTATIVE,
            responded_at=self.now,
        )
        EventRsvp.objects.create(
            event=self.event,
            user=self.declined_user,
            rsvp_status=EventRsvp.RsvpStatus.DECLINED,
            responded_at=self.now,
        )
        EventRsvp.objects.create(
            event=self.event,
            user=self.pending_user,
            rsvp_status=EventRsvp.RsvpStatus.PENDING,
        )

    def test_service_sends_only_to_accepted_attendees(self):
        EventRsvp.objects.create(
            event=self.event,
            user=self.no_email_user,
            rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
            responded_at=self.now,
        )

        summary = send_due_event_rsvp_reminders(now=self.now)

        self.assertEqual(summary["events_considered"], 1)
        self.assertEqual(summary["emails_sent"], 1)
        self.assertEqual(summary["emails_failed"], 0)
        self.assertEqual(summary["emails_skipped"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.accepted_user.email])
        self.assertIn("Reminder Event", mail.outbox[0].subject)

        self.event.refresh_from_db()
        self.assertEqual(self.event.rsvp_reminder_sent_for_start, self.event.start_datetime)

    def test_service_does_not_resend_same_event_start(self):
        self.event.rsvp_reminder_sent_for_start = self.event.start_datetime
        self.event.save(update_fields=["rsvp_reminder_sent_for_start"])

        summary = send_due_event_rsvp_reminders(now=self.now)

        self.assertEqual(summary["events_considered"], 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_rescheduled_event_becomes_eligible_again(self):
        old_start = self.event.start_datetime
        self.event.rsvp_reminder_sent_for_start = old_start
        self.event.start_datetime = self.now + timezone.timedelta(hours=24, minutes=45)
        self.event.ends_datetime = self.now + timezone.timedelta(hours=26, minutes=45)
        self.event.save(
            update_fields=[
                "rsvp_reminder_sent_for_start",
                "start_datetime",
                "ends_datetime",
            ]
        )

        summary = send_due_event_rsvp_reminders(now=self.now)

        self.assertEqual(summary["events_considered"], 1)
        self.assertEqual(summary["emails_sent"], 1)
        self.event.refresh_from_db()
        self.assertEqual(self.event.rsvp_reminder_sent_for_start, self.event.start_datetime)

    def test_deleted_event_is_skipped(self):
        self.event.deleted_at = self.now
        self.event.save(update_fields=["deleted_at"])

        summary = send_due_event_rsvp_reminders(now=self.now)

        self.assertEqual(summary["events_considered"], 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_management_command_dry_run_does_not_send_or_mark(self):
        call_command("send_event_rsvp_reminders", "--dry-run")

        self.event.refresh_from_db()
        self.assertIsNone(self.event.rsvp_reminder_sent_for_start)
        self.assertEqual(len(mail.outbox), 0)
