"""The credit balance read from QEV's answers (apps.users.email_credits).

HTTP is mocked as in test_email_verification; no test spends real credits.
"""
from unittest import mock

from django.db import DatabaseError
from django.test import override_settings

from apps.users import email_credits
from apps.users import email_verification as ev
from apps.users.models import EmailVerificationCredits

from .test_email_verification import KEY, QevTestCase, qev, response

HEADER = "X-QEV-Remaining-Credits"


class CreditTestCase(QevTestCase):
    def setUp(self):
        super().setUp()
        email_credits._unreadable_logged = False
        self.addCleanup(setattr, email_credits, "_unreadable_logged", False)

    def balance(self):
        credits = EmailVerificationCredits.get()
        return credits.remaining, credits.updated_at

    def set_balance(self, remaining):
        credits = EmailVerificationCredits.get()
        credits.remaining = remaining
        credits.save()

    def unusable_logs(self, records):
        return [r for r in records if r.getMessage().startswith("email_credits.header_unusable")]


class BalanceTests(CreditTestCase):
    def test_each_answer_updates_the_balance(self):
        self.answer(response(headers={HEADER: "2499"}), response(headers={HEADER: "2498"}))

        ev.verify_email("a@example.com")
        self.assertEqual(self.balance()[0], 2499)
        ev.verify_email("b@example.com")

        remaining, updated_at = self.balance()
        self.assertEqual(remaining, 2498)
        self.assertIsNotNone(updated_at)

    def test_spaces_around_the_number_are_ignored(self):
        self.answer(response(headers={HEADER: " 1200 "}))

        ev.verify_email("kid@example.com")

        self.assertEqual(self.balance()[0], 1200)

    def test_an_error_answer_still_updates_the_balance(self):
        self.answer(response({"success": "false", "message": "Low credit"}, status=402, headers={HEADER: "0"}))

        result = ev.verify_email("kid@example.com")

        self.assertEqual(result.reason, "http_402")
        self.assertEqual(self.balance()[0], 0)

    def test_a_failed_request_leaves_the_balance_alone(self):
        self.set_balance(2000)
        self.answer(ev.requests.Timeout("timed out"))

        ev.verify_email("kid@example.com")

        self.assertEqual(self.balance()[0], 2000)

    def test_the_balance_row_is_locked_while_it_changes(self):
        self.answer(response(headers={HEADER: "2400"}))
        manager = EmailVerificationCredits.objects

        with mock.patch.object(manager, "select_for_update", wraps=manager.select_for_update) as lock:
            ev.verify_email("kid@example.com")

        lock.assert_called_once_with()

    @override_settings(QEV_USE_SANDBOX=True)
    def test_the_sandbox_never_changes_the_balance(self):
        self.set_balance(2000)
        self.answer(response(headers={HEADER: "999999"}), response())

        with self.captured_logs() as records:
            ev.verify_emails(["valid@example.com", "rejected-email@example.com"])

        self.assertEqual(self.balance()[0], 2000)
        self.assertEqual(self.unusable_logs(records), [])


class UnusableHeaderTests(CreditTestCase):
    def test_a_missing_empty_or_non_numeric_header_keeps_the_last_balance(self):
        for headers in ({}, {HEADER: ""}, {HEADER: "   "}, {HEADER: "lots"}, {HEADER: "12.5"},
                        {HEADER: "-3"}, {HEADER: "1,200"}, {HEADER: None}):
            with self.subTest(headers=headers):
                self.set_balance(2000)
                self.answer(response(headers=headers))

                result = ev.verify_email(f"kid{len(str(headers))}@example.com")

                self.assertEqual(result.status, "valid")
                self.assertEqual(self.balance()[0], 2000)

    def test_headers_that_cant_be_read_are_ignored(self):
        broken = mock.Mock()
        broken.get.side_effect = RuntimeError("unreadable")
        self.set_balance(2000)

        email_credits.record_remaining(broken)

        self.assertEqual(self.balance()[0], 2000)

    def test_a_run_of_unusable_headers_is_logged_once(self):
        self.answer_always(headers={})

        with self.captured_logs() as records:
            ev.verify_emails(["a@example.com", "b@example.com", "c@example.com"])

        self.assertEqual(len(self.unusable_logs(records)), 1)

    def test_an_unusable_header_after_a_good_one_is_logged_again(self):
        self.answer(
            response(headers={}), response(headers={HEADER: "2000"}),
            response(headers={}), response(headers={}),
        )

        with self.captured_logs() as records:
            ev.verify_emails(["a@example.com", "b@example.com", "c@example.com", "d@example.com"])

        self.assertEqual(len(self.unusable_logs(records)), 2)


class FailureTests(CreditTestCase):
    def test_a_balance_that_cant_be_saved_is_logged_and_the_check_carries_on(self):
        self.answer(response(qev("invalid", "rejected_email"), headers={HEADER: "2400"}))

        with mock.patch.object(EmailVerificationCredits.objects, "select_for_update",
                               side_effect=DatabaseError("x")):
            with self.captured_logs() as records:
                result = ev.verify_email("kid@example.com")

        self.assertEqual(result.status, "invalid")
        self.assertIn("email_credits.record_failed error=DatabaseError", [r.getMessage() for r in records])

    def test_nothing_logged_names_the_key_or_the_address(self):
        self.answer(response(headers={HEADER: "2400"}), response(headers={HEADER: "nope"}))

        with self.captured_logs() as records:
            ev.verify_emails(["kid@example.com", "pat@example.com"])

        self.assertNothingSecretIn(records, "kid@example.com", "pat@example.com")
        self.assertIn("email_credits.recorded remaining=2400", [r.getMessage() for r in records])
        self.assertNotIn(KEY, repr(self.balance()))
