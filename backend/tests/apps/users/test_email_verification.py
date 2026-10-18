"""Checking addresses with QuickEmailVerification (apps.users.email_verification).

All HTTP is mocked: any request a test hasn't set up fails it, and the key is
the dummy one from the test settings, so no test can spend real credits.
"""
import logging
from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

import requests
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.users import email_verification as ev
from apps.users.models import EmailVerification, EmailVerificationCredits

KEY = "test-dummy-key"


def qev(result="valid", reason="accepted_email", **fields):
    """A QEV answer, with its flags as the strings QEV sends."""
    return {
        "result": result, "reason": reason, "disposable": "false", "accept_all": "false",
        "role": "false", "free": "false", "email": "", "user": "", "domain": "",
        "mx_record": "", "mx_domain": "", "safe_to_send": "true", "did_you_mean": "",
        "success": "true", "message": "", **fields,
    }


def response(body=None, *, status=200, bad_json=False, headers=None):
    answer = mock.Mock(spec=requests.Response)
    answer.status_code = status
    answer.headers = headers or {}
    if bad_json:
        answer.json.side_effect = requests.JSONDecodeError("Expecting value", "<html>", 0)
    else:
        answer.json.return_value = qev() if body is None else body
    return answer


# Only the free key, unless a test says otherwise (two-key behaviour is in
# test_email_verification_keys).
@override_settings(
    QEV_API_KEY=KEY, QEV_PAID_API_KEY="", QEV_USE_SANDBOX=False, QEV_TIMEOUT_SECONDS=5, QEV_RESULT_MAX_AGE_DAYS=180,
    QEV_DAILY_LOOKUP_CAP=600, EMAIL_VERIFICATION_DISPATCH_SYNC=True,
)
class QevTestCase(TestCase):
    def setUp(self):
        get = mock.patch.object(ev.requests, "get", side_effect=AssertionError("unexpected HTTP call"))
        self.http = get.start()
        self.addCleanup(get.stop)
        # Any other real request (a different library call) fails too.
        send = mock.patch.object(requests.Session, "send", side_effect=AssertionError("real network call"))
        send.start()
        self.addCleanup(send.stop)

    def answer(self, *answers):
        """QEV answers these, in turn, to the next calls."""
        self.http.side_effect = list(answers)

    def answer_always(self, body=None, **kwargs):
        self.http.side_effect = None
        self.http.return_value = response(body, **kwargs)

    @contextmanager
    def captured_logs(self):
        """Every log record from any logger, DEBUG and up."""
        records = []
        handler = logging.Handler(level=logging.DEBUG)
        handler.emit = records.append
        root = logging.getLogger()
        old_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        try:
            yield records
        finally:
            root.removeHandler(handler)
            root.setLevel(old_level)

    def assertNothingSecretIn(self, records, *addresses):
        text = "\n".join(record.getMessage() for record in records)
        self.assertNotIn(KEY, text)
        for address in addresses:
            self.assertNotIn(address, text)

    def stored(self, email):
        return EmailVerification.objects.get(email=email)


