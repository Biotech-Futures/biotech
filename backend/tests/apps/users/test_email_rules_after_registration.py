"""A guardian's (or student's) address saved after registering is refused as
registering refuses it: a placeholder (.invalid) address, or a student's
account as a guardian. An admin's edit, a supervisor's edits and upload sheet,
the guardian details form and the student's own guardian. Only a new address
is checked, so one saved before can still be edited around.

And an address finds its account whatever its case: signing in, a password
reset, the join permission webhook and an admin adding a user."""
from datetime import timedelta
from io import BytesIO

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.admin.services.user import add_users_by_role, ensure_admin_email_available, update_user
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.services.auth_service import _resolve_resettable_user
from apps.users.guardian_details import details_form_link, save_details_form
from apps.users.guardian_upload import parse_guardian_upload
from apps.users.models import StudentProfile, SupervisorProfile, User
from apps.users.serializers import GUARDIAN_IS_STUDENT, PLACEHOLDER_ADDRESS

SUPERVISED = "/api/v1/users/supervised-students/"


def _student(email, *, supervisor=None, pg_email="pat@example.com", **user_fields):
    user = User.objects.create_user(email=email, first_name="Wren", last_name="Ward", **user_fields)
    RoleAssignmentHistory.objects.create(
        user=user, role=Roles.objects.get_or_create(role_name="student")[0],
        valid_from=timezone.now() - timedelta(days=1),
    )
    StudentProfile.objects.create(
        user=user, pg_first_name="Pat", pg_last_name="Parent", pg_email=pg_email,
        parent_guardian_flag=bool(pg_email), school_name="Test High", year_lvl="10", supervisor=supervisor,
    )
    return user


def _legacy(email, **fields):
    """An account saved before addresses were lower-cased."""
    user = User.objects.create_user(email=email.lower(), **fields)
    User.objects.filter(pk=user.pk).update(email=email)
    user.refresh_from_db()
    return user


class AdminEditTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="admin@example.com")
        self.student = _student("ward@example.com")
        self.other = _student("kid@example.com")

    def update(self, **fields):
        return update_user(self.student.id, fields, initiated_by=self.admin)

    def guardian(self):
        return StudentProfile.objects.get(user=self.student).pg_email

    def test_a_placeholder_is_refused_for_the_account_or_the_guardian(self):
        self.assertEqual(self.update(email="wren@example.invalid")["msg"], PLACEHOLDER_ADDRESS)
        self.assertEqual(self.update(guardianEmail="pat@school.invalid")["msg"], PLACEHOLDER_ADDRESS)
        self.student.refresh_from_db()
        self.assertEqual((self.student.email, self.guardian()), ("ward@example.com", "pat@example.com"))

    def test_a_students_account_is_refused_as_the_guardian(self):
        self.assertEqual(self.update(guardianEmail="KID@example.com")["msg"], GUARDIAN_IS_STUDENT)
        self.assertEqual(self.guardian(), "pat@example.com")

    def test_an_address_saved_before_can_still_be_edited_around(self):
        StudentProfile.objects.filter(user=self.student).update(pg_email="kid@example.com")
        result = self.update(guardianEmail="kid@example.com", schoolName="New High")
        self.assertIsNotNone(result["data"], result["msg"])


class SupervisorEditTests(TestCase):
    def setUp(self):
        self.supervisor = User.objects.create_user(email="sam@example.com")
        self.profile = SupervisorProfile.objects.create(user=self.supervisor, school_name="Test High")
        self.student = _student("ward@example.com", supervisor=self.profile)
        _student("kid@example.com")
        self.client = APIClient()
        self.client.force_authenticate(self.supervisor)

    def guardian(self, email):
        return self.client.patch(SUPERVISED, {
            "student_ids": [self.student.id], "pg_first_name": "Robin", "pg_last_name": "Carer", "pg_email": email,
        }, format="json")

    def test_a_placeholder_or_a_students_account_is_refused_as_the_guardian(self):
        for email, message in (("robin@example.invalid", PLACEHOLDER_ADDRESS), ("Kid@Example.com", GUARDIAN_IS_STUDENT)):
            response = self.guardian(email)
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(str(response.data["fields"]["pg_email"]), message)
        self.assertEqual(StudentProfile.objects.get(user=self.student).pg_email, "pat@example.com")

    def test_a_placeholder_is_refused_as_the_students_own_address(self):
        response = self.client.patch(f"{SUPERVISED}{self.student.id}/", {
            "first_name": "Wren", "last_name": "Ward", "email": "wren@example.invalid",
            "school_name": "Test High", "year_lvl": "10",
        }, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(str(response.data["fields"]["email"]), PLACEHOLDER_ADDRESS)
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "ward@example.com")

    def test_an_upload_sheet_flags_both(self):
        _student("lee@example.com", supervisor=self.profile)
        sheet = BytesIO(
            b"student_email,guardian_first_name,guardian_last_name,guardian_email\n"
            b"ward@example.com,Robin,Carer,robin@example.invalid\n"
            b"lee@example.com,Robin,Carer,kid@example.com\n"
        )
        students = StudentProfile.objects.filter(supervisor=self.profile)

        result = parse_guardian_upload(sheet, "guardians.csv", students)

        self.assertEqual(result["checks"]["bad_rows"], [
            {"row": 2, "reason": "guardian_email is a placeholder (.invalid)"},
            {"row": 3, "reason": "guardian_email is a student's account"},
        ])


