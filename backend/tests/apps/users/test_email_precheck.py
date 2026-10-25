"""Checking a registration's addresses before it's submitted
(apps.users.email_precheck): starting a check, its gate and limits, and
polling its progress. The lookups themselves are mocked; no test can reach
the network."""
import logging
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.users import email_precheck
from apps.users.email_verification import VerificationResult
from apps.users.models import EmailCheckJob, EmailVerification, SupervisorProfile
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch

START = "/api/v1/registration/email-check/"
STUDENT = "jordan.lee@example.com"
GUARDIAN = "guardian@example.com"


def status_url(job_id):
    return f"{START}{job_id}/"


@override_settings(
    EMAIL_PRECHECK_ENABLED=True, EMAIL_PRECHECK_MAX_ADDRESSES=2000, EMAIL_PRECHECK_ANONYMOUS_MAX_ADDRESSES=20,
    EMAIL_PRECHECK_IP_HOURLY_LOOKUPS=200, EMAIL_PRECHECK_STALL_SECONDS=60,
    EMAIL_PRECHECK_QUEUED_STALL_SECONDS=300, QEV_RESULT_MAX_AGE_DAYS=180,
    EMAIL_VERIFICATION_DISPATCH_SYNC=True,
)
class PrecheckTestCase(MultiStudentSetup, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        # No supervisor named, so these count the student's and guardian's
        # addresses alone (SupervisorTests check the named supervisor's).
        self.body["payload"].pop("supervisor", None)
        # The lookups are mocked: "bad..." addresses don't exist, "down..." can't be checked.
        self.checked = []
        verify = patch.object(email_precheck.email_verification, "verify_email", side_effect=self.fake_verify)
        verify.start()
        self.addCleanup(verify.stop)
        get = patch.object(requests, "get", side_effect=AssertionError("unexpected HTTP call"))
        get.start()
        self.addCleanup(get.stop)

    def fake_verify(self, address):
        self.checked.append(address)
        if address.startswith("bad"):
            return VerificationResult(address, "invalid", "rejected_email")
        if address.startswith("down"):
            return VerificationResult(address, "error", "request_timeout")
        return VerificationResult(address, "valid", "accepted_email")

    def start(self, body=None, *, client=None, run=True, **headers):
        with self.captureOnCommitCallbacks(execute=run):
            return (client or self.client).post(START, body or self.body, format="json", **headers)

    def poll(self, job_id):
        return self.client.get(status_url(job_id))

    @staticmethod
    def unsupervised(body):
        """``body`` without the supervisor its students named."""
        body["payload"].pop("supervisor", None)
        return body

    def supervisor_start(self, body, **kwargs):
        return self.start(body, client=self.supervisor_client, **kwargs)

    @contextmanager
    def captured_logs(self):
        records = []
        handler = logging.Handler(level=logging.DEBUG)
        handler.emit = records.append
        root = logging.getLogger()
        old = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        try:
            yield records
        finally:
            root.removeHandler(handler)
            root.setLevel(old)


class StartTests(PrecheckTestCase):
    def test_a_check_starts_and_reports_its_job(self):
        response = self.start(run=False)

        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(response.data["status"], "started")
        job = EmailCheckJob.objects.get(pk=response.data["jobId"])
        self.assertEqual((job.total, job.cached, job.done, job.status), (2, 0, 0, "queued"))
        self.assertEqual(self.checked, [], "nothing is checked until the job is saved")

    def test_once_saved_each_address_is_checked_and_counted(self):
        self.body["payload"]["students"][0]["email"] = "bad.jordan@example.com"

        job_id = self.start().data["jobId"]

        self.assertEqual(self.checked, ["bad.jordan@example.com", GUARDIAN])
        data = self.poll(job_id).data
        self.assertEqual(
            {key: data[key] for key in ("status", "total", "done", "invalid", "errors", "skipped")},
            {"status": "done", "total": 2, "done": 2, "invalid": 1, "errors": 0, "skipped": 0},
        )
        self.assertEqual(data["estimatedSecondsRemaining"], 0)

    def test_a_check_that_fails_counts_as_an_error(self):
        self.body["payload"]["students"][0]["guardian"]["email"] = "down.parent@example.com"

        data = self.poll(self.start().data["jobId"]).data

        self.assertEqual((data["status"], data["errors"]), ("done", 1))

    def test_addresses_answered_recently_arent_checked_again(self):
        EmailVerification.objects.create(email=STUDENT, status="invalid")

        response = self.start()

        self.assertEqual(self.checked, [GUARDIAN])
        job = EmailCheckJob.objects.get(pk=response.data["jobId"])
        self.assertEqual((job.cached, job.invalid, job.done), (1, 1, 2))

    @override_settings(QEV_UNKNOWN_MAX_AGE_HOURS=24)
    def test_an_unknown_answer_is_reused_within_its_window_and_checked_again_after(self):
        EmailVerification.objects.create(email=STUDENT, status="unknown", checked_at=timezone.now() - timedelta(hours=23))
        EmailVerification.objects.create(email=GUARDIAN, status="unknown", checked_at=timezone.now() - timedelta(hours=25))

        response = self.start()

        self.assertEqual(self.checked, [GUARDIAN])
        self.assertEqual(EmailCheckJob.objects.get(pk=response.data["jobId"]).cached, 1)

    def test_with_every_address_answered_already_it_is_done_at_once(self):
        EmailVerification.objects.create(email=STUDENT, status="valid")
        EmailVerification.objects.create(email=GUARDIAN, status="valid")

        response = self.start()

        self.assertEqual((response.status_code, response.data["status"]), (202, "done"))
        self.assertEqual(self.checked, [])

    def test_a_team_checks_each_address_once(self):
        body = batch("student_team", 3)
        body["payload"]["students"][1]["email"] = "learner1@students.example.test"

        response = self.start(body)

        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(self.checked, [
            "learner0@students.example.test", "parent0@guardians.example.test",
            "learner1@students.example.test", "learner2@students.example.test",
            # And the supervisor the team named, once.
            "teacher@example.com",
        ])

    def test_an_invalid_registration_is_refused_and_starts_nothing(self):
        self.body["payload"]["students"][0]["email"] = "not-an-email"

        response = self.start()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(EmailCheckJob.objects.exists())

    def test_old_jobs_are_deleted_when_a_new_one_starts(self):
        old = EmailCheckJob.objects.create(total=1)
        EmailCheckJob.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=2))
        recent = EmailCheckJob.objects.create(total=1)

        self.start()

        self.assertFalse(EmailCheckJob.objects.filter(pk=old.pk).exists())
        self.assertTrue(EmailCheckJob.objects.filter(pk=recent.pk).exists())

    def test_the_job_keeps_no_addresses_and_nothing_logged_names_one(self):
        with self.captured_logs() as records:
            job_id = self.start().data["jobId"]

        job = EmailCheckJob.objects.get(pk=job_id)
        stored = " ".join(str(value) for value in job.__dict__.values())
        logged = "\n".join(record.getMessage() for record in records)
        for address in (STUDENT, GUARDIAN):
            self.assertNotIn(address, stored)
            self.assertNotIn(address, logged)