class AnswerTests(QevTestCase):
    def test_a_valid_address_is_valid_and_stored(self):
        self.answer(response(qev(free="true", did_you_mean="")))

        result = ev.verify_email("Kid@Example.com")

        self.assertEqual((result.email, result.status, result.reason), ("kid@example.com", "valid", "accepted_email"))
        self.assertTrue(result.passed)
        self.assertFalse(result.cached)
        row = self.stored("kid@example.com")
        self.assertEqual((row.status, row.reason, row.free, row.safe_to_send), ("valid", "accepted_email", True, True))

    def test_an_invalid_address_fails_and_is_stored_with_its_reason(self):
        for reason in ("rejected_email", "invalid_domain", "no_mx_record", "exceeded_storage", "invalid_email"):
            with self.subTest(reason=reason):
                self.answer(response(qev("invalid", reason)))

                result = ev.verify_email(f"{reason}@example.com")

                self.assertEqual((result.status, result.reason), ("invalid", reason))
                self.assertFalse(result.passed)
                self.assertEqual(self.stored(f"{reason}@example.com").status, "invalid")

    def test_an_unknown_answer_is_unknown_passes_and_is_stored(self):
        for reason in ("timeout", "no_connect", "unavailable_smtp", "unexpected_error", "temporarily_blocked"):
            with self.subTest(reason=reason):
                self.answer(response(qev("unknown", reason)))

                result = ev.verify_email(f"{reason.replace('_', '-')}@example.com")

                self.assertEqual((result.status, result.reason), ("unknown", reason))
                self.assertTrue(result.passed)

    def test_a_domain_that_accepts_every_address_is_unknown(self):
        self.answer(response(qev("valid", accept_all="true", safe_to_send="false")))

        result = ev.verify_email("anyone@catchall.example")

        self.assertEqual(result.status, "unknown")
        self.assertTrue(result.passed)
        row = self.stored("anyone@catchall.example")
        self.assertTrue(row.accept_all)
        self.assertFalse(row.safe_to_send)

    def test_disposable_and_role_addresses_stay_valid_with_their_flags_kept(self):
        self.answer(response(qev(disposable="true")), response(qev(role="true")))

        results = ev.verify_emails(["temp@mailinator.example", "info@school.example"])

        self.assertEqual({r.status for r in results.values()}, {"valid"})
        self.assertTrue(self.stored("temp@mailinator.example").disposable)
        self.assertTrue(self.stored("info@school.example").role)

    def test_a_suggested_correction_is_kept(self):
        self.answer(response(qev("invalid", "rejected_email", did_you_mean="kid@gmail.com")))

        result = ev.verify_email("kid@gmial.com")

        self.assertEqual(result.did_you_mean, "kid@gmail.com")
        self.assertEqual(self.stored("kid@gmial.com").did_you_mean, "kid@gmail.com")

    def test_flags_sent_as_real_booleans_are_read_too(self):
        self.answer(response(qev(accept_all=False, disposable=True, success=True)))

        result = ev.verify_email("kid@example.com")

        self.assertEqual(result.status, "valid")
        self.assertTrue(self.stored("kid@example.com").disposable)

    def test_safe_to_send_left_out_is_stored_as_not_said(self):
        body = qev()
        del body["safe_to_send"]
        self.answer(response(body))

        ev.verify_email("kid@example.com")

        self.assertIsNone(self.stored("kid@example.com").safe_to_send)


class RequestTests(QevTestCase):
    def test_asks_the_live_endpoint_with_the_key_the_address_and_a_timeout(self):
        self.answer(response())

        ev.verify_email(" Kid@Example.com ")

        self.http.assert_called_once_with(
            ev.VERIFY_URL, params={"apikey": KEY, "email": "kid@example.com"}, timeout=5.0,
        )

    @override_settings(QEV_TIMEOUT_SECONDS=2.5)
    def test_the_timeout_comes_from_the_setting(self):
        self.answer(response())

        ev.verify_email("kid@example.com")

        self.assertEqual(self.http.call_args.kwargs["timeout"], 2.5)

    @override_settings(QEV_USE_SANDBOX=True)
    def test_the_sandbox_setting_uses_the_free_sandbox_endpoint(self):
        self.answer(response(qev("invalid", "rejected_email")))

        result = ev.verify_email("rejected-email@example.com")

        self.assertEqual(self.http.call_args.args[0], ev.SANDBOX_URL)
        self.assertEqual(result.status, "invalid")

    @override_settings(QEV_API_KEY="")
    def test_without_a_key_nothing_is_looked_up_and_every_check_is_an_error(self):
        with self.captured_logs() as records:
            results = ev.verify_emails(["a@example.com", "b@example.com"])

        self.http.assert_not_called()
        self.assertEqual({(r.status, r.reason) for r in results.values()}, {("error", "not_configured")})
        self.assertTrue(all(r.passed for r in results.values()))
        self.assertIn("email_verification.not_configured", [r.getMessage() for r in records])
        self.assertEqual(EmailVerificationCredits.get().lookups_today, 0)


