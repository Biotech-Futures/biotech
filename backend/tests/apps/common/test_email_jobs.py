"""The scheduled email jobs share one token, sent in the X-Email-Jobs-Token
header: it opens every job's endpoint, and nothing else does. While the jobs
move from RSVP_REMINDER_TOKEN to EMAIL_JOBS_TOKEN, either is accepted. With
neither set, every job answers 503 rather than standing open."""
from contextlib import ExitStack
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework import status

JOBS = (
    "/api/v1/events/admin/send-rsvp-reminders/",
    "/events/v1/admin/send-rsvp-reminders/",
    "/api/v1/submissions/admin/send-reminders/",
    "/api/v1/chat/admin/send-unread-digest/",
    "/api/v1/admin/send-guardian-details-reminders/",
    "/api/v1/admin/send-guardian-consent-reminders/",
)


@override_settings(EMAIL_JOBS_TOKEN="one-token")
class EmailJobsTokenTests(TestCase):
    def setUp(self):
        # Nobody is emailed: each job's own work is stood in for.
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("apps.events.views.send_due_rsvp_reminders", return_value=(0, 0, 0)))
        stack.enter_context(patch("apps.submissions.views.send_due_reminders", return_value={}))
        stack.enter_context(patch("apps.chat.services.digest.dispatch_unread_digest", return_value="started"))
        stack.enter_context(patch("apps.users.guardian_details.send_due", return_value={}))
        stack.enter_context(patch("apps.users.guardian_reminders.send_due", return_value={}))

    def test_the_one_token_runs_every_job(self):
        for url in JOBS:
            with self.subTest(url):
                response = self.client.post(url, HTTP_X_EMAIL_JOBS_TOKEN="one-token")
                self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_202_ACCEPTED))

    def test_a_wrong_token_or_an_old_header_runs_none(self):
        for url in JOBS:
            with self.subTest(url):
                self.assertEqual(
                    self.client.post(url, HTTP_X_EMAIL_JOBS_TOKEN="wrong").status_code, status.HTTP_401_UNAUTHORIZED,
                )
                for old in ("HTTP_X_REMINDER_TOKEN", "HTTP_X_DIGEST_TOKEN"):
                    self.assertEqual(
                        self.client.post(url, **{old: "one-token"}).status_code, status.HTTP_401_UNAUTHORIZED,
                    )

    @override_settings(EMAIL_JOBS_TOKEN="", RSVP_REMINDER_TOKEN="old-token")
    def test_the_old_token_still_runs_every_job_while_the_new_one_is_unset(self):
        for url in JOBS:
            with self.subTest(url):
                response = self.client.post(url, HTTP_X_EMAIL_JOBS_TOKEN="old-token")
                self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_202_ACCEPTED))

    @override_settings(RSVP_REMINDER_TOKEN="old-token")
    def test_with_both_set_either_token_runs_the_jobs(self):
        for token in ("one-token", "old-token"):
            with self.subTest(token):
                response = self.client.post(JOBS[0], HTTP_X_EMAIL_JOBS_TOKEN=token)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.post(JOBS[0], HTTP_X_EMAIL_JOBS_TOKEN="wrong").status_code, status.HTTP_401_UNAUTHORIZED,
        )

    @override_settings(EMAIL_JOBS_TOKEN="", RSVP_REMINDER_TOKEN="")
    def test_with_no_token_set_every_job_refuses(self):
        for url in JOBS:
            with self.subTest(url):
                response = self.client.post(url, HTTP_X_EMAIL_JOBS_TOKEN="")
                self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
