"""The timed jobs the backend runs itself (apps.management.scheduler): their
slots, one process per slot, failures kept apart, and never in tests or
commands unless switched on."""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from apps.management import scheduler
from apps.management.models import ScheduledJobRun
from apps.users.models import AdminScope

User = get_user_model()
UTC = dt_timezone.utc
TEN = scheduler.Job("ten", "Every ten", 10, 3, "tests.apps.management.test_scheduler:_count")
DAILY = scheduler.Job("daily", "Daily", scheduler.DAY, 6 * 60 + 41, "tests.apps.management.test_scheduler:_count")
BROKEN = scheduler.Job("broken", "Broken", 10, 3, "tests.apps.management.test_scheduler:_fail")

CALLS = []


def _count():
    CALLS.append(1)


def _fail():
    raise RuntimeError("the mail server said no")


def at(hour, minute):
    return datetime(2026, 10, 22, hour, minute, 30, tzinfo=UTC)


class SlotTests(TestCase):
    def test_a_slot_starts_at_the_jobs_minute_in_each_period(self):
        self.assertEqual(scheduler.slot_for(TEN, at(9, 3)), datetime(2026, 10, 22, 9, 3, tzinfo=UTC))
        self.assertEqual(scheduler.slot_for(TEN, at(9, 12)), datetime(2026, 10, 22, 9, 3, tzinfo=UTC))
        self.assertEqual(scheduler.slot_for(TEN, at(9, 13)), datetime(2026, 10, 22, 9, 13, tzinfo=UTC))

    def test_a_daily_slot_is_that_time_each_day(self):
        self.assertEqual(scheduler.slot_for(DAILY, at(6, 40)), datetime(2026, 10, 21, 6, 41, tzinfo=UTC))
        self.assertEqual(scheduler.slot_for(DAILY, at(6, 41)), datetime(2026, 10, 22, 6, 41, tzinfo=UTC))
        self.assertEqual(scheduler.slot_for(DAILY, at(23, 0)), datetime(2026, 10, 22, 6, 41, tzinfo=UTC))


@patch.object(scheduler, "JOBS", (TEN, BROKEN, DAILY))
class TickTests(TestCase):
    def setUp(self):
        CALLS.clear()

    def test_a_job_first_runs_at_its_next_slot_not_when_first_seen(self):
        self.assertEqual(scheduler.tick(at(9, 5)), [])
        self.assertEqual(scheduler.tick(at(9, 13)), ["ten", "broken"])

    def test_each_slot_runs_once(self):
        scheduler.tick(at(9, 5))
        scheduler.tick(at(9, 13))
        self.assertEqual(scheduler.tick(at(9, 15)), [])
        self.assertEqual(len(CALLS), 1)

    def test_a_missed_slot_runs_at_the_next_tick(self):
        scheduler.tick(at(9, 5))
        # Asleep from 9:05 until 11:40: one run on waking, not one per slot missed.
        self.assertEqual(scheduler.tick(at(11, 40)), ["ten", "broken"])
        self.assertEqual(len(CALLS), 1)

    def test_one_failing_doesnt_stop_the_rest_and_is_noted(self):
        scheduler.tick(at(5, 0))
        ran = scheduler.tick(at(6, 45))

        self.assertEqual(ran, ["ten", "broken", "daily"])
        self.assertEqual(len(CALLS), 2)
        broken = ScheduledJobRun.objects.get(name="broken")
        self.assertIs(broken.last_ok, False)
        self.assertEqual(broken.last_error, "RuntimeError: the mail server said no")
        self.assertIs(ScheduledJobRun.objects.get(name="ten").last_ok, True)


class ClaimTests(TransactionTestCase):
    def test_only_one_process_claims_a_slot(self):
        slot = scheduler.slot_for(TEN, at(9, 13))
        scheduler.claim(TEN, scheduler.slot_for(TEN, at(9, 5)), at(9, 5))

        claims = [scheduler.claim(TEN, slot, at(9, 13)) for _process in range(3)]

        self.assertEqual(claims, [True, False, False])


class SwitchTests(TestCase):
    def setUp(self):
        scheduler._started = False
        self.addCleanup(setattr, scheduler, "_started", False)

    def test_off_by_default_so_nothing_starts(self):
        with patch.object(scheduler.threading, "Thread") as thread:
            self.client.get("/")
        thread.assert_not_called()

    @override_settings(SCHEDULER_ENABLED=True)
    def test_never_in_a_test_run_even_when_switched_on(self):
        with patch.object(scheduler.threading, "Thread") as thread:
            scheduler.ensure_started()
        thread.assert_not_called()

    @override_settings(SCHEDULER_ENABLED=True)
    def test_switched_on_a_web_process_starts_one_timer(self):
        with patch.object(scheduler.sys, "argv", ["gunicorn"]), patch.object(scheduler.threading, "Thread") as thread:
            scheduler.ensure_started()
            scheduler.ensure_started()
        thread.assert_called_once()


class StatusEndpointTests(TestCase):
    url = "/api/v1/admin/scheduled-jobs/"

    def test_admins_see_each_job_and_its_last_run(self):
        admin = User.objects.create_user(email="jobs.admin@example.com")
        AdminScope.objects.create(user=admin)
        ScheduledJobRun.objects.create(
            name="bounce_check", last_started_at=at(9, 13), last_finished_at=at(9, 13) + timedelta(seconds=2),
            last_ok=False, last_error="MailApiError: The Mail API answered 401.",
        )
        client = APIClient()
        client.force_authenticate(admin)

        data = client.get(self.url).json()["data"]

        self.assertIs(data["enabled"], False)
        self.assertEqual([job["name"] for job in data["jobs"]], [job.name for job in scheduler.JOBS])
        bounce = data["jobs"][0]
        self.assertEqual((bounce["every"], bounce["at"], bounce["ok"]), (10, 3, False))
        self.assertIn("401", bounce["error"])
        self.assertIsNone(data["jobs"][1]["lastStartedAt"])

    def test_others_dont(self):
        client = APIClient()
        client.force_authenticate(User.objects.create_user(email="not.admin@example.com"))
        self.assertEqual(client.get(self.url).status_code, 403)