class FailOpenTests(QevTestCase):
    """Any failure reports an error, never raises, and stores nothing."""

    def assertFailedOpen(self, reason, address="kid@example.com"):
        with self.captured_logs() as records:
            result = ev.verify_email(address)

        self.assertEqual((result.status, result.reason), ("error", reason))
        self.assertTrue(result.passed)
        self.assertFalse(EmailVerification.objects.filter(email=address).exists())
        self.assertTrue(any("lookup_failed" in r.getMessage() for r in records))
        self.assertNothingSecretIn(records, address)
        return result

    def test_a_timeout(self):
        self.answer(requests.Timeout("timed out"))
        self.assertFailedOpen("request_timeout")

    def test_a_connection_error(self):
        self.answer(requests.ConnectionError("connection refused"))
        self.assertFailedOpen("connection_error")

    def test_any_other_requests_error(self):
        self.answer(requests.TooManyRedirects("redirects"))
        self.assertFailedOpen("connection_error")

    def test_an_unexpected_exception(self):
        self.answer(ValueError("something odd"))
        self.assertFailedOpen("request_failed")

    def test_each_error_status(self):
        # 402 (out of credit) is its own case: test_email_verification_keys.
        for status in (400, 401, 403, 404, 429, 500, 502, 503):
            with self.subTest(status=status):
                self.answer(response(qev(), status=status))
                self.assertFailedOpen(f"http_{status}")

    def test_a_response_that_isnt_json(self):
        self.answer(response(bad_json=True))
        self.assertFailedOpen("bad_response")

    def test_json_that_isnt_an_object(self):
        self.answer(response(["valid"]))
        self.assertFailedOpen("bad_response")

    def test_a_refused_request(self):
        self.answer(response({"success": "false", "message": "Low credit. Payment required"}))
        self.assertFailedOpen("service_refused")

    def test_an_answer_without_a_result(self):
        body = qev()
        del body["result"]
        self.answer(response(body))
        self.assertFailedOpen("bad_response")

    def test_an_answer_with_a_result_we_dont_know(self):
        self.answer(response(qev("maybe")))
        self.assertFailedOpen("bad_response")

    def test_a_failed_check_is_tried_again_next_time(self):
        self.answer(requests.Timeout("timed out"), response())

        self.assertEqual(ev.verify_email("kid@example.com").status, "error")
        self.assertEqual(ev.verify_email("kid@example.com").status, "valid")
        self.assertEqual(self.http.call_count, 2)

    def test_an_answer_that_cant_be_stored_is_still_reported(self):
        self.answer(response(qev("invalid", "rejected_email")))

        with mock.patch.object(EmailVerification.objects, "update_or_create", side_effect=DatabaseError("x")):
            with self.captured_logs() as records:
                result = ev.verify_email("kid@example.com")

        self.assertEqual(result.status, "invalid")
        self.assertIn("email_verification.store_failed", "\n".join(r.getMessage() for r in records))

    def test_stored_answers_that_cant_be_read_are_looked_up_instead(self):
        self.answer(response())

        with mock.patch.object(EmailVerification, "reusable", side_effect=DatabaseError("x")):
            result = ev.verify_email("kid@example.com")

        self.assertEqual(result.status, "valid")


class SecretTests(QevTestCase):
    """The key travels in the URL, so URLs and exception text are never logged."""

    def test_an_exception_quoting_the_url_never_reaches_the_logs_or_the_result(self):
        url = f"{ev.VERIFY_URL}?apikey={KEY}&email=kid%40example.com"
        self.answer(requests.ConnectionError(f"Max retries exceeded with url: {url}"))

        with self.captured_logs() as records:
            result = ev.verify_email("kid@example.com")

        self.assertNothingSecretIn(records, "kid@example.com", "kid%40example.com")
        self.assertNotIn(KEY, repr(result))

    def test_an_error_status_never_logs_the_key(self):
        self.answer(response({"success": "false", "message": f"Bad key {KEY}"}, status=401))

        with self.captured_logs() as records:
            result = ev.verify_email("kid@example.com")

        self.assertNothingSecretIn(records, "kid@example.com")
        self.assertNotIn(KEY, repr(result))

    def test_a_successful_check_never_logs_the_key_or_the_address(self):
        self.answer(response())

        with self.captured_logs() as records:
            ev.verify_email("kid@example.com")

        self.assertTrue(records)
        self.assertNothingSecretIn(records, "kid@example.com")

    def test_a_check_never_raises_even_when_everything_goes_wrong(self):
        self.answer(requests.ConnectionError(f"url with apikey={KEY}"))

        with mock.patch.object(EmailVerification, "reusable", side_effect=DatabaseError("x")):
            try:
                ev.verify_emails(["kid@example.com"])
            except Exception as exc:  # pragma: no cover - the assertion is that this never runs
                self.fail(f"verify_emails raised {type(exc).__name__}")


