"""Coming back for a later year (apps.users.returning): Start new year
deactivates every student, mentor and supervisor, and registering again is the
only way back. A student or mentor registers with the same email; a supervisor
confirms theirs with a code on the registration page and is signed in. Never
an admin, and a student's guardian gives permission again for the new year."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.resources.models import RoleAssignmentHistory, Roles
from apps.services.models import LoginToken
from apps.submissions.services import current_cohort
from apps.users.models import (
    AdminScope, GuardianConsent, GuardianConsentRequest, MentorProfile, RegistrationSubmission,
    RegistrationWindow, StudentProfile, SupervisorProfile, User, UserInterest,
)
from apps.users.models.areas_of_interest import AreasOfInterest
from apps.users.serializers import UserRegisterBodySerializer
from tests.apps.users.test_registration_latelink import RegistrationSetup
from tests.apps.users.test_registration_mentor import mentor_body

CODE_URL = "/api/v1/registration/returning-supervisor/"
CONFIRM_URL = "/api/v1/registration/returning-supervisor/confirm/"
SUPERVISED = "/api/v1/users/supervised-students/"


def _last_years_student(email="jordan.lee@example.com", **user_fields):
    """A student from last year, as Start new year left them: deactivated,
    their guardian's permission given, a consent link still out."""
    user_fields.setdefault("account_status", User.AccountStatus.DEACTIVATED)
    user = User.objects.create_user(email=email, first_name="Jo", last_name="Old", **user_fields)
    profile = StudentProfile.objects.create(
        user=user, pg_first_name="Pat", pg_last_name="Parent", pg_email="pat@example.com",
        parent_guardian_flag=True, school_name="Old High", year_lvl="9",
        has_join_permission=True, joinperm_responseID="BTF-1", joinperm_granted_at=timezone.now() - timedelta(days=300),
        media_consent=True, guardian_reminder_sent_at=timezone.now() - timedelta(days=300),
        registered_by=StudentProfile.RegisteredBy.SUPERVISOR, supervisor_edited_at=timezone.now() - timedelta(days=200),
        challenge_year=current_cohort() - 1,
    )
    GuardianConsent.objects.create(
        student=profile, guardian_full_name="Pat Parent", guardian_email="pat@example.com",
        media_consent=True, signature_png=b"png", consent_version="2026-1",
    )
    GuardianConsentRequest.objects.create(
        student=profile, token_hash=f"{user.pk:064d}", guardian_email="pat@example.com",
        expires_at=timezone.now() + timedelta(days=5),
    )
    interest = AreasOfInterest.objects.create(interest_desc="Last year's interest")
    UserInterest.objects.create(user=user, interest=interest)
    return user, profile


