"""The warning for an address QuickEmailVerification answered as not existing
or unknown (apps.users.serializers.registration_warnings, stored_email_answers),
which a registration can confirm past. Outside the CSV journey a not-existing
answer is a hard error instead (test_registration_email_rules). Only stored
answers are read: nothing here makes a lookup, so no test can reach the network."""
from datetime import timedelta
from unittest.mock import patch

from django.db import DatabaseError, connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.users.models import EmailVerification, StudentProfile, User
from apps.users.serializers import REGISTRATION_OVERRIDES, registration_warnings, stored_email_answers
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch

STUDENT = "jordan.lee@example.com"
GUARDIAN = "guardian@example.com"
SUPERVISOR = "teacher@example.com"


def answer(email, status="invalid", *, did_you_mean="", days_old=0, hours_old=0):
    return EmailVerification.objects.create(
        email=email, status=status, reason="rejected_email" if status == "invalid" else "accepted_email",
        did_you_mean=did_you_mean, checked_at=timezone.now() - timedelta(days=days_old, hours=hours_old),
    )


def details(**overrides):
    """One student's validated details, as registration_warnings gets them."""
    return {
        "Title": STUDENT, "FirstName": "Jordan", "Surname": "Lee", "SchoolName": "Example High",
        "GuardianEmail": GUARDIAN, **overrides,
    }