class GuardianDetailsFormTests(TestCase):
    def test_a_placeholder_or_a_students_account_is_refused(self):
        student = _student("ward@example.com", pg_email=None)
        _student("kid@example.com")
        token = details_form_link(StudentProfile.objects.get(user=student)).rsplit("/", 1)[1]

        for email, message in (("robin@example.invalid", PLACEHOLDER_ADDRESS), ("kid@example.com", GUARDIAN_IS_STUDENT)):
            with self.assertRaisesMessage(ValueError, message):
                save_details_form(token, first_name="Robin", last_name="Carer", email=email)
        self.assertIsNone(StudentProfile.objects.get(user=student).pg_email)


class OwnGuardianTests(TestCase):
    def test_a_placeholder_or_a_students_account_is_refused(self):
        student = _student("ward@example.com")
        _student("kid@example.com")
        client = APIClient()
        client.force_authenticate(student)

        for email, message in (("robin@example.invalid", PLACEHOLDER_ADDRESS), ("kid@example.com", GUARDIAN_IS_STUDENT)):
            response = client.put(
                reverse("me-guardian"), {"first_name": "Robin", "last_name": "Carer", "email": email}, format="json",
            )
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(response.data["fields"]["email"], [message])
        self.assertEqual(StudentProfile.objects.get(user=student).pg_email, "pat@example.com")


class AnyCaseTests(TestCase):
    def setUp(self):
        # Sign-in attempts are counted in the cache.
        cache.clear()

    def test_by_email_prefers_the_exact_match_then_the_oldest(self):
        older = _legacy("Kim@Example.com")
        newer = User.objects.create_user(email="kim@example.com")
        self.assertEqual(User.objects.by_email(" kim@example.com "), newer)
        self.assertEqual(User.objects.by_email("Kim@Example.com"), older)
        self.assertEqual(User.objects.by_email("KIM@EXAMPLE.COM"), older)
        self.assertIsNone(User.objects.by_email(""))

    def test_signing_in_finds_an_account_in_any_case(self):
        _legacy("Kim@Example.com", password="Secret-pass-1", account_status=User.AccountStatus.ACTIVE)
        response = APIClient().post(
            reverse("password-login"), {"email": "kim@example.com", "password": "Secret-pass-1"}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_typing_it_another_way_is_not_more_tries(self):
        User.objects.create_user(email="kim@example.com", password="Secret-pass-1")
        client = APIClient()
        for email in ("kim@example.com", "Kim@example.com", "KIM@example.com", "kIm@example.com", "kiM@example.com"):
            client.post(reverse("password-login"), {"email": email, "password": "wrong"}, format="json")
        response = client.post(
            reverse("password-login"), {"email": "KIM@EXAMPLE.COM", "password": "Secret-pass-1"}, format="json",
        )
        self.assertEqual(response.status_code, 429, response.data)

    def test_a_password_reset_never_fails_on_two_accounts_in_different_case(self):
        _legacy("Kim@Example.com", password="Secret-pass-1", account_status=User.AccountStatus.ACTIVE)
        newer = User.objects.create_user(
            email="kim@example.com", password="Secret-pass-1", account_status=User.AccountStatus.ACTIVE,
        )
        self.assertEqual(_resolve_resettable_user("kim@example.com"), newer)

    def test_the_join_permission_webhook_finds_the_student_in_any_case(self):
        student = _student("ward@example.com")
        with self.settings(JOIN_PERMISSION_WEBHOOK_TOKEN="secret-token"):
            response = APIClient().post(
                reverse("join_perm"), {"body": {"Email": "Ward@Example.com", "ResponseID": "r-1"}},
                format="json", HTTP_X_JOIN_PERMISSION_TOKEN="secret-token",
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(StudentProfile.objects.get(user=student).has_join_permission)

    def test_adding_a_user_refuses_an_address_an_account_has_in_another_case(self):
        _legacy("Kim@Example.com")
        result = add_users_by_role([{"email": "kim@example.com", "firstName": "Kim", "lastName": "Lee", "role": "mentor"}])
        self.assertEqual(result[0]["msg"], "Email already exists")
        self.assertEqual(ensure_admin_email_available("kim@example.com"), "Account email already exists")
