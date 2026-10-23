"""Outside the CSV journey, an address QuickEmailVerification answered as not
existing is a hard error (unknown still warns, as on every journey). A guardian's
address can't be a current student's, and one with any other account warns."""
from unittest.mock import patch

from django.core.cache import cache
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.services import current_cohort
from apps.users.models import AdminScope, EmailVerification, MentorProfile, StudentProfile, User
from apps.users.serializers import (
    GUARDIAN_HAS_ACCOUNT, GUARDIAN_IS_STUDENT, REGISTRATION_OVERRIDES, UserRegisterBodySerializer,
    registration_warnings, stored_email_answers,
)
from tests.apps.users.test_registration_email_warnings import answer
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch
from tests.apps.users.test_returning import _last_years_student

NOT_CSV = ("student_individual", "student_team", "team_join", "supervisor_individual", "supervisor_group", "admin")
STUDENT_INVALID = "This email address doesn't appear to exist. Please correct it."
GUARDIAN_INVALID = "The guardian's email address doesn't appear to exist. Please correct it."


def body(**fields):
    return {
        "Title": "kid@students.example.test", "FirstName": "Kid", "Surname": "Student",
        "Country": "Australia", "Region": "NSW", "SchoolName": "Example High", "YearLevel": "10",
        "Areaofinterest": "Biotechnology", "RegisteredBy": "supervisor", **fields,
    }


def guardian(email):
    return {"GuardianName": "Pat", "GuardianSurname": "Parent", "GuardianEmail": email}


class Journeys(MultiStudentSetup):
    def submit(self, *args, **kwargs):
        # More registrations than the per-IP limit allows in one test.
        cache.clear()
        return super().submit(*args, **kwargs)

    def journey(self, name, offset, *, guardian_email=None):
        """A registration on journey ``name`` whose first student has a guardian:
        (body, client, student email, guardian email)."""
        if name == "team_join":
            created = self.post_batch(batch("student_team", 2, offset=offset + 500))
            self.assertEqual(created.status_code, 201, created.data)
            body = batch("student_team", offset=offset)
            body["payload"]["group"] = {"joinCode": created.data["group_code"]}
            body["payload"]["students"] = [batch("student_individual", offset=offset)["payload"]["students"][0]]
            client = self.client
        else:
            body = batch("supervisor_individual" if name == "admin" else name, offset=offset)
            client = (
                self.staff_client if name == "admin"
                else self.supervisor_client if name.startswith("supervisor_") else self.client
            )
        first = body["payload"]["students"][0]
        guardian_email = guardian_email or f"parent{offset}@guardians.example.test"
        first.update(guardianDeferred=False, guardian={
            "firstName": "Pat", "lastName": "Parent", "email": guardian_email,
        })
        return body, client, first["email"], guardian_email


