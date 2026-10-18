"""The two QuickEmailVerification keys (apps.users.email_verification): the free
QEV_API_KEY first, the paid QEV_PAID_API_KEY when it's out of credit, and when
a key out of credit is tried again.

All HTTP is mocked and both keys are dummies: no test spends real credits."""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.core import mail
from django.db import DatabaseError
from django.test import override_settings
from django.utils import timezone

from apps.users import email_verification as ev
from apps.users.models import EmailVerification, EmailVerificationCredits

from .test_email_verification import QevTestCase, qev, response

FREE_KEY = "test-dummy-key"
PAID_KEY = "test-dummy-paid-key"
HEADER = "X-QEV-Remaining-Credits"
NOON = datetime(2026, 10, 18, 12, 0, tzinfo=dt_timezone.utc)


def out_of_credit():
    return response({"success": "false", "message": "Low credit. Payment required"}, status=402)


@override_settings(
    QEV_API_KEY=FREE_KEY, QEV_PAID_API_KEY=PAID_KEY, QEV_EXHAUSTED_RETRY_MINUTES=60,
    QEV_LOW_CREDIT_THRESHOLDS=(500, 100), QEV_ALERT_EMAIL="info@biotechfutures.org",
)
class KeyTestCase(QevTestCase):
    def keys_used(self):
        names = {FREE_KEY: "free", PAID_KEY: "paid"}
        return [names[call.kwargs["params"]["apikey"]] for call in self.http.call_args_list]

    def exhausted_at(self, name):
        credits = EmailVerificationCredits.objects.filter(pk=1).first()
        return getattr(credits, f"{name}_exhausted_at") if credits else None

    def mark_exhausted(self, name, at):
        credits = EmailVerificationCredits.get()
        setattr(credits, f"{name}_exhausted_at", at)
        credits.save()

    def messages(self, records):
        return [record.getMessage() for record in records]

    def assertNoKeysIn(self, records, *things):
        text = "\n".join(self.messages(records)) + "\n".join(repr(thing) for thing in things)
        self.assertNotIn(FREE_KEY, text)
        self.assertNotIn(PAID_KEY, text)


class FreeKeyFirstTests(KeyTestCase):
    def test_the_free_key_is_used_while_it_has_credit(self):
        self.answer(response(headers={HEADER: "73"}))

        result = ev.verify_email("kid@example.com")

        self.assertEqual(result.status, "valid")
        self.assertEqual(self.keys_used(), ["free"])
        self.assertIsNone(self.exhausted_at("free"))

    def test_out_of_credit_on_the_free_key_falls_back_to_the_paid_key_for_the_same_address(self):
        self.answer(out_of_credit(), response(qev("invalid", "rejected_email"), headers={HEADER: "2400"}))

        with self.captured_logs() as records:
            result = ev.verify_email("kid@example.com")

        self.assertEqual((result.status, result.reason), ("invalid", "rejected_email"))
        self.assertEqual(self.keys_used(), ["free", "paid"])
        self.assertIsNotNone(self.exhausted_at("free"))
        self.assertIsNone(self.exhausted_at("paid"))
        self.assertEqual(self.messages(records).count("email_verification.key_exhausted key=free"), 1)
        self.assertEqual(EmailVerification.objects.get().status, "invalid")

    def test_after_the_free_key_runs_out_later_addresses_go_straight_to_the_paid_key(self):
        self.answer(out_of_credit(), response(), response(), response())

        ev.verify_emails(["a@example.com", "b@example.com", "c@example.com"])

        self.assertEqual(self.keys_used(), ["free", "paid", "paid", "paid"])

    def test_no_credits_left_after_an_answer_marks_the_key_out_of_credit(self):
        self.answer(response(headers={HEADER: "0"}), response())

        first = ev.verify_email("a@example.com")
        second = ev.verify_email("b@example.com")

        self.assertEqual((first.status, second.status), ("valid", "valid"))
        self.assertEqual(self.keys_used(), ["free", "paid"])
        self.assertIsNotNone(self.exhausted_at("free"))

    def test_other_failures_on_the_free_key_dont_fall_back(self):
        for failure, reason in ((response(status=429), "http_429"), (ev.requests.Timeout("t"), "request_timeout"),
                                (response(status=500), "http_500")):
            with self.subTest(reason=reason):
                self.http.reset_mock()
                self.answer(failure)

                result = ev.verify_email(f"{reason}@example.com")

                self.assertEqual((result.status, result.reason), ("error", reason))
                self.assertEqual(self.keys_used(), ["free"])
                self.assertIsNone(self.exhausted_at("free"))


