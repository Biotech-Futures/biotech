"""The workers that check a pre-submission job's addresses
(apps.users.email_precheck): the bounded pool, the guard against paying
twice for one address, backing off when QEV answers 429, and the estimate.

The real verification client runs with every request mocked and a dummy
key; any request a test hasn't set up fails it. Waiting is never real."""
import time
from unittest import mock

from django.core.cache import cache
from django.test import override_settings

from apps.users import email_precheck as precheck
from apps.users.models import EmailCheckJob, EmailVerification

from .test_email_verification import KEY, QevTestCase, qev, response

ADDRESS = "kid@example.com"


@override_settings(QEV_DAILY_LOOKUP_CAP=0, QEV_PRECHECK_WORKERS=16, EMAIL_VERIFICATION_DISPATCH_SYNC=True)
class RunnerTestCase(QevTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        sleep = mock.patch.object(precheck, "_sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def job(self, total=1, **fields):
        return EmailCheckJob.objects.create(total=total, **fields)

    def reload(self, job):
        job.refresh_from_db()
        return job


class PoolTests(RunnerTestCase):
    def setUp(self):
        super().setUp()
        self._old, precheck._executor = precheck._executor, None

        def restore():
            if precheck._executor is not None:
                precheck._executor.shutdown(wait=False)
            precheck._executor = self._old

        self.addCleanup(restore)

    def test_the_pool_has_the_set_number_of_workers(self):
        self.assertEqual(precheck._pool()._max_workers, 16)

    @override_settings(QEV_PRECHECK_WORKERS=3)
    def test_the_number_comes_from_the_setting(self):
        self.assertEqual(precheck._pool()._max_workers, 3)

    def test_the_pool_is_made_once(self):
        self.assertIs(precheck._pool(), precheck._pool())

    @override_settings(EMAIL_VERIFICATION_DISPATCH_SYNC=False)
    def test_each_address_is_its_own_task_on_the_pool(self):
        pool = mock.Mock()
        with mock.patch.object(precheck, "_pool", return_value=pool):
            precheck._dispatch("job-id", ["a@example.com", "b@example.com"])

        self.assertEqual(pool.submit.call_args_list, [
            mock.call(precheck._check_in_pool, "job-id", "a@example.com"),
            mock.call(precheck._check_in_pool, "job-id", "b@example.com"),
        ])

    def test_a_pool_task_closes_its_database_connection(self):
        job = self.job()
        self.answer(response())

        with mock.patch.object(precheck.connections, "close_all") as close_all:
            precheck._check_in_pool(job.pk, ADDRESS)

        close_all.assert_called_once_with()


class JobTests(RunnerTestCase):
    def test_a_job_runs_then_finishes_with_its_counts_and_timings(self):
        job = self.job(total=2)
        self.answer(response(), response(qev("invalid", "rejected_email")))

        with mock.patch.object(precheck, "_clock", side_effect=[0, 1.5, 10, 12.5]):
            precheck.check_address(job.pk, "a@example.com")
            self.assertEqual(self.reload(job).status, "running")
            precheck.check_address(job.pk, "b@example.com")

        job = self.reload(job)
        self.assertEqual(
            (job.status, job.done, job.invalid, job.errors, job.lookups, job.lookup_seconds),
            ("done", 2, 1, 0, 2, 4.0),
        )

    def test_an_answer_reused_from_file_isnt_timed_as_a_lookup(self):
        EmailVerification.objects.create(email=ADDRESS, status="valid")
        job = self.job()

        precheck.check_address(job.pk, ADDRESS)

        job = self.reload(job)
        self.assertEqual((job.done, job.lookups), (1, 0))
        self.http.assert_not_called()

    def test_a_check_that_crashes_counts_as_an_error_and_the_job_finishes(self):
        job = self.job()

        with mock.patch.object(precheck.email_verification, "verify_email", side_effect=RuntimeError("boom")):
            precheck.check_address(job.pk, ADDRESS)

        job = self.reload(job)
        self.assertEqual((job.status, job.done, job.errors), ("done", 1, 1))


class GuardTests(RunnerTestCase):
    def hold(self, address=ADDRESS):
        """Another worker is checking ``address``."""
        cache.add(precheck._busy_key(address), 1, precheck.BUSY_SECONDS)

    def test_the_guard_key_doesnt_contain_the_address(self):
        self.assertNotIn(ADDRESS, precheck._busy_key(ADDRESS))

    def test_an_address_another_worker_is_checking_is_waited_for_not_paid_for_twice(self):
        self.hold()

        def other_worker_finishes(seconds):
            EmailVerification.objects.create(email=ADDRESS, status="invalid", reason="rejected_email")

        self.sleep.side_effect = other_worker_finishes
        result = precheck._guarded_verify(ADDRESS)

        self.assertEqual((result.status, result.cached), ("invalid", True))
        self.http.assert_not_called()
        self.sleep.assert_called_once_with(precheck.WAIT_STEP_SECONDS)

    def test_if_the_other_worker_lets_go_without_an_answer_it_is_checked_here(self):
        self.hold()
        self.sleep.side_effect = lambda seconds: cache.delete(precheck._busy_key(ADDRESS))
        self.answer(response())

        self.assertEqual(precheck._guarded_verify(ADDRESS).status, "valid")
        self.assertEqual(self.http.call_count, 1)

    def test_after_waiting_long_enough_it_is_checked_here(self):
        self.hold()
        self.answer(response())

        self.assertEqual(precheck._guarded_verify(ADDRESS).status, "valid")
        self.assertEqual(self.sleep.call_count, int(precheck.BUSY_WAIT_SECONDS / precheck.WAIT_STEP_SECONDS))

    def test_the_address_is_let_go_after_its_check(self):
        self.answer(response())

        precheck._guarded_verify(ADDRESS)

        self.assertIsNone(cache.get(precheck._busy_key(ADDRESS)))

    def test_the_address_is_let_go_even_if_its_check_crashes(self):
        with mock.patch.object(precheck.email_verification, "verify_email", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                precheck._guarded_verify(ADDRESS)

        self.assertIsNone(cache.get(precheck._busy_key(ADDRESS)))


class RateLimitTests(RunnerTestCase):
    def test_a_429_pauses_every_worker_then_the_address_is_tried_again(self):
        self.answer(response(status=429), response())

        result = precheck._verify(ADDRESS)

        self.assertEqual(result.status, "valid")
        self.assertEqual(self.http.call_count, 2)
        self.assertGreater(float(cache.get(precheck.PAUSE_KEY)), time.time())
        self.sleep.assert_called_once()
        self.assertAlmostEqual(self.sleep.call_args.args[0], 1, delta=0.5)

    def test_the_pause_grows_each_time_then_the_address_counts_as_not_checked(self):
        self.answer(*[response(status=429)] * 6)

        with mock.patch.object(precheck, "_pause_everyone", wraps=precheck._pause_everyone) as pause:
            result = precheck._verify(ADDRESS)

        self.assertEqual((result.status, result.reason), ("error", "http_429"))
        self.assertEqual(self.http.call_count, 6)
        self.assertEqual([call.args[0] for call in pause.call_args_list], [1, 2, 4, 8, 16])

    def test_a_pause_set_by_another_worker_is_waited_out_before_a_lookup(self):
        cache.set(precheck.PAUSE_KEY, time.time() + 5, 10)
        self.answer(response())

        precheck._verify(ADDRESS)

        self.assertAlmostEqual(self.sleep.call_args.args[0], 5, delta=0.5)

    def test_a_pause_is_never_waited_for_more_than_30_seconds(self):
        cache.set(precheck.PAUSE_KEY, time.time() + 600, 700)
        self.answer(response())

        precheck._verify(ADDRESS)

        self.assertLessEqual(self.sleep.call_args.args[0], 30)

    def test_a_shorter_pause_never_cuts_a_longer_one_short(self):
        later = time.time() + 20
        cache.set(precheck.PAUSE_KEY, later, 30)

        precheck._pause_everyone(1)

        self.assertEqual(float(cache.get(precheck.PAUSE_KEY)), later)

    def test_other_failures_arent_retried(self):
        self.answer(response(status=500))

        self.assertEqual(precheck._verify(ADDRESS).reason, "http_500")
        self.assertEqual(self.http.call_count, 1)
        self.sleep.assert_not_called()


class EstimateTests(RunnerTestCase):
    def test_before_any_lookup_it_assumes_the_default_time(self):
        job = self.job(total=100, done=20)

        self.assertEqual(precheck.estimate_seconds(job), 80 * 2.0 / 16)

    def test_it_uses_the_jobs_average_lookup_time(self):
        job = self.job(total=100, done=20, lookups=10, lookup_seconds=30.0)

        self.assertEqual(precheck.estimate_seconds(job), 15)

    def test_fewer_left_than_workers_run_side_by_side(self):
        job = self.job(total=100, done=98, lookups=10, lookup_seconds=30.0)

        self.assertEqual(precheck.estimate_seconds(job), 3)

    @override_settings(QEV_PRECHECK_WORKERS=4)
    def test_the_worker_count_comes_from_the_setting(self):
        job = self.job(total=100, done=20, lookups=10, lookup_seconds=30.0)

        self.assertEqual(precheck.estimate_seconds(job), 60)

    def test_it_rounds_up_to_whole_seconds(self):
        # 50 left x 10/3 seconds each / 16 workers = 10.4.
        job = self.job(total=50, done=0, lookups=3, lookup_seconds=10.0)

        self.assertEqual(precheck.estimate_seconds(job), 11)

    def test_a_finished_job_has_nothing_left(self):
        self.assertEqual(precheck.estimate_seconds(self.job(total=5, done=5, status="done")), 0)


class SecretTests(RunnerTestCase):
    def test_no_key_or_address_is_logged_while_a_job_runs(self):
        job = self.job(total=2)
        self.answer(response(status=429), response(), response(qev("invalid", "rejected_email")))

        with self.captured_logs() as records:
            precheck.check_address(job.pk, ADDRESS)
            precheck.check_address(job.pk, "pat@example.com")

        self.assertTrue(records)
        self.assertNothingSecretIn(records, ADDRESS, "pat@example.com")
        self.assertNotIn(KEY, " ".join(str(value) for value in self.reload(job).__dict__.values()))
