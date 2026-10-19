"""Tests for the Log on System Emails.

Pins what a send notes (when, who sent it, and who it couldn't reach and
why), that a background send notes itself too, that a failed guardian
consent request is still noted after its rollback, that only the latest
sends that missed someone are kept, and how the Log names people: by group,
as a guardian of their student, or by address alone. A Management bulk email
shows its last run instead; a queued job (an announcement, a reminder) keeps
only counts in its run, so it shows its own log like the rest.
"""
import smtplib
from datetime import timedelta
from unittest.mock import patch

from django.core.mail import EmailMultiAlternatives
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin.services.guardian_consent import SEND_FAILED, send_guardian_consent_request
from apps.groups.models import GroupMembership, Groups
from apps.management.models import EmailSendRun
from apps.services.email_log import (
    MISSED_KEPT, NOT_SENT, email_log, mark_failures_seen, note_send, unseen_failures,
)
from apps.services.email_registry import EMAIL_TYPES
from apps.services.models import EmailDeliveryMetric, SystemEmailLog, SystemEmailSettings
from apps.services.system_email import FAILED, SENT, send_system_email, sender_for
from apps.submissions.emails import send_messages
from apps.users.models import GuardianConsentRequest, StudentProfile, User
from apps.users.models.admin_scope import AdminScope

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def _refused(address):
    return smtplib.SMTPRecipientsRefused({address: (550, b"no such mailbox")})


def _entry(key):
    return next(email for email in email_log() if email["key"] == key)