class ListTests(QevTestCase):
    def test_repeats_in_any_casing_or_spacing_are_checked_once(self):
        self.answer_always()

        results = ev.verify_emails(["kid@example.com", " KID@example.com", "Kid@Example.COM "])

        self.assertEqual(list(results), ["kid@example.com"])
        self.assertEqual(self.http.call_count, 1)

    def test_blanks_are_left_out_without_a_lookup(self):
        results = ev.verify_emails(["", "   ", None])

        self.assertEqual(results, {})
        self.http.assert_not_called()

    def test_a_malformed_address_is_invalid_without_a_lookup(self):
        results = ev.verify_emails(["not-an-email", "kid@", "@example.com", "two@@example.com"])

        self.assertEqual({(r.status, r.reason) for r in results.values()}, {("invalid", "invalid_email")})
        self.http.assert_not_called()
        self.assertFalse(EmailVerification.objects.exists())

    def test_recent_valid_and_invalid_answers_are_reused(self):
        EmailVerification.objects.create(email="good@example.com", status="valid", reason="accepted_email")
        EmailVerification.objects.create(email="bad@example.com", status="invalid", reason="rejected_email")

        results = ev.verify_emails(["good@example.com", "BAD@example.com"])

        self.http.assert_not_called()
        self.assertEqual(
            {email: (r.status, r.reason, r.cached) for email, r in results.items()},
            {"good@example.com": ("valid", "accepted_email", True), "bad@example.com": ("invalid", "rejected_email", True)},
        )

    def test_an_answer_older_than_the_maximum_age_is_checked_again_and_updated(self):
        old = timezone.now() - timedelta(days=181)
        EmailVerification.objects.create(email="kid@example.com", status="invalid", checked_at=old)
        self.answer(response())

        result = ev.verify_email("kid@example.com")

        self.assertEqual((result.status, result.cached), ("valid", False))
        row = self.stored("kid@example.com")
        self.assertEqual(row.status, "valid")
        self.assertGreater(row.checked_at, old)
        self.assertEqual(EmailVerification.objects.count(), 1)

    @override_settings(QEV_RESULT_MAX_AGE_DAYS=30)
    def test_the_maximum_age_comes_from_the_setting(self):
        EmailVerification.objects.create(
            email="kid@example.com", status="valid", checked_at=timezone.now() - timedelta(days=31),
        )
        self.answer(response())

        ev.verify_email("kid@example.com")

        self.assertEqual(self.http.call_count, 1)

    def test_an_unknown_answer_is_checked_again(self):
        EmailVerification.objects.create(email="kid@example.com", status="unknown", reason="timeout")
        self.answer(response())

        self.assertEqual(ev.verify_email("kid@example.com").status, "valid")
        self.assertEqual(self.http.call_count, 1)

    def test_a_mixed_batch_makes_one_call_per_new_address_in_order(self):
        EmailVerification.objects.create(email="known@example.com", status="valid")
        self.answer_always()

        results = ev.verify_emails([
            "new1@example.com", "", "known@example.com", "bad-address", "NEW1@example.com",
            "new2@example.com", None, "new3@example.com",
        ])

        self.assertEqual(list(results), [
            "new1@example.com", "known@example.com", "bad-address", "new2@example.com", "new3@example.com",
        ])
        self.assertEqual(self.http.call_count, 3)
        self.assertEqual(
            [call.kwargs["params"]["email"] for call in self.http.call_args_list],
            ["new1@example.com", "new2@example.com", "new3@example.com"],
        )

    def test_a_blank_single_address_is_an_error_without_a_lookup(self):
        result = ev.verify_email("  ")

        self.assertEqual((result.status, result.reason), ("error", "blank"))
        self.http.assert_not_called()