@override_settings(EMAIL_PRECHECK_ENABLED=True, QEV_RESULT_MAX_AGE_DAYS=180)
class WarningTests(TestCase):
    def warnings(self, **overrides):
        data = details(**overrides)
        return registration_warnings(data, stored_email_answers([data["Title"], data["GuardianEmail"]]))

    def codes(self, **overrides):
        return [warning["code"] for warning in self.warnings(**overrides)]

    def test_a_students_address_answered_invalid_is_warned_about(self):
        answer(STUDENT)

        self.assertEqual(self.warnings(), [{
            "code": "email_invalid",
            "field": "Title",
            "override_field": "ConfirmEmailInvalidOverride",
            "message": "This email address doesn't appear to exist. Please correct it, or confirm if this is correct.",
        }])

    def test_a_guardians_address_answered_invalid_is_warned_about(self):
        answer(GUARDIAN)

        self.assertEqual(self.warnings(), [{
            "code": "guardian_email_invalid",
            "field": "GuardianEmail",
            "override_field": "ConfirmGuardianEmailInvalidOverride",
            "message": "The guardian's email address doesn't appear to exist. Please correct it, or confirm if this is correct.",
        }])

    def test_the_suggestion_is_mentioned_only_when_there_is_one(self):
        answer(STUDENT, did_you_mean="jordan.lee@example.org")

        (warning,) = self.warnings()
        self.assertEqual(
            warning["message"],
            "This email address doesn't appear to exist. Did you mean jordan.lee@example.org? "
            "Please correct it, or confirm if this is correct.",
        )

    def test_both_addresses_can_be_warned_about_at_once(self):
        answer(STUDENT)
        answer(GUARDIAN)

        self.assertEqual(self.codes(), ["email_invalid", "guardian_email_invalid"])

    def test_no_warning_for_a_valid_answer(self):
        answer(STUDENT, "valid")
        answer(GUARDIAN, "valid")

        self.assertEqual(self.codes(), [])

    def test_an_unknown_answer_warns_as_invalid_does_with_its_own_wording(self):
        answer(STUDENT, "unknown", did_you_mean="jordan.lee@example.org")
        answer(GUARDIAN, "unknown")

        self.assertEqual(self.warnings(), [
            {
                "code": "email_invalid",
                "field": "Title",
                "override_field": "ConfirmEmailInvalidOverride",
                "message": "This email address couldn't be verified. Please check it, or confirm if this is correct.",
            },
            {
                "code": "guardian_email_invalid",
                "field": "GuardianEmail",
                "override_field": "ConfirmGuardianEmailInvalidOverride",
                "message": "The guardian's email address couldn't be verified. Please check it, or confirm if this is correct.",
            },
        ])

    def test_an_unknown_answer_is_confirmed_with_the_same_override(self):
        answer(STUDENT, "unknown")

        self.assertEqual(self.codes(ConfirmEmailInvalidOverride=True), [])

    @override_settings(QEV_UNKNOWN_MAX_AGE_HOURS=24)
    def test_an_unknown_answer_older_than_its_window_is_no_answer(self):
        answer(STUDENT, "unknown", hours_old=25)
        answer(GUARDIAN, "unknown", hours_old=23)

        self.assertEqual(self.codes(), ["guardian_email_invalid"])

    def test_no_warning_without_a_stored_answer(self):
        # A failed check is never stored, so it looks the same: no answer, no warning.
        self.assertEqual(self.codes(), [])

    def test_no_warning_for_an_answer_older_than_the_maximum_age(self):
        answer(STUDENT, days_old=181)
        answer(GUARDIAN, days_old=179)

        self.assertEqual(self.codes(), ["guardian_email_invalid"])

    def test_no_warning_once_confirmed(self):
        answer(STUDENT)
        answer(GUARDIAN)

        self.assertEqual(self.codes(ConfirmEmailInvalidOverride=True), ["guardian_email_invalid"])
        self.assertEqual(self.codes(ConfirmGuardianEmailInvalidOverride=True), ["email_invalid"])

    def test_addresses_match_whatever_their_casing(self):
        answer(STUDENT)

        self.assertEqual(self.codes(Title=" Jordan.Lee@Example.COM "), ["email_invalid"])

    def test_a_blank_guardian_email_is_fine(self):
        self.assertEqual(self.codes(GuardianEmail=""), [])

    def test_without_answers_there_are_no_email_warnings(self):
        answer(STUDENT)

        self.assertEqual(registration_warnings(details()), [])

    @override_settings(EMAIL_PRECHECK_ENABLED=False)
    def test_with_the_switch_off_answers_on_file_are_still_read(self):
        answer(STUDENT)
        answer(GUARDIAN, "unknown")

        with self.assertNumQueries(1):
            on_file = stored_email_answers([STUDENT, GUARDIAN])
        self.assertEqual(
            [w["code"] for w in registration_warnings(details(), on_file)], ["email_invalid", "guardian_email_invalid"],
        )

    def test_the_lookup_is_one_query_and_none_for_nothing(self):
        answer(STUDENT)

        with self.assertNumQueries(1):
            self.assertEqual(list(stored_email_answers([STUDENT, GUARDIAN, "x@example.com"])), [STUDENT])
        with self.assertNumQueries(0):
            self.assertEqual(stored_email_answers(["", None]), {})

    def test_a_lookup_that_fails_gives_no_answers(self):
        with patch.object(EmailVerification, "reusable", side_effect=DatabaseError("x")):
            self.assertEqual(stored_email_answers([STUDENT]), {})

    def test_both_new_overrides_are_accepted(self):
        self.assertTrue({"ConfirmEmailInvalidOverride", "ConfirmGuardianEmailInvalidOverride"} <= REGISTRATION_OVERRIDES)

    def test_the_supervisor_a_student_named_is_warned_about_when_asked(self):
        answer(SUPERVISOR)
        data = details(SupervisorEmail=SUPERVISOR)
        answers = stored_email_answers([SUPERVISOR])

        self.assertEqual(registration_warnings(data, answers), [])
        self.assertEqual(registration_warnings(data, answers, check_supervisor=True), [{
            "code": "supervisor_email_invalid",
            "field": "SupervisorEmail",
            "override_field": "ConfirmSupervisorEmailInvalidOverride",
            "message": "The supervisor's email address doesn't appear to exist. Please correct it, or confirm if this is correct.",
        }])
        confirmed = details(SupervisorEmail=SUPERVISOR, ConfirmSupervisorEmailInvalidOverride=True)
        self.assertEqual(registration_warnings(confirmed, answers, check_supervisor=True), [])

    def test_where_invalid_is_an_error_only_unknown_warns(self):
        answer(STUDENT)
        answer(GUARDIAN, "unknown")
        answers = stored_email_answers([STUDENT, GUARDIAN])

        self.assertEqual(
            [w["code"] for w in registration_warnings(details(), answers, invalid_is_error=True)],
            ["guardian_email_invalid"],
        )