@override_settings(EMAIL_BACKEND=LOCMEM, FRONTEND_BASE_URL="https://connect.example.com")
class EmailLogTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="x", first_name="Ada", last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin)
        self.jin = User.objects.create_user(
            email="jin@example.com", password="x", first_name="Jin", last_name="Fischer",
        )
        self.btf06 = Groups.objects.create(group_name="BTF06")
        GroupMembership.objects.create(
            user=self.jin, group=self.btf06, membership_role="student",
            joined_at=timezone.now() - timedelta(days=30),
        )
        self.profile = StudentProfile.objects.create(
            user=self.jin, pg_first_name="Pat", pg_last_name="Parent", pg_email="pat@example.com",
            parent_guardian_flag=True, school_name="Test High", year_lvl="10",
        )

    # -- what a send notes ---------------------------------------------------------

    def test_a_send_notes_when_it_went_and_who_sent_it(self):
        outcome = send_system_email("password_changed", ["jin@example.com"], {}, sent_by=self.admin)

        self.assertEqual(outcome, SENT)
        log = SystemEmailLog.objects.get(key="password_changed")
        self.assertIsNotNone(log.last_sent_at)
        self.assertEqual(log.last_sent_by, self.admin)
        self.assertEqual(log.missed, [])
        metric = EmailDeliveryMetric.objects.get(email_type="password_changed")
        self.assertEqual(metric.source_mailbox, "info@biotechfutures.org")
        self.assertEqual(metric.attempted_count, 1)
        self.assertEqual(metric.delivered_count, 1)
        self.assertEqual(metric.failed_count, 0)
        self.assertEqual(metric.status, EmailDeliveryMetric.Status.SUCCESS)
        self.assertEqual(metric.initiated_by, self.admin)

    def test_a_refused_address_is_noted_with_its_reason(self):
        with patch.object(EmailMultiAlternatives, "send", side_effect=_refused("jin@example.com")):
            outcome = send_system_email("password_changed", ["jin@example.com"], {})

        self.assertEqual(outcome, FAILED)
        log = SystemEmailLog.objects.get(key="password_changed")
        self.assertIsNone(log.last_sent_by)
        self.assertEqual(log.missed[0]["missed"], [{"address": "jin@example.com", "reason": "address refused"}])
        metric = EmailDeliveryMetric.objects.get(email_type="password_changed")
        self.assertEqual(metric.attempted_count, 1)
        self.assertEqual(metric.delivered_count, 0)
        self.assertEqual(metric.failed_count, 1)
        self.assertEqual(metric.status, EmailDeliveryMetric.Status.FAILED)

    def test_a_background_send_notes_itself_once_it_has_gone_or_not(self):
        # The test settings send the mail pool's work straight away.
        with patch.object(EmailMultiAlternatives, "send", side_effect=ConnectionResetError()):
            send_system_email("login_code", ["jin@example.com"], {}, background=True)

        missed = SystemEmailLog.objects.get(key="login_code").missed
        self.assertEqual(missed[0]["missed"], [{"address": "jin@example.com", "reason": "lost the mail server connection"}])

    def test_a_failed_consent_request_is_noted_after_its_rollback(self):
        with patch.object(EmailMultiAlternatives, "send", side_effect=_refused("pat@example.com")):
            result = send_guardian_consent_request(self.jin.id, initiated_by=self.admin)

        self.assertEqual(result["status"], SEND_FAILED)
        self.assertFalse(GuardianConsentRequest.objects.exists())
        log = SystemEmailLog.objects.get(key="guardian_consent_request")
        self.assertEqual(log.last_sent_by, self.admin)
        self.assertEqual(log.missed[0]["missed"], [{"address": "pat@example.com", "reason": NOT_SENT}])

    def test_a_batch_notes_only_the_messages_that_failed(self):
        sender = sender_for("submission_reminder")
        good = EmailMultiAlternatives("Hi", "Hi", to=["jin@example.com"])
        bad = EmailMultiAlternatives("Hi", "Hi", to=["gone@example.com"], cc=["cc@example.com"])
        with patch.object(bad, "send", side_effect=_refused("gone@example.com")):
            self.assertEqual(send_messages([good, bad], kind="submission_reminder", sender=sender), (1, 1))

        self.assertEqual(
            SystemEmailLog.objects.get(key="submission_reminder").missed[0]["missed"],
            [
                {"address": "gone@example.com", "reason": "address refused"},
                {"address": "cc@example.com", "reason": "address refused"},
            ],
        )
        metric = EmailDeliveryMetric.objects.get(email_type="submission_reminder")
        self.assertEqual(metric.source_mailbox, sender.address)
        self.assertEqual(metric.attempted_count, 3)
        self.assertEqual(metric.delivered_count, 1)
        self.assertEqual(metric.failed_count, 2)
        self.assertEqual(metric.status, EmailDeliveryMetric.Status.PARTIAL)

    def test_metric_normalises_a_display_name_to_its_mailbox(self):
        note_send(
            "unread_messages",
            attempted=2,
            delivered=2,
            failed=0,
            source_mailbox="BIOTech Connect <CONNECT@biotechfutures.org>",
        )

        metric = EmailDeliveryMetric.objects.get(email_type="unread_messages")
        self.assertEqual(metric.source_mailbox, "connect@biotechfutures.org")

    def test_only_the_latest_sends_that_missed_someone_are_kept(self):
        for n in range(MISSED_KEPT + 5):
            note_send("password_reset", missed={f"p{n}@example.com": "address refused"})

        missed = SystemEmailLog.objects.get(key="password_reset").missed
        self.assertEqual(len(missed), MISSED_KEPT)
        self.assertEqual(missed[0]["missed"][0]["address"], f"p{MISSED_KEPT + 4}@example.com")

    # -- what the Log shows ----------------------------------------------------------

    def test_every_email_is_listed_in_order_with_where_bounces_go(self):
        emails = email_log()

        self.assertEqual([email["key"] for email in emails], [email_type.key for email_type in EMAIL_TYPES])
        reset = _entry("password_reset")
        self.assertIsNone(reset["lastSentAt"])
        self.assertEqual(reset["missed"], [])
        self.assertEqual(reset["sentFrom"], sender_for("password_reset").address)
        self.assertFalse(reset["toGroups"])
        self.assertTrue(_entry("finalist_notification")["toGroups"])

    def test_people_are_named_by_group_guardians_by_their_student(self):
        note_send(
            "guardian_consent_request",
            missed={"jin@example.com": "address refused", "PAT@example.com": "address refused",
                    "nobody@example.com": "address refused"},
            by=self.admin,
        )

        entry = _entry("guardian_consent_request")
        self.assertEqual(entry["lastSentBy"], "Ada Admin")
        self.assertEqual(
            [person["who"] for person in entry["missed"][0]["people"]],
            [
                "jin@example.com (BTF06, Jin Fischer)",
                "PAT@example.com (BTF06, guardian of Jin Fischer)",
                "nobody@example.com",
            ],
        )

    def test_a_bulk_email_shows_its_last_run(self):
        started = timezone.now() - timedelta(hours=1)
        missed = {"who": "jin@example.com (BTF06, Jin Fischer)", "reason": "couldn't reach the mail server"}
        EmailSendRun.objects.create(
            key="finalist_notification", started_at=started, started_by=self.admin, missed=[missed],
        )

        entry = _entry("finalist_notification")
        self.assertEqual(entry["lastSentAt"], started.isoformat())
        self.assertEqual(entry["lastSentBy"], "Ada Admin")
        self.assertEqual(entry["missed"], [{"at": started.isoformat(), "people": [missed]}])

    def test_a_queued_email_shows_who_its_sends_missed_not_its_run(self):
        # An announcement goes as a queued job, whose run keeps only counts.
        EmailSendRun.objects.create(
            key="announcement", started_at=timezone.now() - timedelta(hours=1), started_by=self.admin, failed=1,
        )
        note_send("announcement", missed={"jin@example.com": "lost the mail server connection"}, by=self.admin)

        entry = _entry("announcement")
        log = SystemEmailLog.objects.get(key="announcement")
        # When its send finished, and who sent it; who it missed, and why.
        self.assertEqual((entry["lastSentAt"], entry["lastSentBy"]), (log.last_sent_at.isoformat(), "Ada Admin"))
        self.assertEqual(
            entry["missed"][0]["people"],
            [{"who": "jin@example.com (BTF06, Jin Fischer)", "reason": "lost the mail server connection"}],
        )

    def test_a_queued_email_whose_run_emailed_nobody_is_not_emailed_yet(self):
        EmailSendRun.objects.create(key="rsvp_reminder", started_at=timezone.now())

        entry = _entry("rsvp_reminder")
        self.assertEqual((entry["lastSentAt"], entry["missed"]), (None, []))

    def test_admins_read_the_log_and_nobody_else_does(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get("/api/v1/admin/email-log/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["data"]), len(EMAIL_TYPES))

        client.force_authenticate(self.jin)
        self.assertEqual(client.get("/api/v1/admin/email-log/").status_code, status.HTTP_403_FORBIDDEN)

    # -- the count on the Failed Sending Emails button ------------------------------

    def test_every_failure_is_unseen_until_someone_looks(self):
        note_send("password_reset", missed={"a@example.com": "address refused", "b@example.com": "address refused"})
        EmailSendRun.objects.create(
            key="finalist_notification", started_at=timezone.now(),
            missed=[{"who": "jin@example.com (BTF06, Jin Fischer)", "reason": "couldn't reach the mail server"}],
        )
        self.assertEqual(unseen_failures(), 3)

        self.assertEqual(mark_failures_seen(), 0)
        self.assertEqual(unseen_failures(), 0)

    def test_only_failures_after_the_last_look_count(self):
        # Set times: two calls can land on the same clock tick.
        note_send("password_reset", missed={"old@example.com": "address refused"})
        log = SystemEmailLog.objects.get(key="password_reset")
        log.missed[0]["at"] = (timezone.now() - timedelta(hours=1)).isoformat()
        log.save()
        SystemEmailSettings.get()
        SystemEmailSettings.objects.update(failures_seen_at=timezone.now() - timedelta(minutes=30))
        note_send("announcement", missed={"new@example.com": "address refused"})

        self.assertEqual(unseen_failures(), 1)

    def test_looking_leaves_the_switch_last_changed_time_alone(self):
        updated = SystemEmailSettings.get().updated_at
        mark_failures_seen()
        self.assertEqual(SystemEmailSettings.get().updated_at, updated)

    def test_admins_read_and_clear_the_count(self):
        note_send("password_reset", missed={"a@example.com": "address refused"})
        client = APIClient()
        client.force_authenticate(self.admin)
        self.assertEqual(client.get("/api/v1/admin/email-log/unseen/").json()["data"], {"unseen": 1})
        self.assertEqual(client.post("/api/v1/admin/email-log/unseen/").json()["data"], {"unseen": 0})
        self.assertEqual(client.get("/api/v1/admin/email-log/unseen/").json()["data"], {"unseen": 0})

        client.force_authenticate(self.jin)
        self.assertEqual(client.post("/api/v1/admin/email-log/unseen/").status_code, status.HTTP_403_FORBIDDEN)