@override_settings(EMAIL_PRECHECK_ENABLED=True, QEV_RESULT_MAX_AGE_DAYS=180)
class MailboxTests(Journeys, TestCase):
    def test_invalid_is_a_hard_error_on_every_journey_but_csv(self):
        for offset, name in enumerate(NOT_CSV):
            with self.subTest(journey=name):
                body, client, student, parent = self.journey(name, offset * 10)
                answer(student, did_you_mean="learner@students.example.org")
                answer(parent)
                # Confirming doesn't get past it.
                body["payload"]["students"][0]["overrides"] = {
                    "ConfirmEmailInvalidOverride": True, "ConfirmGuardianEmailInvalidOverride": True,
                }

                response = self.submit(body=body, client=client)

                self.assertEqual(response.status_code, 400, response.data)
                self.assertNotIn("warnings", response.data)
                self.assertEqual(response.data["fields"]["students.0.email"], [
                    "This email address doesn't appear to exist. Did you mean learner@students.example.org? "
                    "Please correct it.",
                ])
                self.assertEqual(response.data["fields"]["students.0.guardian.email"], [GUARDIAN_INVALID])
                self.assertFalse(User.objects.filter(email=student).exists())

    def test_unknown_warns_on_every_journey_and_can_be_confirmed(self):
        for offset, name in enumerate(NOT_CSV):
            with self.subTest(journey=name):
                body, client, student, parent = self.journey(name, offset * 10)
                answer(student, "unknown")
                answer(parent, "unknown")

                response = self.submit(body=body, client=client)

                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(
                    [(w["code"], w["field"]) for w in response.data["warnings"]],
                    [("email_invalid", "students.0.email"), ("guardian_email_invalid", "students.0.guardian.email")],
                )
                self.assertIn("couldn't be verified", response.data["warnings"][0]["message"])
                body["payload"]["students"][0]["overrides"] = {
                    "ConfirmEmailInvalidOverride": True, "ConfirmGuardianEmailInvalidOverride": True,
                }
                self.assertEqual(self.submit(body=body, client=client).status_code, 201)

    def test_no_answer_or_a_failed_lookup_gives_nothing(self):
        for offset, name in enumerate(NOT_CSV):
            with self.subTest(journey=name, answer="none"):
                body, client, _, _ = self.journey(name, offset * 10)
                self.assertEqual(self.submit(body=body, client=client).status_code, 201)
            with self.subTest(journey=name, answer="lookup failed"):
                body, client, student, parent = self.journey(name, 200 + offset * 10)
                answer(student)
                answer(parent)
                with patch.object(EmailVerification, "reusable", side_effect=DatabaseError("x")):
                    self.assertEqual(self.submit(body=body, client=client).status_code, 201)

    @override_settings(EMAIL_PRECHECK_ENABLED=False)
    def test_with_the_switch_off_an_invalid_answer_does_nothing(self):
        for offset, name in enumerate(NOT_CSV):
            with self.subTest(journey=name):
                body, client, student, parent = self.journey(name, offset * 10)
                answer(student)
                answer(parent)
                self.assertEqual(self.submit(body=body, client=client).status_code, 201)

    def test_the_csv_journey_warns_for_invalid_and_unknown(self):
        body = batch("supervisor_csv", 2)
        second = body["payload"]["students"][1]
        second.update(guardianDeferred=False, guardian={
            "firstName": "Pat", "lastName": "Parent", "email": "parent1@guardians.example.test",
        })
        answer(body["payload"]["students"][0]["email"], did_you_mean="learner0@students.example.org")
        answer("parent1@guardians.example.test", "unknown")

        response = self.submit(body=body, client=self.supervisor_client)

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            [(w["code"], w["field"]) for w in response.data["warnings"]],
            [("email_invalid", "students.0.email"), ("guardian_email_invalid", "students.1.guardian.email")],
        )
        self.assertEqual(
            response.data["warnings"][0]["message"],
            "This email address doesn't appear to exist. Did you mean learner0@students.example.org? "
            "Please correct it, or confirm if this is correct.",
        )
        body["payload"]["students"][0]["overrides"] = {"ConfirmEmailInvalidOverride": True}
        second["overrides"] = {"ConfirmGuardianEmailInvalidOverride": True}
        self.assertEqual(self.submit(body=body, client=self.supervisor_client).status_code, 201)

    def test_a_supervisor_a_student_named_answered_invalid_is_a_hard_error(self):
        for offset, name in enumerate(("student_individual", "student_team")):
            with self.subTest(journey=name):
                body, client, _, _ = self.journey(name, offset * 10)
                EmailVerification.objects.all().delete()
                answer(body["payload"]["supervisor"]["email"], did_you_mean="teacher@example.org")
                body["payload"]["students"][0]["overrides"] = {"ConfirmSupervisorEmailInvalidOverride": True}

                response = self.submit(body=body, client=client)

                self.assertEqual(response.status_code, 400, response.data)
                self.assertNotIn("warnings", response.data)
                self.assertEqual(response.data["fields"]["supervisor.email"], [
                    "The supervisor's email address doesn't appear to exist. Did you mean teacher@example.org? "
                    "Please correct it.",
                ])

    def test_hard_errors_come_with_the_others_and_hold_back_warnings(self):
        body = batch("supervisor_group", 2)
        first, second = body["payload"]["students"]
        first["school"] = "University of Sydney"
        answer(first["email"])
        User.objects.create_user(email=second["email"])
        answer("parent9@guardians.example.test", "unknown")
        second.update(guardianDeferred=False, guardian={
            "firstName": "Pat", "lastName": "Parent", "email": "parent9@guardians.example.test",
        })

        response = self.submit(body=body, client=self.supervisor_client)

        self.assertEqual(response.status_code, 400, response.data)
        self.assertNotIn("warnings", response.data)
        self.assertEqual(response.data["fields"]["students.0.email"], [STUDENT_INVALID])
        self.assertEqual(
            response.data["fields"]["students.1.email"], ["An account with this email address already exists."],
        )

    def test_the_error_has_its_own_code(self):
        answer("kid@students.example.test")
        answers = stored_email_answers(["kid@students.example.test"])

        refused = UserRegisterBodySerializer(data=body(), context={"email_answers": answers, "invalid_is_error": True})
        self.assertFalse(refused.is_valid())
        self.assertEqual(refused.errors["Title"][0].code, "email_invalid_address")
        allowed = UserRegisterBodySerializer(data=body(), context={"email_answers": answers})
        self.assertTrue(allowed.is_valid(), allowed.errors)