class BothOutOfCreditTests(KeyTestCase):
    def test_both_keys_out_of_credit_fails_open_and_stores_nothing(self):
        self.answer(out_of_credit(), out_of_credit())

        with self.captured_logs() as records:
            result = ev.verify_email("kid@example.com")

        self.assertEqual((result.status, result.reason), ("error", "out_of_credit"))
        self.assertTrue(result.passed)
        self.assertFalse(EmailVerification.objects.exists())
        self.assertIsNotNone(self.exhausted_at("paid"))
        self.assertEqual(self.messages(records).count("email_verification.key_exhausted key=paid"), 1)

    def test_once_both_are_out_later_addresses_make_no_requests_and_log_nothing_more(self):
        self.answer(out_of_credit(), out_of_credit())

        with self.captured_logs() as records:
            results = ev.verify_emails(["a@example.com", "b@example.com", "c@example.com"])

        self.assertEqual(self.keys_used(), ["free", "paid"])
        self.assertEqual({r.reason for r in results.values()}, {"out_of_credit"})
        self.assertEqual(sum("key_exhausted" in m for m in self.messages(records)), 2)

    def test_while_both_are_out_no_daily_lookup_is_counted(self):
        self.mark_exhausted("free", timezone.now())
        self.mark_exhausted("paid", timezone.now())

        with override_settings(QEV_DAILY_LOOKUP_CAP=5):
            ev.verify_emails(["a@example.com", "b@example.com"])

        self.http.assert_not_called()
        self.assertEqual(EmailVerificationCredits.get().lookups_today, 0)


class OneKeyTests(KeyTestCase):
    @override_settings(QEV_PAID_API_KEY="")
    def test_only_the_free_key_means_no_fallback(self):
        self.answer(out_of_credit())

        result = ev.verify_email("kid@example.com")

        self.assertEqual((result.status, result.reason), ("error", "out_of_credit"))
        self.assertEqual(self.keys_used(), ["free"])

    @override_settings(QEV_API_KEY="")
    def test_only_the_paid_key_is_used_directly(self):
        self.answer(response(headers={HEADER: "2400"}))

        result = ev.verify_email("kid@example.com")

        self.assertEqual(result.status, "valid")
        self.assertEqual(self.keys_used(), ["paid"])
        self.assertEqual(EmailVerificationCredits.get().remaining, 2400)

    @override_settings(QEV_API_KEY="", QEV_PAID_API_KEY="")
    def test_no_key_checks_nothing(self):
        result = ev.verify_email("kid@example.com")

        self.assertEqual((result.status, result.reason), ("error", "not_configured"))
        self.http.assert_not_called()