class ReturningStudentTests(RegistrationSetup, TestCase):
    def test_registering_again_brings_last_years_student_back_for_this_year(self):
        user, profile = _last_years_student()
        last_year = RegistrationWindow.objects.create(year=current_cohort() - 1)
        RegistrationSubmission.objects.create(
            idempotency_key="00000000-0000-0000-0000-000000000001", request_digest="x",
            window=last_year, student=user,
        )

        response = self.submit()

        self.assertEqual(response.status_code, 201, response.data)
        # Their own account, not a new one.
        self.assertEqual(User.objects.filter(email__iexact="jordan.lee@example.com").count(), 1)
        user.refresh_from_db()
        self.assertEqual((user.account_status, user.is_active), (User.AccountStatus.ACTIVE, True))
        self.assertEqual((user.first_name, user.last_name, user.pronouns), ("Jordan", "Lee", "they/them"))
        profile.refresh_from_db()
        # This year's details, registered by themselves this time.
        self.assertEqual(profile.challenge_year, current_cohort())
        self.assertEqual((profile.school_name, profile.year_lvl), ("Example High", "10"))
        self.assertEqual((profile.pg_first_name, profile.pg_email), ("Taylor", "guardian@example.com"))
        self.assertEqual(profile.registered_by, StudentProfile.RegisteredBy.SELF)
        self.assertIsNone(profile.supervisor_edited_at)
        # Their guardian gives permission again.
        self.assertFalse(profile.has_join_permission)
        self.assertIsNone(profile.joinperm_responseID)
        self.assertIsNone(profile.joinperm_granted_at)
        self.assertIsNone(profile.media_consent)
        self.assertIsNone(profile.guardian_reminder_sent_at)
        self.assertIsNotNone(GuardianConsentRequest.objects.get(student=profile).revoked_at)
        # Last year's signed form stays on record.
        self.assertEqual(GuardianConsent.objects.filter(student=profile).count(), 1)
        self.assertEqual(
            sorted(UserInterest.objects.filter(user=user).values_list("interest__interest_desc", flat=True)),
            ["Biotechnology", "Engineering"],
        )
        # A student's role for this year, as a new registration gets.
        self.assertTrue(RoleAssignmentHistory.objects.filter(
            user=user, role__role_name="student", valid_to__gt=timezone.now() + timedelta(weeks=5),
        ).exists())
        # One registration a year: last year's and this year's.
        self.assertEqual(
            sorted(RegistrationSubmission.objects.filter(student=user).values_list("window__year", flat=True)),
            [current_cohort() - 1, current_cohort()],
        )

    def test_last_years_form_no_longer_counts_once_theyre_back(self):
        from apps.management.models import ChallengeYear

        _, profile = _last_years_student()
        GuardianConsent.objects.filter(student=profile).update(signed_at=timezone.now() - timedelta(days=60))
        ChallengeYear.objects.create(year=current_cohort())
        # It stands for the year they signed it for, until they're back.
        self.assertTrue(GuardianConsent.objects.standing().filter(student=profile).exists())

        self.assertEqual(self.submit().status_code, 201)

        self.assertFalse(GuardianConsent.objects.standing().filter(student=profile).exists())
        new_form = GuardianConsent.objects.create(
            student=profile, guardian_full_name="Taylor Guardian", guardian_email="guardian@example.com",
            media_consent=False, signature_png=b"png", consent_version="2027-1",
        )
        self.assertEqual(list(GuardianConsent.objects.standing().filter(student=profile)), [new_form])

    def test_a_student_already_back_this_year_cant_register_twice(self):
        user, _ = _last_years_student()
        self.assertEqual(self.submit().status_code, 201)
        user.deactivate()

        response = self.submit()

        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", str(response.data["fields"]["students.0.email"]))

    def test_only_a_deactivated_student_from_an_earlier_year_comes_back(self):
        refused = {
            "active": dict(account_status=User.AccountStatus.ACTIVE),
            "suspended": dict(account_status=User.AccountStatus.SUSPENDED),
            "staff": dict(is_staff=True),
        }
        for name, fields in refused.items():
            with self.subTest(name):
                email = f"was-{name}@example.com"
                _last_years_student(email, **fields)
                serializer = UserRegisterBodySerializer(data={"Title": email})
                serializer.is_valid()
                self.assertEqual(serializer.errors["Title"][0].code, "email_taken")

    def test_an_admins_student_account_is_never_brought_back(self):
        user, _ = _last_years_student()
        AdminScope.objects.create(user=user)

        response = self.submit()

        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertEqual(user.account_status, User.AccountStatus.DEACTIVATED)

    def test_a_supervisors_email_is_still_refused_for_a_student(self):
        user, _ = _last_years_student()
        SupervisorProfile.objects.create(user=user, school_name="Old High")

        serializer = UserRegisterBodySerializer(data={"Title": user.email})
        serializer.is_valid()

        self.assertEqual(serializer.errors["Title"][0].code, "student_email_is_supervisor")