class DailyCapTests(QevTestCase):
    def lookups(self):
        credits = EmailVerificationCredits.get()
        return credits.lookups_on, credits.lookups_today

    @override_settings(QEV_DAILY_LOOKUP_CAP=2)
    def test_lookups_stop_at_the_cap_and_the_rest_are_errors_not_stored(self):
        self.answer_always()

        with self.captured_logs() as records:
            results = ev.verify_emails(["a@example.com", "b@example.com", "c@example.com", "d@example.com"])

        self.assertEqual(self.http.call_count, 2)
        self.assertEqual(
            [(r.status, r.reason) for r in results.values()][2:],
            [("error", "daily_cap_reached")] * 2,
        )
        self.assertTrue(all(r.passed for r in results.values()))
        self.assertEqual(EmailVerification.objects.count(), 2)
        self.assertEqual(self.lookups(), (timezone.now().date(), 2))
        self.assertEqual([r.getMessage() for r in records].count("email_verification.daily_cap_reached"), 1)

    @override_settings(QEV_DAILY_LOOKUP_CAP=3)
    def test_the_count_carries_across_batches_on_the_same_day(self):
        self.answer_always()

        ev.verify_emails(["a@example.com", "b@example.com"])
        results = ev.verify_emails(["c@example.com", "d@example.com"])

        self.assertEqual(self.http.call_count, 3)
        self.assertEqual(results["d@example.com"].reason, "daily_cap_reached")

    @override_settings(QEV_DAILY_LOOKUP_CAP=2)
    def test_a_new_day_starts_the_count_again(self):
        credits = EmailVerificationCredits.get()
        credits.lookups_on, credits.lookups_today = timezone.now().date() - timedelta(days=1), 2
        credits.save()
        self.answer_always()

        result = ev.verify_email("kid@example.com")

        self.assertEqual(result.status, "valid")
        self.assertEqual(self.lookups(), (timezone.now().date(), 1))

    def test_failed_lookups_still_count(self):
        self.answer(requests.Timeout("timed out"), response(status=500))

        ev.verify_emails(["a@example.com", "b@example.com"])

        self.assertEqual(self.lookups()[1], 2)

    def test_reused_answers_and_malformed_addresses_dont_count(self):
        EmailVerification.objects.create(email="known@example.com", status="valid")

        ev.verify_emails(["known@example.com", "not-an-email"])

        self.assertEqual(self.lookups()[1], 0)

    @override_settings(QEV_USE_SANDBOX=True, QEV_DAILY_LOOKUP_CAP=1)
    def test_free_sandbox_lookups_dont_count(self):
        self.answer_always()

        ev.verify_emails(["a@example.com", "b@example.com", "c@example.com"])

        self.assertEqual(self.http.call_count, 3)
        self.assertEqual(self.lookups()[1], 0)

    @override_settings(QEV_DAILY_LOOKUP_CAP=0)
    def test_a_cap_of_zero_means_no_limit_and_nothing_is_counted(self):
        self.answer_always()

        results = ev.verify_emails([f"kid{index}@example.com" for index in range(25)])

        self.assertEqual(self.http.call_count, 25)
        self.assertEqual({r.status for r in results.values()}, {"valid"})
        credits = EmailVerificationCredits.objects.filter(pk=1).first()
        self.assertTrue(credits is None or (credits.lookups_on, credits.lookups_today) == (None, 0))

    @override_settings(QEV_DAILY_LOOKUP_CAP=0)
    def test_with_no_cap_reserving_a_lookup_never_touches_the_database(self):
        with self.assertNumQueries(0):
            self.assertTrue(ev._reserve_lookup())

    def test_with_the_setting_missing_there_is_no_cap(self):
        from django.conf import settings

        with override_settings():
            del settings.QEV_DAILY_LOOKUP_CAP
            with self.assertNumQueries(0):
                self.assertTrue(ev._reserve_lookup())

    @override_settings(QEV_DAILY_LOOKUP_CAP=-1)
    def test_a_negative_cap_is_treated_as_no_cap(self):
        self.answer_always()

        self.assertEqual(ev.verify_email("kid@example.com").status, "valid")

    def test_without_a_count_no_paid_lookup_is_made(self):
        with mock.patch.object(EmailVerificationCredits, "get", side_effect=DatabaseError("x")):
            result = ev.verify_email("kid@example.com")

        self.assertEqual((result.status, result.reason), ("error", "daily_cap_reached"))
        self.http.assert_not_called()


