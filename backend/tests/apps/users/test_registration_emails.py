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

    def test_each_student_registering_as_a_team_gets_their_own_group_confirmation(self):
        body = batch("student_team")
        send = self.register(body)
        students = body["payload"]["students"]
        self.assertEqual(
            [(call.args[0], call.args[1], call.args[2]["First_Name"]) for call in send.call_args_list],
            [("registration_group", student["email"], student["firstName"]) for student in students],
        )

    def test_a_student_joining_a_group_by_its_code_gets_it_too(self):
        response = self.post_batch(batch("student_team"))
        self.assertEqual(response.status_code, 201, response.data)
        body = batch("student_team", 1, offset=20)
        body["payload"]["group"] = {"joinCode": response.data["group_code"]}
        send = self.register(body)
        joiner = body["payload"]["students"][0]
        send.assert_called_once()
        self.assertEqual(send.call_args.args[:2], ("registration_group", joiner["email"]))

    def test_nothing_for_a_registration_that_fails(self):
        body = batch("student_individual")
        body["payload"]["students"][0]["email"] = "not-an-email"
        with patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post_batch(body).status_code, 400)
        send.assert_not_called()

    def test_a_supervisor_gets_one_confirmation_for_each_registration_and_their_students_none(self):
        for offset, journey in enumerate(("supervisor_individual", "supervisor_group", "supervisor_csv")):
            with self.subTest(journey):
                send = self.register(batch(journey, offset=offset * 10))
                send.assert_called_once()
                key, to, context = send.call_args.args
                self.assertEqual((key, to), ("registration_supervisor", "manager@example.test"))
                self.assertEqual(context["First_Name"], "Current")
                self.assertTrue(context["STUDENTS_URL"].endswith("/#/my-students"))

    def test_none_when_an_admin_registers_students(self):
        body = batch("supervisor_individual")
        body["payload"]["supervisorEmail"] = "manager@example.test"
        with patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            response = self.submit(body=body, client=self.staff_client)
        self.assertEqual(response.status_code, 201, response.data)
        send.assert_not_called()

    def test_the_group_one_reads_as_the_clients_email(self):
        rendered = render_system_email("registration_group", {"First_Name": "Ben", "YEAR": "2026"})
        self.assertEqual(rendered.subject, "BIOTech Futures: Registration")
        for text in ("Hi Ben,", "registration was successful", "the 2026 BIOTech Futures Challenge as a team."):
            self.assertIn(text, rendered.html)

    def test_the_supervisor_one_reads_as_the_clients_email_with_my_students(self):
        rendered = render_system_email(
            "registration_supervisor",
            {"First_Name": "Sam", "YEAR": "2026", "STUDENTS_URL": "https://portal.test/#/my-students"},
        )
        self.assertEqual(rendered.subject, "BIOTech Futures: Registration")
        for text in (
            "Hi Sam,", "registration was successful",
            "registering your students to the 2026 BIOTech Futures Challenge",
            'href="https://portal.test/#/my-students"', "My Students</a> in BIOTech Connect",
        ):
            self.assertIn(text, rendered.html)

    def test_it_reads_as_the_clients_email(self):
        rendered = render_system_email(
            "registration_student", {"First_Name": "Amy", "YEAR": "2026"},
        )
        self.assertEqual(rendered.subject, "BIOTech Futures: Registration")
        for text in ("Hi Amy,", "registration was successful", "the 2026 BIOTech Futures Challenge as an individual participant"):
            self.assertIn(text, rendered.html)