class ReturningMentorTests(RegistrationSetup, TestCase):
    def setUp(self):
        super().setUp()
        Roles.objects.get_or_create(role_name="mentor")
        self.user = User.objects.create_user(
            email="jordan.ng@uni.example.test", first_name="Jo", last_name="Old",
            account_status=User.AccountStatus.DEACTIVATED,
        )
        MentorProfile.objects.create(user=self.user, institution="Old Uni", mentor_reason="Before.", max_group_count=1)

    def test_registering_again_brings_their_account_back_pending_approval(self):
        response = self.submit(body=mentor_body())

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(User.objects.filter(email__iexact=self.user.email).count(), 1)
        self.user.refresh_from_db()
        # Pending until an admin activates them, as a new mentor is.
        self.assertEqual((self.user.account_status, self.user.is_active), (User.AccountStatus.PENDING, False))
        self.assertEqual((self.user.first_name, self.user.last_name), ("Jordan", "Ng"))
        profile = MentorProfile.objects.get(user=self.user)
        self.assertEqual((profile.institution, profile.max_group_count), ("University of Sydney", 3))
        self.assertTrue(RoleAssignmentHistory.objects.filter(user=self.user, role__role_name="mentor").exists())
        self.assertEqual(RegistrationSubmission.objects.filter(student=self.user).count(), 1)

        # Deactivated again the same year: registering doesn't bring them back twice.
        self.user.deactivate()
        again = self.submit(body=mentor_body())
        self.assertEqual(again.status_code, 400)
        self.assertIn("already exists", str(again.data))

    def test_an_active_mentor_or_an_admin_is_refused(self):
        for status, admin in ((User.AccountStatus.ACTIVE, False), (User.AccountStatus.DEACTIVATED, True)):
            with self.subTest(status=status, admin=admin):
                User.objects.filter(pk=self.user.pk).update(account_status=status, is_staff=admin)
                response = self.submit(body=mentor_body())
                self.assertEqual(response.status_code, 400)
                self.assertIn("already exists", str(response.data))


class ReturningSupervisorTests(RegistrationSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email="sam@school.example", first_name="Sam", last_name="Teacher",
            account_status=User.AccountStatus.DEACTIVATED,
        )
        SupervisorProfile.objects.create(user=self.user, school_name="Example High")

    def confirm(self, code, email=None):
        return self.client.post(CONFIRM_URL, {"email": email or self.user.email, "code": code}, format="json")

    def test_a_code_goes_to_a_supervisors_email_alone_and_every_answer_is_the_same(self):
        with patch("apps.users.returning_views.auth_service.send_login_code") as send:
            answers = [
                self.client.post(CODE_URL, {"email": email}, format="json")
                for email in ("Sam@School.example", "nobody@example.com")
            ]
        self.assertEqual([answer.status_code for answer in answers], [200, 200])
        self.assertEqual(answers[0].data, answers[1].data)
        send.assert_called_once_with("sam@school.example")

    def test_the_code_brings_them_back_and_signs_them_in_to_register_students(self):
        token = LoginToken.create_for_user(self.user)

        response = self.confirm(token.token)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("csrfToken", response.data)
        self.user.refresh_from_db()
        self.assertEqual((self.user.account_status, self.user.is_active), (User.AccountStatus.ACTIVE, True))
        self.assertTrue(RoleAssignmentHistory.objects.filter(user=self.user, role__role_name="supervisor").exists())
        # Signed in: their own page answers.
        self.assertEqual(self.client.get("/api/v1/users/me/").status_code, 200)

    def test_a_wrong_code_brings_nobody_back(self):
        LoginToken.create_for_user(self.user)

        response = self.confirm("000000")

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.account_status, User.AccountStatus.DEACTIVATED)

    def test_never_an_admin_nor_anyone_while_registration_is_closed(self):
        admin = User.objects.create_user(
            email="admin@school.example", first_name="Ada", last_name="Admin",
            account_status=User.AccountStatus.DEACTIVATED,
        )
        SupervisorProfile.objects.create(user=admin, school_name="Example High")
        AdminScope.objects.create(user=admin)
        with patch("apps.users.returning_views.auth_service.send_login_code") as send:
            self.client.post(CODE_URL, {"email": admin.email}, format="json")
        send.assert_not_called()
        self.assertEqual(self.confirm(LoginToken.create_for_user(admin).token, admin.email).status_code, 400)
        admin.refresh_from_db()
        self.assertEqual(admin.account_status, User.AccountStatus.DEACTIVATED)

        self.close_window()
        token = LoginToken.create_for_user(self.user)
        for response in (
            self.client.post(CODE_URL, {"email": self.user.email}, format="json"),
            self.confirm(token.token),
        ):
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data["code"], "registration_closed")
        self.user.refresh_from_db()
        self.assertEqual(self.user.account_status, User.AccountStatus.DEACTIVATED)