class RetryTests(KeyTestCase):
    def setUp(self):
        super().setUp()
        now = mock.patch.object(ev.timezone, "now", return_value=NOON)
        now.start()
        self.addCleanup(now.stop)

    def test_retry_is_the_set_minutes_later_or_the_next_utc_midnight_whichever_is_sooner(self):
        self.assertEqual(ev.retry_at(NOON), NOON + timedelta(minutes=60))
        late = datetime(2026, 10, 18, 23, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(ev.retry_at(late), datetime(2026, 10, 19, 0, 0, tzinfo=dt_timezone.utc))
        with override_settings(QEV_EXHAUSTED_RETRY_MINUTES=15):
            self.assertEqual(ev.retry_at(NOON), NOON + timedelta(minutes=15))

    def test_a_key_out_of_credit_is_skipped_until_its_retry(self):
        self.mark_exhausted("free", NOON - timedelta(minutes=59))
        self.answer(response())

        ev.verify_email("kid@example.com")

        self.assertEqual(self.keys_used(), ["paid"])

    def test_once_due_it_is_tried_again_and_cleared_when_it_has_credit(self):
        self.mark_exhausted("free", NOON - timedelta(minutes=60))
        self.answer(response(headers={HEADER: "100"}))

        with self.captured_logs() as records:
            ev.verify_email("kid@example.com")

        self.assertEqual(self.keys_used(), ["free"])
        self.assertIsNone(self.exhausted_at("free"))
        self.assertIn("email_verification.key_available key=free", self.messages(records))

    def test_a_new_utc_day_allows_a_retry_sooner(self):
        self.mark_exhausted("free", datetime(2026, 10, 17, 23, 50, tzinfo=dt_timezone.utc))
        self.answer(response())

        with mock.patch.object(ev.timezone, "now", return_value=datetime(2026, 10, 18, 0, 5, tzinfo=dt_timezone.utc)):
            ev.verify_email("kid@example.com")

        self.assertEqual(self.keys_used(), ["free"])

    def test_a_retry_that_finds_it_still_empty_moves_the_time_on_without_logging_again(self):
        self.mark_exhausted("free", NOON - timedelta(hours=2))
        self.answer(out_of_credit(), response())

        with self.captured_logs() as records:
            ev.verify_email("kid@example.com")

        self.assertEqual(self.keys_used(), ["free", "paid"])
        self.assertEqual(self.exhausted_at("free"), NOON)
        self.assertNotIn("email_verification.key_exhausted key=free", self.messages(records))

    def test_if_the_key_record_cant_be_read_every_key_is_tried(self):
        with mock.patch.object(EmailVerificationCredits.objects, "filter", side_effect=DatabaseError("x")):
            self.assertEqual([name for name, _ in ev._usable_keys()], ["free", "paid"])


class BalanceTests(KeyTestCase):
    def test_only_the_paid_keys_balance_is_kept_and_alerted_on(self):
        self.answer(response(headers={HEADER: "40"}), out_of_credit(), response(headers={HEADER: "450"}))

        ev.verify_emails(["a@example.com", "b@example.com"])

        self.assertEqual(EmailVerificationCredits.get().remaining, 450)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("alert level of 500", mail.outbox[0].body)

    @override_settings(QEV_PAID_API_KEY="")
    def test_with_only_the_free_key_there_are_no_alerts(self):
        self.answer(response(headers={HEADER: "3"}))

        ev.verify_email("kid@example.com")

        self.assertIsNone(EmailVerificationCredits.objects.filter(pk=1).values_list("remaining", flat=True).first())
        self.assertEqual(mail.outbox, [])


class SecretTests(KeyTestCase):
    def test_neither_key_is_ever_logged_or_returned(self):
        url = f"{ev.VERIFY_URL}?apikey={FREE_KEY}&email=a%40example.com"
        self.answer(
            out_of_credit(),
            ev.requests.ConnectionError(f"Max retries exceeded with url: {url}&apikey={PAID_KEY}"),
            response(headers={HEADER: "0"}),
            response(status=500, headers={HEADER: "9"}),
        )

        with self.captured_logs() as records:
            results = ev.verify_emails(["a@example.com", "b@example.com", "c@example.com"])

        self.assertTrue(records)
        self.assertNoKeysIn(records, results, EmailVerificationCredits.get().__dict__)
        self.assertNothingSecretIn(records, "a@example.com", "b@example.com", "c@example.com")
