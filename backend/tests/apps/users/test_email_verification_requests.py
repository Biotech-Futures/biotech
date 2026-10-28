"""Each real request to QuickEmailVerification is recorded for usage reporting
(EmailVerificationRequest), and recording one never stops a lookup."""
from unittest import mock

import requests
from django.db import DatabaseError
from django.test import override_settings

from apps.users import email_verification as ev
from apps.users.models import EmailVerificationRequest

from .test_email_verification import QevTestCase, qev, response

PAID_KEY = "test-dummy-paid-key"


def rows():
    return list(EmailVerificationRequest.objects.order_by("id").values("key", "outcome", "credits", "remaining", "caller"))


class RequestLogTests(QevTestCase):
    def test_an_answer_is_one_request_costing_one_credit(self):
        self.answer(response(qev(), headers={"X-QEV-Remaining-Credits": "97"}))

        ev.verify_email("kid@example.com")

        self.assertEqual(rows(), [{"key": "free", "outcome": "valid", "credits": 1, "remaining": 97, "caller": ""}])

    def test_every_answer_is_recorded_as_what_it_said(self):
        for status in ("valid", "invalid", "unknown"):
            with self.subTest(status=status):
                self.answer(response(qev(status, "rejected_email" if status == "invalid" else "accepted_email")))
                ev.verify_email(f"{status}@example.com")
        self.assertEqual([row["outcome"] for row in rows()], ["valid", "invalid", "unknown"])

    def test_failed_requests_are_recorded_and_cost_nothing(self):
        failures = [
            (requests.Timeout("slow"), "request_timeout"),
            (requests.ConnectionError("down"), "connection_error"),
            (response(status=500), "http_500"),
            (response(bad_json=True), "bad_response"),
            (response({"success": "false", "message": "nope"}), "service_refused"),
        ]
        for index, (answer, outcome) in enumerate(failures):
            with self.subTest(outcome=outcome):
                self.answer(answer)
                ev.verify_email(f"fail{index}@example.com")
        self.assertEqual([(row["outcome"], row["credits"]) for row in rows()], [(o, 0) for _, o in failures])

    @override_settings(QEV_PAID_API_KEY=PAID_KEY)
    def test_a_free_key_out_of_credit_then_the_paid_key_is_two_requests(self):
        self.answer(response({"success": "false"}, status=402), response(qev(), headers={"X-QEV-Remaining-Credits": "4999"}))

        ev.verify_email("kid@example.com")

        self.assertEqual(rows(), [
            {"key": "free", "outcome": "out_of_credit", "credits": 0, "remaining": None, "caller": ""},
            {"key": "paid", "outcome": "valid", "credits": 1, "remaining": 4999, "caller": ""},
        ])

    @override_settings(QEV_USE_SANDBOX=True)
    def test_sandbox_requests_are_not_recorded(self):
        self.answer(response(qev()))
        ev.verify_email("kid@example.com")
        self.assertEqual(rows(), [])

    def test_an_answer_on_file_reused_is_not_a_request(self):
        self.answer(response(qev()))
        ev.verify_email("kid@example.com")
        ev.verify_email("kid@example.com")
        self.assertEqual(len(rows()), 1)

    def test_the_feature_that_asked_is_recorded(self):
        self.answer(response(qev()), response(qev()))
        with ev.lookups_for("step_check"):
            ev.verify_email("one@example.com")
        ev.verify_email("two@example.com")
        self.assertEqual([row["caller"] for row in rows()], ["step_check", ""])

    def test_no_email_address_is_kept(self):
        self.answer(response(qev()))
        ev.verify_email("private.person@example.com")
        row = EmailVerificationRequest.objects.get()
        values = " ".join(str(getattr(row, field.attname)) for field in EmailVerificationRequest._meta.fields)
        self.assertNotIn("private.person", values)
        self.assertNotIn("example.com", values)

    def test_a_failure_to_record_never_stops_the_lookup(self):
        self.answer(response(qev()))
        broken = mock.patch.object(EmailVerificationRequest.objects, "create", side_effect=DatabaseError("down"))
        with broken, self.captured_logs() as records:
            result = ev.verify_email("kid@example.com")

        self.assertEqual(result.status, "valid")
        # The answer is still stored for registration to use.
        self.assertEqual(self.stored("kid@example.com").status, "valid")
        self.assertIn("email_verification.request_log_failed", "\n".join(r.getMessage() for r in records))
        self.assertNothingSecretIn(records, "kid@example.com")
