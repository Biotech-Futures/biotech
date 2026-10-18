"""emailCheck and guardianEmailCheck in the admin People payload: the stored
QuickEmailVerification answer for a student's and their guardian's address
(apps.admin.services.user.email_checks)."""
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.admin.services.user import (
    GUARDIAN_AUDIT_KEYS,
    _guardian_audit_state,
    email_checks,
    fetch_user_by_id,
    query_users,
)
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import EmailVerification, MentorProfile, StudentProfile, User


def make_student(index, *, guardian_email=None):
    user = User.objects.create_user(email=f"pupil{index}@school.example", first_name=f"Pupil{index}", last_name="Test")
    RoleAssignmentHistory.objects.create(
        user=user, role=Roles.objects.get_or_create(role_name="student")[0],
        valid_from=timezone.now() - timedelta(days=1),
    )
    StudentProfile.objects.create(
        user=user, pg_first_name="Pat", pg_last_name="Parent", school_name="Test High", year_lvl="10",
        pg_email=guardian_email if guardian_email is not None else f"parent{index}@home.example",
        parent_guardian_flag=True,
    )
    return user


def checked(email, status="valid", reason="accepted_email", did_you_mean=""):
    return EmailVerification.objects.create(email=email, status=status, reason=reason, did_you_mean=did_you_mean)


class EmailChecksTests(TestCase):
    def test_returns_each_stored_answer_by_lower_case_address(self):
        row = checked("pupil1@school.example", "invalid", "rejected_email", did_you_mean="pupil1@school.example.com")
        checked("someone.else@example.com")

        result = email_checks(["  Pupil1@School.EXAMPLE ", "never.checked@example.com", "", None])

        self.assertEqual(result, {"pupil1@school.example": {
            "status": "invalid", "reason": "rejected_email",
            "didYouMean": "pupil1@school.example.com", "checkedAt": row.checked_at.isoformat(),
        }})

    def test_one_query_and_none_for_nothing_to_look_up(self):
        checked("pupil1@school.example")

        with self.assertNumQueries(1):
            email_checks(["pupil1@school.example", "parent1@home.example", "x@example.com"])
        with self.assertNumQueries(0):
            self.assertEqual(email_checks(["", None, "  "]), {})

    def test_an_answer_without_a_suggestion_shows_none(self):
        checked("pupil1@school.example")

        self.assertIsNone(email_checks(["pupil1@school.example"])["pupil1@school.example"]["didYouMean"])


class PeoplePayloadTests(TestCase):
    def row(self, result, user):
        return next(item for item in result["data"]["items"] if item["id"] == user.id)

    def test_checked_addresses_show_their_answer_and_unchecked_ones_none(self):
        checked_student = make_student(1)
        unchecked_student = make_student(2)
        student_row = checked("pupil1@school.example", "valid")
        guardian_row = checked("parent1@home.example", "invalid", "rejected_email", "parent1@home.example.au")

        result = query_users(limit=50)

        row = self.row(result, checked_student)
        self.assertEqual(row["emailCheck"], {
            "status": "valid", "reason": "accepted_email", "didYouMean": None,
            "checkedAt": student_row.checked_at.isoformat(),
        })
        self.assertEqual(row["guardianEmailCheck"], {
            "status": "invalid", "reason": "rejected_email", "didYouMean": "parent1@home.example.au",
            "checkedAt": guardian_row.checked_at.isoformat(),
        })
        other = self.row(result, unchecked_student)
        self.assertIsNone(other["emailCheck"])
        self.assertIsNone(other["guardianEmailCheck"])

    def test_a_guardian_email_stored_in_another_casing_still_matches(self):
        student = make_student(1, guardian_email="Parent.One@Home.Example")
        checked("parent.one@home.example", "unknown", "timeout")

        row = self.row(query_users(limit=50), student)

        self.assertEqual(row["guardianEmailCheck"]["status"], "unknown")

    def test_a_student_with_no_guardian_email_has_no_guardian_check(self):
        student = make_student(1, guardian_email="")

        self.assertIsNone(self.row(query_users(limit=50), student)["guardianEmailCheck"])

    def test_people_who_arent_students_have_neither(self):
        mentor = User.objects.create_user(email="mentor@example.com", first_name="Mia", last_name="Mentor")
        MentorProfile.objects.create(user=mentor)
        checked("mentor@example.com", "invalid")

        row = self.row(query_users(limit=50), mentor)

        self.assertIsNone(row["emailCheck"])
        self.assertIsNone(row["guardianEmailCheck"])

    def test_the_checks_sit_alongside_the_existing_guardian_fields(self):
        student = make_student(1)

        row = self.row(query_users(limit=50), student)

        self.assertEqual(row["guardianEmail"], "parent1@home.example")
        for key in ("guardianFirstName", "guardianLastName", "joinPermissionReceived", "joinpermResponseId",
                    "joinPermissionGrantedAt", "pendingGuardian", "mediaConsent", "consentRequestSentAt",
                    "emailCheck", "guardianEmailCheck"):
            self.assertIn(key, row)

    def test_a_bigger_page_makes_no_more_queries(self):
        def queries_for(count):
            User.objects.all().delete()
            EmailVerification.objects.all().delete()
            for index in range(count):
                make_student(index)
                checked(f"pupil{index}@school.example")
                checked(f"parent{index}@home.example", "invalid")
            with CaptureQueriesContext(connection) as captured:
                result = query_users(limit=50)
            self.assertEqual(len(result["data"]["items"]), count)
            self.assertTrue(all(item["emailCheck"] and item["guardianEmailCheck"] for item in result["data"]["items"]))
            return len(captured.captured_queries)

        self.assertEqual(queries_for(2), queries_for(8))


class SingleUserTests(TestCase):
    def test_one_users_details_show_their_checks(self):
        student = make_student(1)
        checked("pupil1@school.example", "invalid", "rejected_email")

        data = fetch_user_by_id(student.id)

        self.assertEqual(data["emailCheck"]["status"], "invalid")
        self.assertIsNone(data["guardianEmailCheck"])

    def test_the_audited_guardian_fields_are_unchanged(self):
        student = make_student(1)
        checked("parent1@home.example", "invalid")

        state = _guardian_audit_state(student.id)

        self.assertEqual(set(state), set(GUARDIAN_AUDIT_KEYS))
        self.assertNotIn("guardianEmailCheck", GUARDIAN_AUDIT_KEYS)