@override_settings(EMAIL_PRECHECK_ENABLED=True, QEV_RESULT_MAX_AGE_DAYS=180)
class RegistrationTests(MultiStudentSetup, TestCase):
    def test_an_address_answered_unknown_holds_the_registration_with_a_warning(self):
        answer(STUDENT, "unknown")
        answer(GUARDIAN, "unknown")

        response = self.post_batch(self.body)

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            [(w["code"], w["field"], w["override_field"]) for w in response.data["warnings"]],
            [
                ("email_invalid", "students.0.email", "students.0.overrides.ConfirmEmailInvalidOverride"),
                ("guardian_email_invalid", "students.0.guardian.email",
                 "students.0.overrides.ConfirmGuardianEmailInvalidOverride"),
            ],
        )
        self.assertFalse(User.objects.filter(email=STUDENT).exists())

    def test_confirming_both_lets_it_through(self):
        answer(STUDENT, "unknown")
        answer(GUARDIAN, "unknown")
        self.body["payload"]["students"][0]["overrides"] = {
            "ConfirmEmailInvalidOverride": True, "ConfirmGuardianEmailInvalidOverride": True,
        }

        self.assertEqual(self.post_batch(self.body).status_code, 201)

    def test_a_supervisor_address_answered_unknown_holds_it_until_confirmed(self):
        answer(SUPERVISOR, "unknown")

        response = self.post_batch(self.body)

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            [(w["code"], w["field"], w["override_field"]) for w in response.data["warnings"]],
            [("supervisor_email_invalid", "supervisor.email",
              "students.0.overrides.ConfirmSupervisorEmailInvalidOverride")],
        )
        self.body["payload"]["students"][0]["overrides"] = {"ConfirmSupervisorEmailInvalidOverride": True}
        self.assertEqual(self.post_batch(self.body).status_code, 201)

    def test_a_supervisor_registering_their_students_isnt_checked(self):
        body = batch("supervisor_csv", 2)
        answer(self.supervisor.email)

        self.assertEqual(self.post_batch(body).status_code, 201)

    def test_a_later_students_warning_points_at_that_student(self):
        body = batch("supervisor_csv", 3)
        answer("learner2@students.example.test")

        response = self.post_batch(body)

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            [(w["field"], w["override_field"]) for w in response.data["warnings"]],
            [("students.2.email", "students.2.overrides.ConfirmEmailInvalidOverride")],
        )

    def test_valid_unknown_stale_or_missing_answers_let_it_through(self):
        answer(STUDENT, "valid")
        answer(GUARDIAN, days_old=200)

        self.assertEqual(self.post_batch(self.body).status_code, 201)

    @override_settings(EMAIL_PRECHECK_ENABLED=False)
    def test_with_the_switch_off_an_answer_on_file_still_holds_it(self):
        answer(STUDENT, "unknown")

        response = self.post_batch(self.body)

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual([w["code"] for w in response.data["warnings"]], ["email_invalid"])

    def test_a_lookup_that_fails_lets_it_through(self):
        answer(STUDENT)

        with patch.object(EmailVerification, "reusable", side_effect=DatabaseError("x")):
            self.assertEqual(self.post_batch(self.body).status_code, 201)

    def test_one_lookup_per_submission_however_many_students(self):
        def lookups_for(count, offset):
            with CaptureQueriesContext(connection) as captured:
                self.assertEqual(self.post_batch(batch("supervisor_csv", count, offset=offset)).status_code, 201)
            return sum('"email_verification"' in query["sql"] for query in captured.captured_queries)

        self.assertEqual(lookups_for(3, 0), 1)
        self.assertEqual(lookups_for(40, 100), 1)

    def test_a_legacy_registration_can_confirm_it_too(self):
        answer(STUDENT, "unknown")
        body = {"body": {
            "Title": STUDENT, "FirstName": "Jordan", "Surname": "Lee", "Country": "Australia", "Region": "NSW",
            "SchoolName": "Example High", "YearLevel": "10", "Areaofinterest": "Biotechnology",
            "GuardianEmail": GUARDIAN, "GuardianName": "Taylor", "GuardianSurname": "Lee",
        }}

        held = self.client.post("/api/v1/registration", body, format="json")
        self.assertEqual(held.status_code, 400, held.data)
        self.assertEqual([w["code"] for w in held.data["warnings"]], ["email_invalid"])

        body["body"]["ConfirmEmailInvalidOverride"] = True
        self.assertEqual(self.client.post("/api/v1/registration", body, format="json").status_code, 200)
        self.assertTrue(StudentProfile.objects.filter(user__email=STUDENT).exists())

    def test_the_existing_warnings_are_unaffected(self):
        answer(STUDENT, "unknown")
        self.body["payload"]["students"][0].update(school="University of Sydney")

        response = self.post_batch(self.body)

        self.assertEqual(
            [w["code"] for w in response.data["warnings"]], ["university_school", "email_invalid"],
        )
