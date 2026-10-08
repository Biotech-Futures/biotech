"""Tests for the daily email asking students for their parent/guardian's details.

Pins who is emailed (this year's students with no guardian email whose account
can sign in and whose consent isn't recorded), that nobody is emailed twice in
a day, what the email says, and the scheduler's token check.
"""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.services.models import SystemEmailTemplate
from apps.services.system_email import FAILED
from apps.users.guardian_details import send_due
from apps.users.models import StudentProfile, User

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
FRONTEND = "https://connect.example.com"
TRIGGER = "/api/v1/admin/send-guardian-details-reminders/"


@override_settings(EMAIL_BACKEND=LOCMEM, FRONTEND_BASE_URL=FRONTEND)
class GuardianDetailsEmailTests(TestCase):
    def _student(self, email, *, pg_email=None, **user_fields):
        user = User.objects.create_user(
            email=email, password="x", first_name="Ana", last_name="Lee", **user_fields,
        )
        StudentProfile.objects.create(
            user=user,
            # No guardian known: the names hold the student's own, as registration leaves them.
            pg_first_name="Ana",
            pg_last_name="Lee",
            pg_email=pg_email,
            school_name="Test High",
            year_lvl="10",
        )
        return user

    def test_emails_a_student_with_no_guardian_email(self):
        self._student("ana@example.com")

        result = send_due()

        self.assertEqual(result, {"sent": 1, "failed": 0})
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["ana@example.com"])
        self.assertEqual(message.subject, "Information Required: Parent/Guardian Contact")
        html = message.alternatives[0][0]
        self.assertIn("Hi Ana", html)
        self.assertIn("Your parent/guardian information is required for", html)
        self.assertIn("without your parent/guardian contact information", html)
        self.assertIn("Provide parent/guardian details", html)
        self.assertIn(f"{FRONTEND}/#/profile?guardian=edit", html)
        self.assertIn("mailto:info@biotechfutures.org", html)

    def test_a_blank_guardian_email_counts_as_missing(self):
        self._student("ana@example.com", pg_email="")

        self.assertEqual(send_due()["sent"], 1)

    def test_emails_each_student_once_a_day(self):
        user = self._student("ana@example.com")

        send_due()
        self.assertEqual(send_due(), {"sent": 0, "failed": 0})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            StudentProfile.objects.get(user=user).guardian_details_reminded_on, timezone.localdate(),
        )

        # The next day they're emailed again.
        send_due(now=timezone.now() + timedelta(days=1))
        self.assertEqual(len(mail.outbox), 2)

    def test_stops_once_a_guardian_email_is_on_file(self):
        self._student("ana@example.com", pg_email="pat@example.com")

        self.assertEqual(send_due()["sent"], 0)
        self.assertEqual(mail.outbox, [])

    def test_skips_students_whose_consent_is_recorded(self):
        user = self._student("ana@example.com")
        StudentProfile.objects.filter(user=user).update(has_join_permission=True, parent_guardian_flag=True)

        self.assertEqual(send_due()["sent"], 0)

    def test_skips_accounts_that_cannot_sign_in(self):
        user = self._student("ana@example.com")
        user.deactivate()

        self.assertEqual(send_due()["sent"], 0)

    def test_skips_students_from_an_earlier_year(self):
        user = self._student("ana@example.com")
        User.objects.filter(pk=user.pk).update(date_joined=timezone.now() - timedelta(days=400))

        self.assertEqual(send_due()["sent"], 0)

    def test_switched_off_sends_and_records_nothing(self):
        user = self._student("ana@example.com")
        SystemEmailTemplate.objects.create(key="guardian_details_request", is_enabled=False)

        self.assertEqual(send_due(), {"sent": 0, "failed": 0, "disabled": True})
        self.assertEqual(mail.outbox, [])
        self.assertIsNone(StudentProfile.objects.get(user=user).guardian_details_reminded_on)

    def test_a_failed_send_is_tried_again_next_run(self):
        user = self._student("ana@example.com")

        with patch("apps.users.guardian_details.send_system_email", return_value=FAILED):
            self.assertEqual(send_due(), {"sent": 0, "failed": 1})
        self.assertIsNone(StudentProfile.objects.get(user=user).guardian_details_reminded_on)

        self.assertEqual(send_due()["sent"], 1)

    def test_dry_run_command_lists_and_sends_nothing(self):
        self._student("ana@example.com")
        out = StringIO()

        call_command("send_guardian_details_reminders", "--dry-run", stdout=out)

        self.assertIn("ana@example.com", out.getvalue())
        self.assertIn("1 student(s) would be emailed", out.getvalue())
        self.assertEqual(mail.outbox, [])


@override_settings(EMAIL_BACKEND=LOCMEM, FRONTEND_BASE_URL=FRONTEND)
class GuardianDetailsTriggerTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @override_settings(GUARDIAN_REMINDER_TOKEN="")
    def test_unconfigured_trigger_is_503(self):
        response = self.client.post(TRIGGER, HTTP_X_REMINDER_TOKEN="anything")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @override_settings(GUARDIAN_REMINDER_TOKEN="secret")
    def test_wrong_token_is_401(self):
        response = self.client.post(TRIGGER, HTTP_X_REMINDER_TOKEN="wrong")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(GUARDIAN_REMINDER_TOKEN="secret")
    def test_right_token_runs_the_emails(self):
        response = self.client.post(TRIGGER, HTTP_X_REMINDER_TOKEN="secret")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"sent": 0, "failed": 0})