class SwitchTests(PrecheckTestCase):
    @override_settings(EMAIL_PRECHECK_ENABLED=False)
    def test_with_the_switch_off_nothing_starts_and_polling_says_so(self):
        job = EmailCheckJob.objects.create(total=1)

        self.assertEqual(self.start().data, {"status": "disabled"})
        self.assertEqual(self.poll(job.pk).data, {"status": "disabled"})
        self.assertEqual(EmailCheckJob.objects.count(), 1)
        self.assertEqual(self.checked, [])


class GateTests(PrecheckTestCase):
    def test_closed_registration_checks_nothing(self):
        self.close_window()

        self.assertEqual(self.start().data, {"status": "closed"})
        self.assertFalse(EmailCheckJob.objects.exists())

    def test_a_valid_late_link_opens_it_without_using_the_link(self):
        self.close_window()
        invite = self.mint()

        response = self.start(HTTP_X_REGISTRATION_INVITATION=invite["token"])

        self.assertEqual(response.status_code, 202, response.data)
        self.assertIsNone(self.window.registrationinvitation_set.get().used_at)

    def test_a_bad_late_link_doesnt(self):
        self.close_window()

        self.assertEqual(self.start(HTTP_X_REGISTRATION_INVITATION="not-a-token").data, {"status": "closed"})

    def test_a_supervisor_allowed_after_close_can_check(self):
        self.close_window()
        SupervisorProfile.objects.filter(pk=self.profile.pk).update(register_after_close=True)

        self.assertEqual(self.supervisor_start(batch("supervisor_csv", 2)).status_code, 202)

    def test_a_supervisor_journey_needs_a_signed_in_supervisor(self):
        self.assertEqual(self.start(batch("supervisor_csv", 2)).status_code, 403)
        self.assertFalse(EmailCheckJob.objects.exists())


