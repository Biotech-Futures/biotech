"""The emails sent once someone registers (System Emails > Registration)."""
from unittest.mock import patch

from django.test import TestCase

from apps.services.system_email import render_system_email
from apps.submissions.services import current_cohort
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch

SEND = "apps.users.registration_emails.send_system_email"


class RegistrationEmailTests(MultiStudentSetup, TestCase):
    def register(self, body, **kwargs):
        with patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            response = self.post_batch(body, **kwargs)
        self.assertEqual(response.status_code, 201, response.data)
        return send

    def test_a_student_on_their_own_gets_the_student_confirmation(self):
        body = batch("student_individual")
        send = self.register(body)
        student = body["payload"]["students"][0]
        send.assert_called_once_with(
            "registration_student",
            student["email"],
            {"First_Name": student["firstName"], "YEAR": str(current_cohort())},
            background=True,
        )

    def test_nothing_for_a_registration_that_fails(self):
        body = batch("student_individual")
        body["payload"]["students"][0]["email"] = "not-an-email"
        with patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post_batch(body).status_code, 400)
        send.assert_not_called()

    def test_students_registered_by_a_supervisor_get_none(self):
        send = self.register(batch("supervisor_individual"))
        self.assertNotIn("registration_student", [call.args[0] for call in send.call_args_list])

    def test_it_reads_as_the_clients_email(self):
        rendered = render_system_email(
            "registration_student", {"First_Name": "Amy", "YEAR": "2026"},
        )
        self.assertEqual(rendered.subject, "BIOTech Futures: Registration")
        for text in ("Hi Amy,", "registration was successful", "the 2026 BIOTech Futures Challenge as an individual participant"):
            self.assertIn(text, rendered.html)
