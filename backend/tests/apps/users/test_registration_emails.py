"""The emails sent once someone registers (System Emails > Registration)."""
from unittest.mock import patch

from django.test import TestCase

from apps.groups.models import Groups
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
        # Each with the group's code, to share with teammates still to register.
        code = Groups.objects.get().code
        self.assertTrue(code)
        self.assertEqual({call.args[2]["GROUP_CODE"] for call in send.call_args_list}, {code})

    def test_a_student_joining_a_group_by_its_code_gets_it_too(self):
        response = self.post_batch(batch("student_team"))
        self.assertEqual(response.status_code, 201, response.data)
        body = batch("student_team", 1, offset=20)
        body["payload"]["group"] = {"joinCode": response.data["group_code"]}
        send = self.register(body)
        joiner = body["payload"]["students"][0]
        send.assert_called_once()
        self.assertEqual(send.call_args.args[:2], ("registration_group", joiner["email"]))
        self.assertEqual(send.call_args.args[2]["GROUP_CODE"], response.data["group_code"])

    def test_nothing_for_a_registration_that_fails(self):
        body = batch("student_individual")
        body["payload"]["students"][0]["email"] = "not-an-email"
        with patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post_batch(body).status_code, 400)
        send.assert_not_called()

    def test_each_student_a_supervisor_registers_gets_theirs_and_the_supervisor_one_confirmation(self):
        for offset, journey in enumerate(("supervisor_individual", "supervisor_group", "supervisor_csv")):
            with self.subTest(journey):
                body = batch(journey, offset=offset * 10)
                send = self.register(body)
                *to_students, to_supervisor = [call.args for call in send.call_args_list]
                # Each student, with who registered them.
                self.assertEqual(
                    [(key, to, context["First_Name"], context["SUPERVISOR_NAME"]) for key, to, context in to_students],
                    [
                        ("registration_by_supervisor", student["email"], student["firstName"], "Current Supervisor")
                        for student in body["payload"]["students"]
                    ],
                )
                key, to, context = to_supervisor
                self.assertEqual((key, to), ("registration_supervisor", "manager@example.test"))
                self.assertEqual(context["First_Name"], "Current")
                self.assertTrue(context["STUDENTS_URL"].endswith("/#/my-students"))

    def test_each_student_an_admin_registers_gets_the_admin_one_naming_their_supervisor(self):
        for offset, journey in enumerate(("supervisor_individual", "supervisor_group", "supervisor_csv")):
            with self.subTest(journey):
                body = batch(journey, offset=offset * 10)
                body["payload"]["supervisorEmail"] = "manager@example.test"
                with patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
                    response = self.submit(body=body, client=self.staff_client)
                self.assertEqual(response.status_code, 201, response.data)
                # Only the students: no supervisor's confirmation for an admin's registration.
                self.assertEqual(
                    [
                        (call.args[0], call.args[1], call.args[2]["First_Name"], call.args[2]["SUPERVISOR_NAME"])
                        for call in send.call_args_list
                    ],
                    [
                        ("registration_by_admin", student["email"], student["firstName"], "Current Supervisor")
                        for student in body["payload"]["students"]
                    ],
                )

    def test_the_admin_one_names_the_supervisor_they_chose(self):
        rendered = render_system_email(
            "registration_by_admin", {"First_Name": "Amy", "YEAR": "2026", "SUPERVISOR_NAME": "Sam Lee"},
        )
        self.assertEqual(rendered.subject, "BIOTech Futures: Registration")
        for text in (
            "Hi Amy,", "been registered for",
            "The BIOTech Futures team has registered you for the 2026 BIOTech Futures Challenge, "
            "with Sam Lee as your supervisor.",
        ):
            self.assertIn(text, rendered.html)

    def test_the_registered_by_supervisor_one_names_their_supervisor(self):
        rendered = render_system_email(
            "registration_by_supervisor", {"First_Name": "Amy", "YEAR": "2026", "SUPERVISOR_NAME": "Sam Lee"},
        )
        self.assertEqual(rendered.subject, "BIOTech Futures: Registration")
        for text in (
            "Hi Amy,", "been registered for",
            "Your supervisor, Sam Lee, has registered you for the 2026 BIOTech Futures Challenge.",
            "your parent or guardian needs to sign a permission form",
        ):
            self.assertIn(text, rendered.html)

    def test_the_group_one_reads_as_the_clients_email(self):
        rendered = render_system_email("registration_group", {"First_Name": "Ben", "YEAR": "2026"})
        self.assertEqual(rendered.subject, "BIOTech Futures: Registration")
        for text in ("Hi Ben,", "registration was successful", "the 2026 BIOTech Futures Challenge as a team."):
            self.assertIn(text, rendered.html)
        self.assertNotIn("Your group code is", rendered.html)

    def test_the_group_one_gives_the_groups_code(self):
        rendered = render_system_email(
            "registration_group", {"First_Name": "Ben", "YEAR": "2026", "GROUP_CODE": "482913"},
        )
        html = " ".join(rendered.html.split())
        self.assertIn("Your group code is <strong", html)
        self.assertIn("482913</strong>", html)
        self.assertIn("It works until registration closes.", html)

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


class GuardianConsentAtRegistrationTests(MultiStudentSetup, TestCase):
    """A guardian named at registration is sent the consent form ("Approval
    required") once it's saved, not at the next daily run."""

    def test_the_guardian_is_sent_the_consent_form_once_registered(self):
        from django.core import mail

        from apps.users.guardian_reminders import guardians_due
        from apps.users.models import GuardianConsentRequest, StudentProfile

        body = batch("student_individual")
        student = body["payload"]["students"][0]
        guardian = student["guardian"]["email"].lower()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_batch(body)

        self.assertEqual(response.status_code, 201, response.data)
        to_guardian = [message for message in mail.outbox if guardian in message.to]
        self.assertEqual([message.subject for message in to_guardian], ["Action Required: Sign parent/guardian permission form"])
        profile = StudentProfile.objects.get(user__email__iexact=student["email"])
        self.assertTrue(GuardianConsentRequest.objects.filter(student=profile, guardian_email=guardian).exists())
        # The daily run doesn't send it again today; it reminds them from tomorrow.
        self.assertNotIn(profile, list(guardians_due()))

    def test_nothing_for_a_registration_that_fails(self):
        from django.core import mail

        from apps.users.models import GuardianConsentRequest

        body = batch("student_individual")
        body["payload"]["students"][0]["email"] = "not-an-email"
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post_batch(body).status_code, 400)

        self.assertFalse(GuardianConsentRequest.objects.exists())
        self.assertEqual(mail.outbox, [])