class LimitTests(PrecheckTestCase):
    @override_settings(EMAIL_PRECHECK_ANONYMOUS_MAX_ADDRESSES=3)
    def test_anyone_not_signed_in_may_send_only_a_few_addresses(self):
        self.assertEqual(self.start(batch("student_team", 4)).data, {"status": "too_many"})
        self.assertEqual(self.start().status_code, 202)

    @override_settings(EMAIL_PRECHECK_MAX_ADDRESSES=4)
    def test_signed_in_there_is_a_larger_limit(self):
        self.assertEqual(self.supervisor_start(batch("supervisor_csv", 4)).status_code, 202)
        self.assertEqual(self.supervisor_start(batch("supervisor_csv", 5, offset=10)).data, {"status": "too_many"})

    @override_settings(EMAIL_PRECHECK_IP_HOURLY_LOOKUPS=3)
    def test_over_the_hourly_budget_the_rest_are_left_unchecked(self):
        # A team of 4 and its creator's guardian: 5 addresses.
        response = self.start(self.unsupervised(batch("student_team", 4)))

        self.assertEqual(len(self.checked), 3)
        job = EmailCheckJob.objects.get(pk=response.data["jobId"])
        self.assertEqual((job.total, job.skipped, job.done, job.status), (5, 2, 5, "done"))

    @override_settings(EMAIL_PRECHECK_IP_HOURLY_LOOKUPS=3)
    def test_the_budget_is_per_ip_and_per_hour(self):
        self.start(self.unsupervised(batch("student_team", 2)))
        spent = self.start(self.unsupervised(batch("student_team", 1, offset=10)))
        other_ip = self.start(self.unsupervised(batch("student_team", 1, offset=20)), REMOTE_ADDR="198.51.100.7")

        self.assertEqual(spent.data["status"], "done")
        self.assertEqual(EmailCheckJob.objects.get(pk=spent.data["jobId"]).skipped, 2)
        self.assertEqual(other_ip.data["status"], "started")
        self.assertEqual(len(self.checked), 5)

    @override_settings(EMAIL_PRECHECK_IP_HOURLY_LOOKUPS=3)
    def test_a_signed_in_supervisor_isnt_held_to_the_ip_budget(self):
        supervised = self.supervisor_start(batch("supervisor_csv", 10))
        anonymous = self.start(self.unsupervised(batch("student_team", 4, offset=50)))

        self.assertEqual(EmailCheckJob.objects.get(pk=supervised.data["jobId"]).skipped, 0)
        self.assertEqual(EmailCheckJob.objects.get(pk=anonymous.data["jobId"]).skipped, 2)
        self.assertEqual(len(self.checked), 10 + 3)

    @override_settings(EMAIL_PRECHECK_MAX_ADDRESSES=4)
    def test_the_per_request_limit_still_applies_to_supervisors(self):
        self.assertEqual(self.supervisor_start(batch("supervisor_csv", 5)).data, {"status": "too_many"})

    @override_settings(EMAIL_PRECHECK_IP_HOURLY_LOOKUPS=1)
    def test_answers_on_file_dont_use_the_budget(self):
        EmailVerification.objects.create(email=STUDENT, status="valid")

        response = self.start()

        self.assertEqual(EmailCheckJob.objects.get(pk=response.data["jobId"]).skipped, 0)
        self.assertEqual(self.checked, [GUARDIAN])