class GuardianTablesTests(TestCase):
    """Admin > Guardians and My Students list this challenge year's students alone."""

    def setUp(self):
        self.supervisor = User.objects.create_user(email="sam@school.example", first_name="Sam", last_name="T")
        self.supervisor.activate()
        supervisor = SupervisorProfile.objects.create(user=self.supervisor, school_name="Example High")
        self.admin = User.objects.create_user(email="ada@example.com", first_name="Ada", last_name="Admin")
        self.admin.activate()
        AdminScope.objects.create(user=self.admin)
        for email, year in (("now@example.com", current_cohort()), ("then@example.com", current_cohort() - 1)):
            user = User.objects.create_user(email=email, first_name="Kid", last_name="Example")
            StudentProfile.objects.create(
                user=user, supervisor=supervisor, pg_first_name="Pat", pg_last_name="Parent",
                pg_email="pat@example.com", parent_guardian_flag=True, school_name="Example High",
                year_lvl="10", challenge_year=year,
            )

    def test_last_years_students_arent_listed(self):
        for user in (self.admin, self.supervisor):
            with self.subTest(user=user.email):
                client = APIClient()
                client.force_login(user)
                response = client.get(SUPERVISED)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual([row["email"] for row in response.json()], ["now@example.com"])

    def test_a_new_student_is_this_years(self):
        user = User.objects.create_user(email="new@example.com", first_name="New", last_name="Kid")
        profile = StudentProfile.objects.create(
            user=user, pg_first_name="Pat", pg_last_name="Parent", school_name="Example High", year_lvl="10",
        )
        self.assertEqual(profile.challenge_year, current_cohort())


class AdminActivatesLastYearsStudentTests(TestCase):
    """An admin setting one of last year's students back to Active on Admin >
    Users brings them back for this year, as registering again would."""

    def setUp(self):
        self.admin = User.objects.create_user(email="ada@example.com", first_name="Ada", last_name="Admin")
        self.admin.activate()
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.user, self.profile = _last_years_student()
        Roles.objects.get_or_create(role_name="student")

    def test_the_users_list_says_which_year_theyre_from(self):
        response = self.client.get(f"/api/v1/admin/user/{self.user.pk}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["earlierChallengeYear"], current_cohort() - 1)

    def test_activating_them_makes_them_this_years(self):
        with patch("apps.users.guardian_reminders.email_registered_guardians") as email:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.patch(
                    f"/api/v1/admin/user/{self.user.pk}/status/", {"isActive": True}, format="json",
                )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["data"]["earlierChallengeYear"])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.challenge_year, current_cohort())
        self.assertFalse(self.profile.has_join_permission)
        self.assertIsNone(self.profile.media_consent)
        self.assertTrue(RoleAssignmentHistory.objects.filter(
            user=self.user, role__role_name="student", valid_to__gt=timezone.now(),
        ).exists())
        email.assert_called_once_with([self.user.pk])

    def test_bulk_activating_does_the_same(self):
        response = self.client.patch(
            "/api/v1/admin/user/bulk-status/", {"isActive": True, "userIds": [self.user.pk]}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.challenge_year, current_cohort())

    def test_a_student_already_this_years_is_left_as_they_are(self):
        StudentProfile.objects.filter(pk=self.profile.pk).update(challenge_year=current_cohort())
        self.client.patch(f"/api/v1/admin/user/{self.user.pk}/status/", {"isActive": True}, format="json")
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_join_permission)