class GuardianAccountTests(Journeys, TestCase):
    def current_student(self, email="current@students.example.test"):
        _, profile = _last_years_student(email, account_status=User.AccountStatus.ACTIVE)
        profile.challenge_year = current_cohort()
        profile.save(update_fields=["challenge_year"])
        return email

    def other_accounts(self):
        mentor = User.objects.create_user(email="mentor@example.test")
        MentorProfile.objects.create(user=mentor, institution="Uni", mentor_reason="Help", max_group_count=1)
        admin = User.objects.create_user(email="admin@example.test")
        AdminScope.objects.create(user=admin)
        _last_years_student("last.year@students.example.test")
        User.objects.create_user(email="no.role@example.test")
        return {
            "supervisor": self.supervisor.email, "mentor": "Mentor@Example.test", "admin": "admin@example.test",
            "earlier-year student": "last.year@students.example.test", "no role": "no.role@example.test",
        }

    def test_a_current_students_address_is_refused_on_every_journey(self):
        self.current_student()
        for offset, name in enumerate((*NOT_CSV, "supervisor_csv")):
            with self.subTest(journey=name):
                body, client, student, _ = self.journey(
                    name, offset * 10, guardian_email="Current@Students.example.test",
                )
                body["payload"]["students"][0]["overrides"] = {"ConfirmGuardianEmailHasAccountOverride": True}

                response = self.submit(body=body, client=client)

                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(response.data["fields"]["students.0.guardian.email"], [GUARDIAN_IS_STUDENT])
                self.assertFalse(User.objects.filter(email=student).exists())

    def test_a_student_by_role_alone_is_current_too(self):
        user = User.objects.create_user(email="role.only@students.example.test")
        RoleAssignmentHistory.objects.create(
            user=user, role=Roles.objects.get(role_name="student"), valid_from=timezone.now(),
        )

        serializer = UserRegisterBodySerializer(data=body(**guardian(user.email)))
        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["GuardianEmail"][0].code, "guardian_email_is_student")

    def test_every_other_account_warns_and_can_be_confirmed(self):
        for offset, (kind, email) in enumerate(self.other_accounts().items()):
            with self.subTest(account=kind):
                body, client, student, _ = self.journey("supervisor_individual", offset * 10, guardian_email=email)

                response = self.submit(body=body, client=client)

                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(response.data["warnings"], [{
                    "code": "guardian_email_has_account",
                    "field": "students.0.guardian.email",
                    "override_field": "students.0.overrides.ConfirmGuardianEmailHasAccountOverride",
                    "message": GUARDIAN_HAS_ACCOUNT,
                }])
                body["payload"]["students"][0]["overrides"] = {"ConfirmGuardianEmailHasAccountOverride": True}
                self.assertEqual(self.submit(body=body, client=client).status_code, 201)
                self.assertTrue(User.objects.filter(email=student).exists())

    def test_another_account_warns_on_every_journey(self):
        User.objects.create_user(email="no.role@example.test")
        for offset, name in enumerate((*NOT_CSV, "supervisor_csv")):
            with self.subTest(journey=name):
                body, client, _, _ = self.journey(name, offset * 10, guardian_email="no.role@example.test")

                response = self.submit(body=body, client=client)

                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual([w["code"] for w in response.data["warnings"]], ["guardian_email_has_account"])

    @override_settings(EMAIL_PRECHECK_ENABLED=True, QEV_RESULT_MAX_AGE_DAYS=180)
    def test_a_current_student_is_refused_before_the_mailbox_is_looked_at(self):
        email = self.current_student()
        answer(email)
        body_, client, _, _ = self.journey("supervisor_individual", 0, guardian_email=email)

        response = self.submit(body=body_, client=client)

        self.assertEqual(response.data["fields"]["students.0.guardian.email"], [GUARDIAN_IS_STUDENT])

    def test_a_blank_guardian_is_not_looked_up(self):
        User.objects.create_user(email="no.role@example.test")
        serializer = UserRegisterBodySerializer(data=body(GuardianEmail=""))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(registration_warnings(serializer.validated_data, guardian_accounts=set()), [])
        self.assertEqual(registration_warnings(serializer.validated_data), [])

    def test_without_the_submissions_accounts_it_looks_one_up(self):
        User.objects.create_user(email="no.role@example.test")
        data = body(**guardian("No.Role@example.test"))

        self.assertEqual(
            [w["code"] for w in registration_warnings(data)], ["guardian_email_has_account"],
        )

    def test_the_override_is_accepted(self):
        self.assertIn("ConfirmGuardianEmailHasAccountOverride", REGISTRATION_OVERRIDES)

    def test_the_old_request_format(self):
        User.objects.create_user(email="no.role@example.test")
        legacy = {"body": {
            "Title": "jordan.lee@example.com", "FirstName": "Jordan", "Surname": "Lee", "Country": "Australia",
            "Region": "NSW", "SchoolName": "Example High", "YearLevel": "10", "Areaofinterest": "Biotechnology",
            "GuardianEmail": "no.role@example.test", "GuardianName": "Taylor", "GuardianSurname": "Lee",
        }}

        held = self.client.post("/api/v1/registration", legacy, format="json")
        self.assertEqual(held.status_code, 400, held.data)
        self.assertEqual([w["code"] for w in held.data["warnings"]], ["guardian_email_has_account"])

        legacy["body"]["ConfirmGuardianEmailHasAccountOverride"] = True
        cache.clear()
        self.assertEqual(self.client.post("/api/v1/registration", legacy, format="json").status_code, 200)
        self.assertTrue(StudentProfile.objects.filter(user__email="jordan.lee@example.com").exists())

        cache.clear()
        self.current_student()
        legacy["body"].update(Title="sam.lee@example.com", GuardianEmail="current@students.example.test")
        refused = self.client.post("/api/v1/registration", legacy, format="json")
        self.assertEqual(refused.status_code, 400, refused.data)
        self.assertIn(GUARDIAN_IS_STUDENT, str(refused.data))
