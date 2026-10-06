"""
The scheduled emails (submission reminders, RSVP reminders, unread digest) go
through the shared system email path, and switching one off sends nothing and
records nothing, so the job carries on normally once it's switched back on.
Run with: python manage.py test tests.apps.services.test_scheduled_system_emails
"""

from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.chat.models import ChatDigestState, Messages
from apps.chat.services.digest import send_unread_message_digests
from apps.events.models import EventRsvp, Events
from apps.events.services import send_due_rsvp_reminders
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.services.models import SystemEmailSettings, SystemEmailTemplate
from apps.submissions.models import Deadline, SubmissionReminder
from apps.submissions.reminders import send_due_reminders
from apps.users.models import User

from tests.apps.submissions.seed_data import install_question_set


def _html(message):
    return next(body for body, mimetype in message.alternatives if mimetype == "text/html")


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class SubmissionReminderSystemEmailTests(TestCase):
    def setUp(self):
        role = Roles.objects.create(role_name="student")
        install_question_set()
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=3), is_active=True)
        self.group = Groups.objects.create(group_name="BTF-TEAM")
        user = User.objects.create_user(
            email="ada@test.local", password="testUser@123", first_name="Ada", last_name="S",
        )
        RoleAssignmentHistory.objects.create(
            user=user, role=role, valid_from=timezone.now(), valid_to=None
        )
        GroupMembership.objects.create(group=self.group, user=user, membership_role="student")

    def test_unedited_subject_is_unchanged(self):
        from django.conf import settings

        send_due_reminders()
        self.assertEqual(
            mail.outbox[0].subject, f"{settings.BRAND_NAME}: Submission reminder for BTF-TEAM",
        )

    def test_edited_email_uses_the_saved_wording_and_component_list(self):
        SystemEmailTemplate.objects.create(
            key="submission_reminder",
            subject="Still missing: {{ group_name }}",
            body_html="<p>Required:</p>{{ required_components_list }}",
        )
        send_due_reminders()

        message = mail.outbox[0]
        self.assertEqual(message.subject, "Still missing: BTF-TEAM")
        self.assertIn("<li><strong>Poster</strong>: Not Submitted</li>", _html(message))

    def test_switched_off_sends_nothing_and_records_nothing(self):
        SystemEmailTemplate.objects.create(key="submission_reminder", is_enabled=False)
        result = send_due_reminders()

        self.assertTrue(result["disabled"])
        self.assertEqual(mail.outbox, [])
        self.assertFalse(SubmissionReminder.objects.exists())

    def test_global_switch_off_sends_nothing(self):
        SystemEmailSettings.objects.create(emails_enabled=False)
        send_due_reminders()
        self.assertEqual(mail.outbox, [])


class RsvpReminderSystemEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com", password="pw", first_name="Alice"
        )
        self.event = Events.objects.create(
            event_name="Test Event",
            description="A test event.",
            start_datetime=timezone.now() + timedelta(hours=24, minutes=30),
            ends_datetime=timezone.now() + timedelta(hours=26),
            location="Sydney",
            event_format="in_person",
        )
        EventRsvp.objects.create(
            event=self.event, user=self.user, rsvp_status=EventRsvp.RsvpStatus.ACCEPTED,
        )

    def test_unedited_subject_is_unchanged(self):
        send_due_rsvp_reminders()
        self.assertEqual(mail.outbox[0].subject, "Reminder: Test Event")

    def test_edited_email_uses_the_saved_wording(self):
        SystemEmailTemplate.objects.create(
            key="rsvp_reminder",
            subject="{{ reminder_subject }} ({{ event_location }})",
            body_html="<p>Hi {{ first_name }}, {{ event_name }} is coming up.</p>",
        )
        send_due_rsvp_reminders()

        message = mail.outbox[0]
        self.assertEqual(message.subject, "Reminder: Test Event (Sydney)")
        self.assertIn("<p>Hi Alice, Test Event is coming up.</p>", _html(message))

    def test_switched_off_sends_nothing_and_leaves_the_event_unclaimed(self):
        SystemEmailTemplate.objects.create(key="rsvp_reminder", is_enabled=False)
        self.assertEqual(send_due_rsvp_reminders(), (0, 0, 0))

        self.assertEqual(mail.outbox, [])
        self.event.refresh_from_db()
        self.assertIsNone(self.event.reminder_24h_sent_for_start)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CONNECT_FROM_ADDRESS="connect@biotechfutures.org",
    CONNECT_DEFAULT_FROM_EMAIL="BIOTech Connect <connect@biotechfutures.org>",
    UNREAD_DIGEST_MIN_INTERVAL_HOURS=24,
    UNREAD_DIGEST_QUIET_START_HOUR=0,
    UNREAD_DIGEST_QUIET_END_HOUR=0,
)
class UnreadDigestSystemEmailTests(TestCase):
    def setUp(self):
        alice = User.objects.create_user(email="alice@t.com", password="pw", first_name="Alice")
        self.bob = User.objects.create_user(email="bob@t.com", password="pw", first_name="Bob")
        group = Groups.objects.create(group_name="BTF1")
        GroupMembership.objects.create(user=alice, group=group, membership_role="mentor")
        GroupMembership.objects.create(user=self.bob, group=group, membership_role="student")
        for _ in range(2):
            Messages.objects.create(group=group, sender_user=alice, message_text="hi")

    def test_unedited_subject_and_sender_are_unchanged(self):
        send_unread_message_digests()

        message = mail.outbox[0]
        self.assertIn("You have 2 unread messages on", message.subject)
        self.assertEqual(message.from_email, "BIOTech Connect <connect@biotechfutures.org>")

    def test_edited_email_uses_the_saved_wording_and_group_list(self):
        SystemEmailTemplate.objects.create(
            key="unread_messages",
            subject="{{ first_name }}, {{ unread_summary }} waiting",
            body_html="<p>Groups:</p>{{ unread_group_list }}",
        )
        send_unread_message_digests()

        message = mail.outbox[0]
        self.assertEqual(message.subject, "Bob, 2 unread messages waiting")
        self.assertIn("<ul><li>BTF1: 2</li></ul>", _html(message))
        self.assertEqual(message.from_email, "BIOTech Connect <connect@biotechfutures.org>")

    def test_switched_off_sends_nothing_and_claims_nobody(self):
        SystemEmailTemplate.objects.create(key="unread_messages", is_enabled=False)
        self.assertEqual(send_unread_message_digests(), (0, 0, 0))

        self.assertEqual(mail.outbox, [])
        self.assertFalse(ChatDigestState.objects.exists())