class SupervisorTests(PrecheckTestCase):
    def test_the_supervisor_a_student_named_is_checked_too(self):
        self.body["payload"]["supervisor"] = {"firstName": "Sam", "lastName": "Teacher", "email": "teacher@example.com"}

        response = self.start()

        self.assertEqual(response.status_code, 202, response.data)
        self.assertEqual(self.checked, [STUDENT, GUARDIAN, "teacher@example.com"])

    def test_a_supervisor_registering_their_own_students_isnt_checked(self):
        response = self.supervisor_start(batch("supervisor_csv", 2))

        self.assertEqual(response.status_code, 202, response.data)
        self.assertNotIn(self.supervisor.email, self.checked)


class PollTests(PrecheckTestCase):
    def test_an_unknown_job_is_not_found(self):
        response = self.poll("3f6c2a54-7e0b-4f59-9d1e-0c1b2a3d4e5f")

        self.assertEqual((response.status_code, response.data), (404, {"status": "not_found"}))

    def idle_job(self, status, seconds):
        job = EmailCheckJob.objects.create(total=10, done=3, status=status)
        EmailCheckJob.objects.filter(pk=job.pk).update(updated_at=timezone.now() - timedelta(seconds=seconds))
        data = self.poll(job.pk).data
        return data["status"], data["estimatedSecondsRemaining"]

    def test_a_running_job_that_stops_moving_is_reported_stalled(self):
        self.assertEqual(self.idle_job("running", 61), ("stalled", None))

    def test_a_job_moving_recently_is_still_running_with_an_estimate(self):
        status, estimate = self.idle_job("running", 5)

        self.assertEqual(status, "running")
        self.assertIsNotNone(estimate)

    def test_a_queued_job_is_reported_queued_without_an_estimate(self):
        self.assertEqual(self.idle_job("queued", 5), ("queued", None))

    def test_a_queued_job_may_wait_longer_than_a_running_one(self):
        self.assertEqual(self.idle_job("queued", 299), ("queued", None))

    def test_a_queued_job_never_started_is_reported_stalled_after_its_own_limit(self):
        self.assertEqual(self.idle_job("queued", 301), ("stalled", None))

    @override_settings(EMAIL_PRECHECK_QUEUED_STALL_SECONDS=30)
    def test_the_queued_limit_comes_from_the_setting(self):
        self.assertEqual(self.idle_job("queued", 31), ("stalled", None))

    def test_a_finished_job_is_never_stalled(self):
        self.assertEqual(self.idle_job("done", 3600), ("done", 0))

    def test_checks_that_crash_count_as_errors_and_the_job_still_finishes(self):
        with patch.object(email_precheck.email_verification, "verify_email", side_effect=RuntimeError("boom")):
            job_id = self.start().data["jobId"]

        data = self.poll(job_id).data
        self.assertEqual((data["status"], data["done"], data["errors"]), ("done", 2, 2))

    def test_a_job_that_cant_be_handed_to_the_workers_is_marked_failed(self):
        with override_settings(EMAIL_VERIFICATION_DISPATCH_SYNC=False), \
                patch.object(email_precheck, "_pool", side_effect=RuntimeError("shutting down")):
            job_id = self.start().data["jobId"]

        self.assertEqual(self.poll(job_id).data["status"], "failed")
