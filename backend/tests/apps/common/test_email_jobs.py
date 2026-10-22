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
        # Nobody is emailed: each job queues its run, and the queue is stood in for.
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.queue_job = stack.enter_context(patch("apps.management.services.send_guard.queue_job"))

    def test_the_one_token_runs_every_job(self):
        for url in JOBS:
            with self.subTest(url):
                response = self.client.post(url, HTTP_X_EMAIL_JOBS_TOKEN="one-token")
                self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
                self.assertEqual(response.data["status"], "queued")

    def test_each_job_queues_its_run_to_send_in_its_turn(self):
        for url in JOBS:
            self.client.post(url, HTTP_X_EMAIL_JOBS_TOKEN="one-token")
        self.assertEqual(
            [call.args[0] for call in self.queue_job.call_args_list],
            [
                "rsvp_reminder",
                "rsvp_reminder",
                # The submissions call runs the finalists' reminders as well as the entry's.
                "finalist_submission_reminder",
                "submission_reminder",
                "unread_messages",
                "guardian_details_request",
                "guardian_consent_request",
            ],
        )

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
                self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    @override_settings(RSVP_REMINDER_TOKEN="old-token")
    def test_with_both_set_either_token_runs_the_jobs(self):
        for token in ("one-token", "old-token"):
            with self.subTest(token):
                response = self.client.post(JOBS[0], HTTP_X_EMAIL_JOBS_TOKEN=token)
                self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            self.client.post(JOBS[0], HTTP_X_EMAIL_JOBS_TOKEN="wrong").status_code, status.HTTP_401_UNAUTHORIZED,
        )

    @override_settings(EMAIL_JOBS_TOKEN="", RSVP_REMINDER_TOKEN="")
    def test_with_no_token_set_every_job_refuses(self):
        for url in JOBS:
            with self.subTest(url):
                response = self.client.post(url, HTTP_X_EMAIL_JOBS_TOKEN="")
                self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