class AfterCommitTests(QevTestCase):
    def test_nothing_is_checked_until_the_transaction_commits(self):
        self.answer(response())

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            ev.verify_after_commit(["kid@example.com"])
            self.http.assert_not_called()

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertEqual(self.http.call_count, 1)
        self.assertEqual(self.stored("kid@example.com").status, "valid")

    def test_nothing_is_checked_if_the_transaction_rolls_back(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            try:
                with transaction.atomic():
                    ev.verify_after_commit(["kid@example.com"])
                    raise RuntimeError("registration failed")
            except RuntimeError:
                pass

        self.assertEqual(callbacks, [])
        self.http.assert_not_called()

    def test_the_addresses_are_taken_when_it_is_called(self):
        self.answer(response())
        emails = (email for email in ["kid@example.com"])

        with self.captureOnCommitCallbacks(execute=True):
            ev.verify_after_commit(emails)

        self.assertEqual(self.http.call_count, 1)

    @override_settings(EMAIL_VERIFICATION_DISPATCH_SYNC=False)
    def test_outside_tests_the_check_runs_on_the_background_worker(self):
        with mock.patch.object(ev._EXECUTOR, "submit") as submit:
            with self.captureOnCommitCallbacks(execute=True):
                ev.verify_after_commit(["kid@example.com", "pat@example.com"])

        submit.assert_called_once_with(ev._run_in_pool, ["kid@example.com", "pat@example.com"])
        self.http.assert_not_called()

    @override_settings(EMAIL_VERIFICATION_DISPATCH_SYNC=False)
    def test_a_worker_that_cant_take_the_batch_is_logged_not_raised(self):
        with mock.patch.object(ev._EXECUTOR, "submit", side_effect=RuntimeError("shutting down")):
            with self.captured_logs() as records:
                with self.captureOnCommitCallbacks(execute=True):
                    ev.verify_after_commit(["kid@example.com"])

        self.assertIn("email_verification.dispatch_unavailable", [r.getMessage() for r in records])

    def test_the_background_worker_closes_its_database_connection(self):
        self.answer(response())

        with mock.patch.object(ev.connections, "close_all") as close_all:
            ev._run_in_pool(["kid@example.com"])

        close_all.assert_called_once_with()
        self.assertEqual(self.http.call_count, 1)

    def test_a_check_that_crashes_never_reaches_the_committing_code(self):
        with mock.patch.object(ev, "verify_emails", side_effect=RuntimeError("boom")):
            with self.captured_logs() as records:
                with self.captureOnCommitCallbacks(execute=True):
                    ev.verify_after_commit(["kid@example.com"])

        self.assertIn("email_verification.batch_failed error=RuntimeError", [r.getMessage() for r in records])

    def test_a_finished_batch_logs_its_counts_and_no_addresses(self):
        self.answer(response(), response(qev("invalid", "rejected_email")), requests.Timeout("t"))

        with self.captured_logs() as records:
            with self.captureOnCommitCallbacks(execute=True):
                ev.verify_after_commit(["a@example.com", "b@example.com", "c@example.com", "d@"])

        self.assertIn(
            "email_verification.batch_done checked=4 valid=1 invalid=2 unknown=0 error=1",
            [r.getMessage() for r in records],
        )
        self.assertNothingSecretIn(records, "a@example.com", "b@example.com", "c@example.com")
