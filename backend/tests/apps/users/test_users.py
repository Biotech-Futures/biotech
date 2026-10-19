from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient

from apps.events.models import Events
from apps.groups.models import Groups
from apps.matching_runtime.models import MatchRecommendation, MatchRun
from apps.users.models import AdminScope, StudentProfile
from apps.groups.models import Countries, CountryStates
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.common.role_names import ROLE_STUDENT, ROLE_SUPERVISOR


User = get_user_model()


class UserEmailFilterTestCase(TestCase):
    """Auth + filter tests for /users/?email= (UserListHTMLView).

    The endpoint was historically ``AllowAny`` — these tests now also assert
    that anonymous and non-admin callers are rejected (CONSOLIDATED 1.2).
    """

    def setUp(self):
        """Create test users"""
        self.client = Client()

        self.admin_user = User.objects.create_user(
            email="admin@admin.com",
            first_name="Admin",
            last_name="User",
            is_active=True
        )
        AdminScope.objects.create(user=self.admin_user)

        self.regular_user = User.objects.create_user(
            email="user@example.com",
            first_name="Regular",
            last_name="User",
            is_active=False
        )

    def test_anonymous_is_rejected(self):
        """Anonymous callers must not be able to enumerate users."""
        response = self.client.get(reverse("UserListHTMLView"))
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_non_admin_user_is_rejected(self):
        """A logged-in but non-admin user must not be able to enumerate users."""
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("UserListHTMLView"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_email_filter_admin(self):
        """Admin can filter for admin@admin.com"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("UserListHTMLView"), {"email": "admin@admin.com"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin@admin.com')
        self.assertContains(response, 'Admin')

    def test_email_filter_regular_user(self):
        """Admin can filter for user@example.com"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("UserListHTMLView"), {"email": "user@example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'user@example.com')
        self.assertContains(response, 'Regular')

    def test_email_filter_nonexistent(self):
        """Admin filtering for a non-existent email returns no rows."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("UserListHTMLView"), {"email": "notfound@example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'admin@admin.com')
        self.assertNotContains(response, 'user@example.com')

    def test_no_email_filter(self):
        """Admin without a filter sees all users."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("UserListHTMLView"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin@admin.com')
        self.assertContains(response, 'user@example.com')


class AdminWorkflowApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="ops-admin@test.com",
            password="adminpass123",
            first_name="Ops",
            last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin_user)

        self.target_user = User.objects.create_user(
            email="target@test.com",
            first_name="Target",
            last_name="User",
        )
        self.invited_user = User.objects.create_user(
            email="invited@test.com",
            first_name="Invited",
            last_name="User",
        )
        self.group = Groups.objects.create(group_name="Ops Group")
        self.match_run = MatchRun.objects.create(
            initiated_by_user=self.admin_user,
            run_type=MatchRun.RunTypeChoices.MANUAL,
        )
        self.recommendation = MatchRecommendation.objects.create(
            match_run=self.match_run,
            group=self.group,
            mentor_user=self.admin_user,
        )
        self.event = Events.objects.create(
            event_name="Upcoming Event",
            start_datetime=timezone.now() + timedelta(days=5),
            ends_datetime=timezone.now() + timedelta(days=5, hours=1),
            event_format="virtual",
        )

    def test_bulk_status_updates_users(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            reverse("admin-bulk-user-status"),
            {
                "user_ids": [self.target_user.id, self.invited_user.id],
                "account_status": User.AccountStatus.ACTIVE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.refresh_from_db()
        self.invited_user.refresh_from_db()
        self.assertEqual(self.target_user.account_status, User.AccountStatus.ACTIVE)
        self.assertTrue(self.target_user.is_active)
        self.assertIsNotNone(self.target_user.activated_at)
        self.assertEqual(self.invited_user.account_status, User.AccountStatus.ACTIVE)

    def test_admin_summary_returns_operational_counts(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse("admin-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["active_groups"], 1)
        self.assertEqual(response.data["groups_without_mentor"], 1)
        self.assertEqual(response.data["unassigned_match_recommendations"], 1)
        self.assertGreaterEqual(response.data["upcoming_events"], 1)


class AuthUnificationTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # Prevent brute force limits from spilling across unit tests
        self.client = APIClient()
        self.user_email = "testauth@example.com"
        self.user_pass = "SecurePass123"
        self.target_user = User.objects.create_user(
            email=self.user_email,
            password=self.user_pass,
            first_name="Auth",
            last_name="Test",
            account_status=User.AccountStatus.ACTIVE
        )

    def test_password_login_success_creates_session(self):
        response = self.client.post(
            reverse("password-login"),
            {"email": self.user_email, "password": self.user_pass},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify Django session cookie is attached in response
        self.assertTrue(self.client.session.session_key is not None)

    def test_password_login_fails_brute_force_lockout(self):
        # 5 consecutive failures
        for _ in range(5):
            self.client.post(
                reverse("password-login"),
                {"email": self.user_email, "password": "WrongPassword"},
                format="json"
            )

        # 6th attempt should be 429 Too Many Requests
        response = self.client.post(
            reverse("password-login"),
            {"email": self.user_email, "password": self.user_pass},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_password_login_fails_inactive_account(self):
        self.target_user.deactivate()

        response = self.client.post(
            reverse("password-login"),
            {"email": self.user_email, "password": self.user_pass},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # The frontend branches on this code — keep it stable.
        self.assertEqual(response.json()["code"], "account_inactive")

    def test_password_login_fails_suspended_account(self):
        self.target_user.suspend()

        response = self.client.post(
            reverse("password-login"),
            {"email": self.user_email, "password": self.user_pass},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["code"], "account_inactive")

    def test_inactive_login_statuses_is_only_suspended_and_deactivated(self):
        """invited/pending must never be added here — they are is_active=False
        but are deliberately still allowed to log in."""
        self.assertEqual(
            User.INACTIVE_LOGIN_STATUSES,
            frozenset({"suspended", "deactivated"}),
        )

    def test_password_login_allowed_for_invited_and_pending(self):
        from django.core.cache import cache

        for transition in ("invite", "mark_pending"):
            with self.subTest(transition=transition):
                cache.clear()
                getattr(self.target_user, transition)()

                response = self.client.post(
                    reverse("password-login"),
                    {"email": self.user_email, "password": self.user_pass},
                    format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_login_per_ip_throttle_blocks_credential_stuffing(self):
        """Regression: a single IP must not be able to fan out brute-force
        attempts across many guessed emails. The per-email lockout alone left
        this attack vector open — see CONSOLIDATED 1.2."""
        from apps.users.views import PWD_LOGIN_PER_IP_LIMIT

        # Burn the per-IP budget using a fresh email each attempt so the
        # per-email counter never trips. All requests come from the same
        # REMOTE_ADDR (APIClient default 127.0.0.1).
        for i in range(PWD_LOGIN_PER_IP_LIMIT):
            response = self.client.post(
                reverse("password-login"),
                {"email": f"stuff{i}@example.com", "password": "WrongPassword"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Next attempt — even with valid credentials for a real user — must
        # be rejected because the IP budget is exhausted.
        response = self.client.post(
            reverse("password-login"),
            {"email": self.user_email, "password": self.user_pass},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_password_login_success_clears_ip_counter(self):
        """A successful login from an IP should reset its failure counter so
        a legitimate user behind a shared NAT isn't permanently penalized by
        their own typo history."""
        from django.core.cache import cache
        from apps.users.views import PWD_LOGIN_PER_IP_LIMIT

        # Accumulate failures from the same IP but stop one short of the cap.
        for i in range(PWD_LOGIN_PER_IP_LIMIT - 1):
            self.client.post(
                reverse("password-login"),
                {"email": f"stuff{i}@example.com", "password": "WrongPassword"},
                format="json",
            )

        response = self.client.post(
            reverse("password-login"),
            {"email": self.user_email, "password": self.user_pass},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(cache.get("pwd_login_attempts_ip:127.0.0.1"), None)


class UserDetailLockdownTests(TestCase):
    """Regression tests for the legacy ``AllowAny`` on ``UsersRetrieveUpdateView``
    that let any anonymous caller PATCH ``account_status`` / ``role_id`` —
    CONSOLIDATED 1.2."""

    def setUp(self):
        self.client = APIClient()

        self.admin_user = User.objects.create_user(
            email="admin-lockdown@test.com",
            first_name="Lock",
            last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin_user)

        self.target_user = User.objects.create_user(
            email="target-lockdown@test.com",
            first_name="Lock",
            last_name="Target",
        )
        self.url = reverse("user-detail", args=[self.target_user.id])

    def test_anonymous_get_forbidden(self):
        response = self.client.get(self.url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_anonymous_patch_cannot_change_status(self):
        response = self.client.patch(
            self.url,
            {"account_status": User.AccountStatus.DEACTIVATED},
            format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.target_user.refresh_from_db()
        self.assertNotEqual(self.target_user.account_status, User.AccountStatus.DEACTIVATED)

    def test_non_admin_patch_forbidden(self):
        other_user = User.objects.create_user(
            email="random@test.com", first_name="Random", last_name="User",
        )
        self.client.force_authenticate(user=other_user)
        response = self.client.patch(
            self.url,
            {"account_status": User.AccountStatus.DEACTIVATED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.target_user.refresh_from_db()
        self.assertNotEqual(self.target_user.account_status, User.AccountStatus.DEACTIVATED)


class MePatchPrivilegeEscalationTests(TestCase):
    """P0 regression suite for the documented privilege-escalation vector
    in ``MeRetrieveView.patch``.

    Before the fix, any authenticated user could PATCH ``/users/me/`` with a
    body like ``{"role_id": 1}`` and the view would unconditionally call
    ``get_object_or_404(Roles, pk=...)`` then ``RoleAssignmentHistory.objects
    .create(user=self.request.user, role=role, ...)`` — granting themselves
    the admin role. ``account_status`` had the same shape (a suspended user
    could re-activate themselves).

    These tests pin the new contract: admin-only fields are rejected with
    400 by name, harmless fields (``timezone``) still flow through, and the
    database never reflects a forbidden mutation.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

        self.client = APIClient()

        from apps.resources.models import Roles
        self.admin_role = Roles.objects.create(role_name="admin")
        self.student_role = Roles.objects.create(role_name="student")

        self.student = User.objects.create_user(
            email="self-escalator@example.com",
            password="StudentPass123",
            first_name="Esc",
            last_name="Student",
            account_status=User.AccountStatus.ACTIVE,
        )
        self.url = reverse("MeListHTMLView")
        self.client.force_authenticate(user=self.student)

    def test_patch_role_id_admin_returns_400(self):
        """The original P0: granting self the admin role."""
        response = self.client.patch(
            self.url, {"role_id": self.admin_role.id}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Custom exception handler nests per-field errors under "fields".
        self.assertIn("role_id", response.data.get("fields", {}))

    def test_patch_role_id_does_not_create_role_assignment(self):
        from apps.resources.models import RoleAssignmentHistory

        self.client.patch(
            self.url, {"role_id": self.admin_role.id}, format="json",
        )

        assignments = RoleAssignmentHistory.objects.filter(
            user=self.student, role=self.admin_role,
        )
        self.assertFalse(
            assignments.exists(),
            "PATCH /users/me/ must NEVER create a RoleAssignmentHistory row.",
        )

    def test_patch_account_status_returns_400(self):
        """Same shape as role_id — a suspended user could re-activate."""
        response = self.client.patch(
            self.url,
            {"account_status": User.AccountStatus.SUSPENDED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("account_status", response.data.get("fields", {}))
        self.student.refresh_from_db()
        self.assertEqual(self.student.account_status, User.AccountStatus.ACTIVE)

    def test_patch_other_admin_only_fields_return_400(self):
        """All admin-only fields should fail loud, not silently.

        ``state`` / ``state_id`` are the geography fields that replaced the
        removed ``track`` — they remain admin-only on the self endpoint.
        """
        for field, value in [
            ("is_staff", True),
            ("is_superuser", True),
            ("is_active", False),
            ("state_id", 9999),
            ("state", 9999),
        ]:
            response = self.client.patch(self.url, {field: value}, format="json")
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST,
                msg=f"{field} should be rejected with 400",
            )
            self.assertIn(
                field, response.data.get("fields", {}),
                msg=f"{field} error should appear in response.data['fields']",
            )

    def test_patch_mixed_forbidden_and_allowed_rejects_whole_request(self):
        """If any forbidden field is present the whole request fails — no
        partial application that would leave the user confused about state."""
        response = self.client.patch(
            self.url,
            {"timezone": "Australia/Sydney", "role_id": self.admin_role.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.student.refresh_from_db()
        self.assertNotEqual(self.student.timezone, "Australia/Sydney")

    def test_patch_timezone_succeeds(self):
        """Sanity: the one legitimately self-mutable field still works."""
        response = self.client.patch(
            self.url, {"timezone": "Australia/Sydney"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertEqual(self.student.timezone, "Australia/Sydney")

    def test_anonymous_patch_rejected(self):
        """Belt-and-braces: the IsAuthenticated guard still works."""
        self.client.force_authenticate(user=None)
        response = self.client.patch(
            self.url, {"role_id": self.admin_role.id}, format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class StudentProfileDashboardFieldsTests(TestCase):
    def test_me_exposes_guardian_email_and_permission_timestamp(self):
        client = APIClient()
        student = User.objects.create_user(
            email="dashboard-student@test.com",
            password="StudentPass123",
            first_name="Dashboard",
            last_name="Student",
            account_status=User.AccountStatus.ACTIVE,
        )
        student_role = Roles.objects.create(role_name=ROLE_STUDENT)
        RoleAssignmentHistory.objects.create(
            user=student,
            role=student_role,
            valid_from=timezone.now(),
        )
        granted_at = timezone.now()
        StudentProfile.objects.create(
            user=student,
            pg_first_name="Grace",
            pg_last_name="Guardian",
            pg_email="guardian@test.com",
            school_name="Dashboard High",
            year_lvl="10",
            parent_guardian_flag=True,
            has_join_permission=True,
            joinperm_granted_at=granted_at,
        )

        client.force_authenticate(user=student)
        response = client.get(reverse("MeListHTMLView"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pg_email"], "guardian@test.com")
        self.assertTrue(response.data["join_perm"])
        self.assertIsNotNone(response.data["joinperm_granted_at"])


class ReceiveJoinPermissionTokenTests(TestCase):
    """The legacy ``AllowAny`` on ``ReceiveJoinPermissionView`` let any anonymous
    caller flip ``has_join_permission`` for any student email — CONSOLIDATED 1.2.
    The endpoint now requires a shared-secret HMAC token."""

    def setUp(self):
        from apps.users.models import StudentProfile
        self.client = APIClient()
        self.student = User.objects.create_user(
            email="student-joinperm@test.com",
            first_name="Join",
            last_name="Student",
        )
        self.profile = StudentProfile.objects.create(
            user=self.student,
            pg_first_name="Guardian",
            pg_last_name="Name",
            # CHECK constraint ``permission_requires_parent_guardian`` requires
            # this flag when ``has_join_permission`` is set — see
            # apps/users/models/student_profile.py.
            parent_guardian_flag=True,
            school_name="Test School",
            year_lvl="10",
        )
        self.url = reverse("join_perm")
        self.payload = {
            "body": {
                "Email": self.student.email,
                "ResponseID": "form-response-1",
            }
        }

    def test_returns_503_when_token_unset(self):
        with self.settings(JOIN_PERMISSION_WEBHOOK_TOKEN=""):
            response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.has_join_permission)

    def test_missing_token_rejected(self):
        with self.settings(JOIN_PERMISSION_WEBHOOK_TOKEN="secret-token"):
            response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.has_join_permission)

    def test_wrong_token_rejected(self):
        with self.settings(JOIN_PERMISSION_WEBHOOK_TOKEN="secret-token"):
            response = self.client.post(
                self.url,
                self.payload,
                format="json",
                HTTP_X_JOIN_PERMISSION_TOKEN="wrong-token",
            )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.has_join_permission)

    def test_correct_token_grants_permission(self):
        with self.settings(JOIN_PERMISSION_WEBHOOK_TOKEN="secret-token"):
            response = self.client.post(
                self.url,
                self.payload,
                format="json",
                HTTP_X_JOIN_PERMISSION_TOKEN="secret-token",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_join_permission)
        self.assertEqual(self.profile.joinperm_responseID, "form-response-1")
        self.assertIsNotNone(self.profile.joinperm_granted_at)


class RegistrationGeographyTests(TestCase):
    """Self-registration must store the country on its own field and only record a
    Region as a state. Non-Australian registrants used to get a synthetic state row
    named after their country, which surfaced as "STATE: United Arab Emirates"."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("registration")
        for name in [ROLE_STUDENT, ROLE_SUPERVISOR]:
            Roles.objects.get_or_create(role_name=name)

    def _register(self, country, region=""):
        payload = {
            "body": {
                "Title": "kid@example.com",
                "FirstName": "Kid",
                "Surname": "Student",
                "Country": country,
                "Region": region,
                "SupervisorEmail": "sup@example.com",
                "SupervisorFirstName": "Sam",
                "SupervisorSurname": "Super",
                "GuardianEmail": "parent@example.com",
                "GuardianName": "Pat",
                "GuardianSurname": "Parent",
                "SchoolName": "Test High",
                "YearLevel": "10",
                "Areaofinterest": "Biotechnology",
            }
        }
        return self.client.post(self.url, payload, format="json")

    def test_international_registrant_has_country_and_no_state(self):
        self._register("United Arab Emirates")
        user = User.objects.get(email="kid@example.com")
        self.assertEqual(user.country.country_name, "United Arab Emirates")
        self.assertIsNone(user.state_id)
        self.assertFalse(
            CountryStates.objects.filter(state_name="United Arab Emirates").exists()
        )

    def test_country_echoed_as_region_is_not_stored_as_a_state(self):
        self._register("United Arab Emirates", region="United Arab Emirates")
        user = User.objects.get(email="kid@example.com")
        self.assertEqual(user.country.country_name, "United Arab Emirates")
        self.assertIsNone(user.state_id)

    def test_australian_registrant_keeps_region_as_state(self):
        self._register("Australia", region="NSW")
        user = User.objects.get(email="kid@example.com")
        self.assertEqual(user.country.country_name, "Australia")
        self.assertEqual(user.state.state_name, "NSW")
        self.assertEqual(user.state.country_id, user.country_id)

    def test_supervisor_nomination_does_not_create_a_privileged_account(self):
        self._register("Australia", region="NSW")
        from apps.users.models import RegistrationSubmission
        self.assertFalse(User.objects.filter(email="sup@example.com").exists())
        submission = RegistrationSubmission.objects.get(student__email="kid@example.com")
        self.assertEqual(submission.supervisor_details["email"], "sup@example.com")

    def test_country_casing_variant_reuses_the_existing_country(self):
        Countries.objects.create(country_name="Australia")
        self._register("australia", region="NSW")
        user = User.objects.get(email="kid@example.com")
        self.assertEqual(user.country.country_name, "Australia")
        self.assertEqual(Countries.objects.filter(country_name__iexact="australia").count(), 1)


class SupervisedStudentsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.supervisor = User.objects.create_user(
            email="supervisor@test.com",
            first_name="Sam",
            last_name="Supervisor",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        from apps.users.models import StudentProfile, SupervisorProfile

        self.sup_profile = SupervisorProfile.objects.create(
            user=self.supervisor, school_name="Test High"
        )
        self.student = User.objects.create_user(
            email="student@test.com",
            first_name="Alex",
            last_name="Student",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        StudentProfile.objects.create(
            user=self.student,
            pg_first_name="Pat",
            pg_last_name="Parent",
            parent_guardian_flag=True,
            supervisor=self.sup_profile,
            school_name="Test High",
            year_lvl="11",
            has_join_permission=False,
        )
        self.outsider = User.objects.create_user(
            email="outsider@test.com",
            first_name="Out",
            last_name="Sider",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )

    def test_supervisor_lists_linked_students(self):
        self.client.force_login(self.supervisor)
        response = self.client.get("/api/v1/users/supervised-students/")
        self.assertEqual(response.status_code, 200)
        emails = [row["email"] for row in response.json()]
        self.assertEqual(emails, ["student@test.com"])
        row = response.json()[0]
        self.assertEqual(row["school_name"], "Test High")
        self.assertEqual(row["year_lvl"], "11")
        self.assertTrue(row["parent_guardian_flag"])
        self.assertFalse(row["has_join_permission"])
        self.assertIsNone(row["group_id"])
        self.assertEqual(row["pg_email"], "")
        self.assertEqual(row["joinperm_response_id"], "")
        self.assertIsNone(row["joinperm_granted_at"])
        # Signatures are fetched when a consent form is opened, not listed.
        self.assertNotIn("signature", row)
        self.assertEqual(row["country_name"], "")
        self.assertEqual(row["state_name"], "")
        self.assertEqual(row["account_status"], "Active")
        self.assertIsNone(row["media_consent"])
        self.assertIsNone(row["media_consent_at"])

    def test_drawn_consent_signature_is_fetched_on_its_own(self):
        import io

        from PIL import Image, ImageDraw

        from apps.users.consent_form import CURRENT_VERSION
        from apps.users.models import GuardianConsent, StudentProfile

        image = Image.new("RGBA", (80, 40), (0, 0, 0, 0))
        ImageDraw.Draw(image).line([(5, 30), (70, 10)], fill=(0, 0, 0, 255), width=3)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        profile = StudentProfile.objects.get(user=self.student)
        consent = GuardianConsent.objects.create(
            student=profile,
            guardian_full_name="Pat Parent",
            guardian_email="pat@example.com",
            media_consent=True,
            signature_png=buffer.getvalue(),
            consent_version=CURRENT_VERSION,
        )
        self.client.force_login(self.supervisor)
        row = self.client.get("/api/v1/users/supervised-students/").json()[0]
        self.assertNotIn("signature", row)
        self.assertTrue(row["media_consent"])
        # Given when the form was signed.
        self.assertEqual(parse_datetime(row["media_consent_at"]), consent.signed_at)

        url = "/api/v1/users/supervised-students/signatures/"
        response = self.client.get(url, {"ids": str(self.student.id)})
        self.assertEqual(response.status_code, 200)
        signature = response.json()["signatures"][str(self.student.id)]
        self.assertTrue(signature.startswith("data:image/png;base64,"))

        # Only students on the user's roster.
        self.assertEqual(self.client.get(url, {"ids": str(self.outsider.id)}).status_code, 403)
        self.assertEqual(self.client.get(url, {"ids": "nope"}).status_code, 400)

    def test_roster_shows_withdrawn_media_consent_as_no(self):
        from django.utils import timezone

        from apps.users.consent_form import CURRENT_VERSION
        from apps.users.models import GuardianConsent, StudentProfile

        withdrawn_at = timezone.now()
        GuardianConsent.objects.create(
            student=StudentProfile.objects.get(user=self.student),
            guardian_full_name="Pat Parent",
            guardian_email="pat@example.com",
            media_consent=True,
            media_withdrawn_at=withdrawn_at,
            signature_png=b"",
            consent_version=CURRENT_VERSION,
        )
        self.client.force_login(self.supervisor)
        row = self.client.get("/api/v1/users/supervised-students/").json()[0]
        self.assertFalse(row["media_consent"])
        # Answered no when it was withdrawn.
        self.assertEqual(parse_datetime(row["media_consent_at"]), withdrawn_at)

    def test_roster_includes_country_and_state(self):
        from apps.groups.models import Countries, CountryStates

        australia = Countries.objects.create(country_name="Australia")
        self.student.country = australia
        self.student.state = CountryStates.objects.create(country=australia, state_name="NSW")
        self.student.save(update_fields=["country", "state"])
        self.client.force_login(self.supervisor)
        row = self.client.get("/api/v1/users/supervised-students/").json()[0]
        self.assertEqual((row["country_name"], row["state_name"]), ("Australia", "NSW"))

    def test_non_supervisor_is_forbidden(self):
        self.client.force_login(self.outsider)
        response = self.client.get("/api/v1/users/supervised-students/")
        self.assertEqual(response.status_code, 403)

    def _admin_and_another_supervisors_student(self):
        from apps.users.models import AdminScope, StudentProfile, SupervisorProfile

        admin = User.objects.create_user(email="admin-guardians@test.com", password="Testpass123!", is_active=True)
        AdminScope.objects.create(user=admin)
        other_supervisor = User.objects.create_user(email="other-sup@test.com", password="Testpass123!")
        other_profile = SupervisorProfile.objects.create(user=other_supervisor, school_name="Other High")
        other_student = User.objects.create_user(
            email="other-student@test.com", first_name="Olly", last_name="Other", password="Testpass123!",
        )
        StudentProfile.objects.create(
            user=other_student, pg_first_name="Olly", pg_last_name="Other",
            supervisor=other_profile, school_name="Other High", year_lvl="10",
        )
        return admin, other_student

    def test_admin_lists_every_supervisors_students(self):
        admin, other_student = self._admin_and_another_supervisors_student()
        self.client.force_login(admin)
        response = self.client.get("/api/v1/users/supervised-students/")
        self.assertEqual(response.status_code, 200)
        emails = sorted(row["email"] for row in response.json())
        self.assertEqual(emails, ["other-student@test.com", "student@test.com"])

    def test_admin_can_record_any_students_guardian(self):
        from apps.users.models import StudentProfile

        admin, other_student = self._admin_and_another_supervisors_student()
        self.client.force_login(admin)
        response = self.client.patch(
            "/api/v1/users/supervised-students/",
            {
                "student_ids": [other_student.id],
                "pg_first_name": "Pat",
                "pg_last_name": "Parent",
                "pg_email": "pat.other@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StudentProfile.objects.get(user=other_student).pg_email, "pat.other@example.com")

    def test_supervisor_still_sees_only_their_own_students(self):
        self._admin_and_another_supervisors_student()
        self.client.force_login(self.supervisor)
        emails = [row["email"] for row in self.client.get("/api/v1/users/supervised-students/").json()]
        self.assertEqual(emails, ["student@test.com"])

    def test_supervisor_can_change_a_students_country_and_region(self):
        from apps.groups.models import Countries, CountryStates

        australia = Countries.objects.create(country_name="Australia")
        nsw = CountryStates.objects.create(country=australia, state_name="NSW")
        nz = Countries.objects.create(country_name="New Zealand")
        self.client.force_login(self.supervisor)
        url = f"/api/v1/users/supervised-students/{self.student.id}/"
        base = {"first_name": "Alex", "last_name": "Student", "school_name": "Test High", "year_lvl": "11"}

        response = self.client.patch(url, {**base, "country_id": australia.id, "state_id": nsw.id}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()["country_name"], response.json()["state_name"]), ("Australia", "NSW"))

        mismatch = self.client.patch(url, {**base, "country_id": nz.id, "state_id": nsw.id}, format="json")
        self.assertEqual(mismatch.status_code, 400)

        options = self.client.get("/api/v1/users/supervised-students/options/").json()
        self.assertIn({"id": australia.id, "country_name": "Australia"}, options["countries"])

    def test_supervisor_can_change_only_their_own_name(self):
        self.client.force_login(self.supervisor)
        response = self.client.patch(
            "/api/v1/users/me/", {"first_name": " Samantha ", "last_name": "Super"}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.supervisor.refresh_from_db()
        self.assertEqual((self.supervisor.first_name, self.supervisor.last_name), ("Samantha", "Super"))

        blank = self.client.patch("/api/v1/users/me/", {"first_name": ""}, format="json")
        self.assertEqual(blank.status_code, 400)
        school = self.client.patch("/api/v1/users/me/", {"school_name": "Elsewhere"}, format="json")
        self.assertEqual(school.status_code, 400)

    def test_supervisor_can_record_guardian_details(self):
        self.client.force_login(self.supervisor)
        response = self.client.patch(
            "/api/v1/users/supervised-students/",
            {
                "student_ids": [self.student.id],
                "pg_first_name": "Jordan",
                "pg_last_name": "Guardian",
                "pg_email": "jordan@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.json() if item["email"] == "student@test.com")
        self.assertEqual(row["pg_first_name"], "Jordan")
        self.assertEqual(row["pg_last_name"], "Guardian")
        self.assertEqual(row["pg_email"], "jordan@example.com")
        self.assertTrue(row["parent_guardian_flag"])

    def test_supervisor_cannot_update_unlinked_student(self):
        self.client.force_login(self.supervisor)
        response = self.client.patch(
            "/api/v1/users/supervised-students/",
            {
                "student_ids": [self.outsider.id],
                "pg_first_name": "Nope",
                "pg_last_name": "Nope",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_supervisor_can_edit_name_and_email_before_permission(self):
        self.client.force_login(self.supervisor)
        response = self.client.patch(
            f"/api/v1/users/supervised-students/{self.student.id}/",
            {
                "first_name": "Alexa",
                "last_name": "Student",
                "email": "alexa.student@test.com",
                "school_name": "Test High",
                "year_lvl": "12",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        row = response.json()
        self.assertEqual(row["first_name"], "Alexa")
        self.assertEqual(row["email"], "alexa.student@test.com")
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "alexa.student@test.com")

    def test_supervisor_cannot_reuse_another_account_email(self):
        self.client.force_login(self.supervisor)
        response = self.client.patch(
            f"/api/v1/users/supervised-students/{self.student.id}/",
            {
                "first_name": "Alex",
                "last_name": "Student",
                "email": self.outsider.email,
                "school_name": "Test High",
                "year_lvl": "11",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_supervisor_cannot_set_student_email_to_guardian_email(self):
        from apps.users.models import StudentProfile

        profile = StudentProfile.objects.get(user=self.student)
        profile.pg_email = "pat.parent@test.com"
        profile.save(update_fields=["pg_email"])
        self.client.force_login(self.supervisor)
        response = self.client.patch(
            f"/api/v1/users/supervised-students/{self.student.id}/",
            {
                "first_name": "Alex",
                "last_name": "Student",
                "email": "pat.parent@test.com",
                "school_name": "Test High",
                "year_lvl": "11",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_supervisor_cannot_set_guardian_email_to_student_email(self):
        self.client.force_login(self.supervisor)
        response = self.client.patch(
            "/api/v1/users/supervised-students/",
            {
                "student_ids": [self.student.id],
                "pg_first_name": "Pat",
                "pg_last_name": "Parent",
                "pg_email": self.student.email,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_supervisor_can_edit_permitted_student_profile(self):
        from apps.users.models import StudentProfile, UserInterest

        profile = StudentProfile.objects.get(user=self.student)
        profile.has_join_permission = True
        profile.save(update_fields=["has_join_permission"])

        self.client.force_login(self.supervisor)
        response = self.client.patch(
            f"/api/v1/users/supervised-students/{self.student.id}/",
            {
                "first_name": "Alexa",
                "last_name": "Updated",
                "school_name": "Waterpark High School",
                "year_lvl": "12",
                "interests": ["Robotics", "Genomics"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        row = response.json()
        self.assertEqual(row["first_name"], "Alexa")
        self.assertEqual(row["last_name"], "Updated")
        self.assertEqual(row["school_name"], "Waterpark High School")
        self.assertEqual(row["year_lvl"], "12")
        self.assertEqual(sorted(row["interests"]), ["Genomics", "Robotics"])
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Alexa")
        self.assertEqual(
            sorted(UserInterest.objects.filter(user=self.student).values_list("interest__interest_desc", flat=True)),
            ["Genomics", "Robotics"],
        )

    def test_supervisor_cannot_edit_unlinked_student_profile(self):
        self.client.force_login(self.supervisor)
        response = self.client.patch(
            f"/api/v1/users/supervised-students/{self.outsider.id}/",
            {
                "first_name": "Nope",
                "last_name": "Nope",
                "school_name": "Test High",
                "year_lvl": "11",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)



@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_BASE_URL="https://connect.example.com",
)
class SupervisedStudentEmailViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.supervisor = User.objects.create_user(
            email="supervisor-mail@test.com",
            first_name="Sam",
            last_name="Supervisor",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        from apps.users.models import StudentProfile, SupervisorProfile

        self.sup_profile = SupervisorProfile.objects.create(
            user=self.supervisor, school_name="Test High"
        )
        self.pending_details = User.objects.create_user(
            email="needs-details@test.com",
            first_name="Alex",
            last_name="Student",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        StudentProfile.objects.create(
            user=self.pending_details,
            pg_first_name="Alex",
            pg_last_name="Student",
            parent_guardian_flag=False,
            supervisor=self.sup_profile,
            school_name="Test High",
            year_lvl="11",
        )
        self.pending_consent = User.objects.create_user(
            email="needs-consent@test.com",
            first_name="Blake",
            last_name="Student",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        StudentProfile.objects.create(
            user=self.pending_consent,
            pg_first_name="Pat",
            pg_last_name="Parent",
            pg_email="pat@example.com",
            parent_guardian_flag=True,
            supervisor=self.sup_profile,
            school_name="Test High",
            year_lvl="10",
        )
        self.outsider = User.objects.create_user(
            email="outsider-mail@test.com",
            first_name="Out",
            last_name="Sider",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )

    def _post(self, student_ids, kind, user=None):
        self.client.force_login(user or self.supervisor)
        return self.client.post(
            "/api/v1/users/supervised-students/email/",
            {"student_ids": student_ids, "kind": kind},
            format="json",
        )

    def test_supervisor_can_email_student_for_guardian_details(self):
        from django.core import mail

        response = self._post([self.pending_details.id], "guardian_details")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sent"], 1)
        self.assertEqual(mail.outbox[0].to, ["needs-details@test.com"])
        self.assertIn("Parent/Guardian Contact", mail.outbox[0].subject)
        self.assertIn(
            "https://connect.example.com/#/profile?guardian=edit",
            mail.outbox[0].alternatives[0][0],
        )

    def test_supervisor_can_email_guardian_for_consent(self):
        from django.core import mail

        response = self._post([self.pending_consent.id], "guardian_consent")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sent"], 1)
        self.assertEqual(mail.outbox[0].to, ["pat@example.com"])
        self.assertIn("permission form", mail.outbox[0].subject.lower())

    def test_email_all_sends_each_selected_student(self):
        from django.core import mail

        second = User.objects.create_user(
            email="also-needs-details@test.com",
            first_name="Casey",
            last_name="Student",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        from apps.users.models import StudentProfile

        StudentProfile.objects.create(
            user=second,
            pg_first_name="Casey",
            pg_last_name="Student",
            parent_guardian_flag=False,
            supervisor=self.sup_profile,
            school_name="Test High",
            year_lvl="9",
        )
        response = self._post(
            [self.pending_details.id, second.id],
            "guardian_details",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sent"], 2)
        self.assertEqual(
            sorted(message.to[0] for message in mail.outbox),
            ["also-needs-details@test.com", "needs-details@test.com"],
        )

    def test_skips_details_email_when_guardian_already_on_file(self):
        response = self._post([self.pending_consent.id], "guardian_details")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["sent"], 0)
        self.assertIn("already has a guardian email", response.json()["msg"])

    def test_non_supervisor_is_forbidden(self):
        response = self._post([self.pending_details.id], "guardian_details", user=self.outsider)
        self.assertEqual(response.status_code, 403)

    def test_cannot_email_unlinked_student(self):
        response = self._post([self.outsider.id], "guardian_details")
        self.assertEqual(response.status_code, 403)

    def _links(self, student_ids, user=None):
        self.client.force_login(user or self.supervisor)
        return self.client.post(
            "/api/v1/users/supervised-students/consent-links/",
            {"student_ids": student_ids},
            format="json",
        )

    def test_consent_link_opens_the_consent_form(self):
        from apps.users import guardian_consent

        response = self._links([self.pending_consent.id])
        self.assertEqual(response.status_code, 200)
        link = response.json()["links"][0]["link"]
        self.assertTrue(link.startswith("https://connect.example.com/#/consent/"))
        token = link.rsplit("/", 1)[1]
        request = guardian_consent.open_request(token)
        self.assertEqual(request.guardian_email, "pat@example.com")

    def test_consent_link_is_given_again_while_it_works(self):
        first = self._links([self.pending_consent.id]).json()["links"][0]["link"]
        second = self._links([self.pending_consent.id]).json()["links"][0]["link"]
        self.assertEqual(first, second)

    def test_consent_link_reuses_the_emailed_link(self):
        from django.core import mail

        self._post([self.pending_consent.id], "guardian_consent")
        link = self._links([self.pending_consent.id]).json()["links"][0]["link"]
        self.assertIn(link, mail.outbox[0].alternatives[0][0])

    def test_consent_link_is_new_once_the_old_one_has_expired(self):
        from django.utils import timezone

        from apps.users.models import GuardianConsentRequest

        first = self._links([self.pending_consent.id]).json()["links"][0]["link"]
        GuardianConsentRequest.objects.update(expires_at=timezone.now())
        second = self._links([self.pending_consent.id]).json()["links"][0]["link"]
        self.assertNotEqual(first, second)

    def test_no_consent_link_without_a_guardian_email(self):
        response = self._links([self.pending_details.id])
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(response.json()["links"][0]["link"])
        self.assertIn("no guardian email", response.json()["msg"])

    def test_consent_links_only_for_own_students(self):
        self.assertEqual(self._links([self.outsider.id]).status_code, 403)
        self.assertEqual(self._links([self.pending_consent.id], user=self.outsider).status_code, 403)

    def _details_link(self, student_id):
        self.client.force_login(self.supervisor)
        response = self.client.post(
            "/api/v1/users/supervised-students/details-links/",
            {"student_ids": [student_id]},
            format="json",
        )
        return response

    def _details_token(self):
        link = self._details_link(self.pending_details.id).json()["links"][0]["link"]
        self.assertTrue(link.startswith("https://connect.example.com/#/guardian-details/"))
        self.client.logout()
        return link.rsplit("/", 1)[1]

    def test_details_form_shows_the_student(self):
        token = self._details_token()
        response = self.client.get(f"/api/v1/guardian-details/{token}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["studentName"], "Alex Student")

    def test_details_form_saves_the_guardian_and_sends_the_consent_form(self):
        from django.core import mail

        from apps.users.models import StudentProfile

        token = self._details_token()
        response = self.client.post(
            f"/api/v1/guardian-details/{token}/",
            {"firstName": "Jamie", "lastName": "Parent", "email": "Jamie@Example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        profile = StudentProfile.objects.get(user=self.pending_details)
        self.assertEqual(
            (profile.pg_first_name, profile.pg_last_name, profile.pg_email),
            ("Jamie", "Parent", "jamie@example.com"),
        )
        self.assertIn(["jamie@example.com"], [message.to for message in mail.outbox])
        # Once given, the link has done its job.
        self.assertEqual(self.client.get(f"/api/v1/guardian-details/{token}/").status_code, 410)

    def test_details_form_names_the_wrong_field(self):
        token = self._details_token()
        url = f"/api/v1/guardian-details/{token}/"
        bad_email = self.client.post(
            url, {"firstName": "Jamie", "lastName": "Parent", "email": "jamie@example"}, format="json",
        )
        self.assertEqual(bad_email.status_code, 400)
        self.assertEqual(bad_email.json()["badFields"], ["email"])
        self.assertIn("full email address", bad_email.json()["error"])
        no_last_name = self.client.post(
            url, {"firstName": "Jamie", "lastName": "", "email": "jamie@example.com"}, format="json",
        )
        self.assertEqual(no_last_name.json()["error"], "Please enter the last name.")

    def test_details_form_refuses_the_students_own_email(self):
        token = self._details_token()
        response = self.client.post(
            f"/api/v1/guardian-details/{token}/",
            {"firstName": "Alex", "lastName": "Student", "email": "needs-details@test.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_details_form_link_expires(self):
        from datetime import timedelta
        from unittest import mock

        token = self._details_token()
        with mock.patch("apps.users.guardian_details.FORM_LINK_LIFETIME", timedelta(seconds=-1)):
            response = self.client.get(f"/api/v1/guardian-details/{token}/")
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()["code"], "details_link_expired")

    def test_details_form_rejects_a_made_up_link(self):
        response = self.client.get("/api/v1/guardian-details/not-a-real-token/")
        self.assertEqual(response.status_code, 404)

    def _upload(self, text, dry_run=True, name="guardians.csv"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.supervisor)
        return self.client.post(
            "/api/v1/users/supervised-students/guardian-upload/",
            {"file": SimpleUploadedFile(name, text.encode()), "dry_run": "true" if dry_run else "false"},
            format="multipart",
        )

    UPLOAD_HEADER = "student_email,guardian_first_name,guardian_last_name,guardian_email\n"

    def test_guardian_upload_previews_then_saves(self):
        from apps.users.models import StudentProfile

        sheet = self.UPLOAD_HEADER + (
            "needs-details@test.com,Jamie,Parent,jamie@example.com\n"
            "needs-consent@test.com,Pat,Parent,pat.new@example.com\n"
        )
        preview = self._upload(sheet).json()
        self.assertEqual(preview["summary"], {"creates": 1, "updates": 1, "unchanged": 0, "errors": 0})
        self.assertEqual(StudentProfile.objects.get(user=self.pending_details).pg_email or "", "")

        applied = self._upload(sheet, dry_run=False)
        self.assertEqual(applied.status_code, 200)
        self.assertEqual(applied.json()["saved"], 2)
        self.assertEqual(StudentProfile.objects.get(user=self.pending_details).pg_email, "jamie@example.com")
        self.assertEqual(StudentProfile.objects.get(user=self.pending_consent).pg_email, "pat.new@example.com")

    def test_guardian_upload_reports_each_problem_and_saves_nothing(self):
        from apps.users.models import StudentProfile

        sheet = self.UPLOAD_HEADER + (
            "needs-details@test.com,Jamie,,jamie@example\n"
            "outsider-mail@test.com,Out,Sider,out@example.com\n"
        )
        checks = self._upload(sheet).json()["checks"]
        self.assertEqual(checks["bad_rows"], [{"row": 2, "reason": "guardian_last_name, guardian_email not an email"}])
        self.assertEqual(checks["unknown_students"], [{"row": 3, "email": "outsider-mail@test.com"}])
        self.assertEqual(self._upload(sheet, dry_run=False).status_code, 400)
        self.assertEqual(StudentProfile.objects.get(user=self.pending_details).pg_email or "", "")

    def test_guardian_upload_checks_the_headers(self):
        checks = self._upload("student_email,guardian_email\nx@test.com,y@test.com\n").json()["checks"]
        self.assertEqual(checks["missing_headers"], ["guardian_first_name", "guardian_last_name"])

    def test_guardian_upload_is_for_supervisors(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.outsider)
        response = self.client.post(
            "/api/v1/users/supervised-students/guardian-upload/",
            {"file": SimpleUploadedFile("g.csv", self.UPLOAD_HEADER.encode())},
            format="multipart",
        )
        self.assertEqual(response.status_code, 403)

    def test_no_details_link_once_a_guardian_email_is_on_file(self):
        response = self._details_link(self.pending_consent.id)
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(response.json()["links"][0]["link"])


class MeGuardianDetailsTests(TestCase):
    """/users/me/ carries the guardian details shown on the student profile."""

    def setUp(self):
        from apps.resources.models import RoleAssignmentHistory
        from apps.users.models import StudentProfile

        self.client = APIClient()
        self.student = User.objects.create_user(
            email="guardian-view@test.com",
            first_name="Alex",
            last_name="Student",
            account_status=User.AccountStatus.ACTIVE,
        )
        RoleAssignmentHistory.objects.create(
            user=self.student,
            role=Roles.objects.create(role_name=ROLE_STUDENT),
            valid_from=timezone.now() - timedelta(days=1),
        )
        self.profile = StudentProfile.objects.create(
            user=self.student,
            pg_first_name="Pat",
            pg_last_name="Parent",
            pg_email="pat.parent@test.com",
            parent_guardian_flag=True,
            school_name="Test High",
            year_lvl="11",
        )
        self.client.force_authenticate(user=self.student)
        self.url = reverse("MeListHTMLView")

    def test_returns_guardian_details_without_consent(self):
        data = self.client.get(self.url).json()

        self.assertEqual(data["pg_firstname"], "Pat")
        self.assertEqual(data["pg_lastname"], "Parent")
        self.assertEqual(data["pg_email"], "pat.parent@test.com")
        self.assertFalse(data["join_perm"])
        self.assertIsNone(data["join_perm_granted_at"])

    def test_returns_when_consent_was_granted(self):
        granted_at = timezone.now() - timedelta(days=3)
        self.profile.has_join_permission = True
        self.profile.joinperm_granted_at = granted_at
        self.profile.save()

        data = self.client.get(self.url).json()

        self.assertTrue(data["join_perm"])
        self.assertEqual(data["join_perm_granted_at"], granted_at.isoformat())

    def test_guardian_fields_are_null_for_non_students(self):
        mentor = User.objects.create_user(
            email="mentor-guardian@test.com",
            account_status=User.AccountStatus.ACTIVE,
        )
        self.client.force_authenticate(user=mentor)

        data = self.client.get(self.url).json()

        self.assertIsNone(data["pg_email"])
        self.assertIsNone(data["join_perm_granted_at"])


class MeGuardianUpdateTests(TestCase):
    """Students update their guardian: a new guardian replaces the old one at
    once, and clears permission they'd already given until the new one signs."""

    def setUp(self):
        from apps.resources.models import RoleAssignmentHistory
        from apps.users.models import StudentProfile

        self.client = APIClient()
        self.student = User.objects.create_user(
            email="guardian-edit@test.com",
            first_name="Alex",
            last_name="Student",
            account_status=User.AccountStatus.ACTIVE,
        )
        RoleAssignmentHistory.objects.create(
            user=self.student,
            role=Roles.objects.create(role_name=ROLE_STUDENT),
            valid_from=timezone.now() - timedelta(days=1),
        )
        self.profile = StudentProfile.objects.create(
            user=self.student,
            pg_first_name="Pat",
            pg_last_name="Parent",
            pg_email="pat.parent@test.com",
            parent_guardian_flag=True,
            school_name="Test High",
            year_lvl="11",
        )
        self.client.force_authenticate(user=self.student)
        self.url = reverse("me-guardian")
        self.new_guardian = {
            "first_name": "Robin",
            "last_name": "Carer",
            "email": "Robin.Carer@test.com",
        }

    def _grant_consent(self):
        self.granted_at = timezone.now() - timedelta(days=10)
        self.profile.has_join_permission = True
        self.profile.joinperm_responseID = "R_old"
        self.profile.joinperm_granted_at = self.granted_at
        self.profile.save()

    def _post_consent(self, response_id):
        with self.settings(JOIN_PERMISSION_WEBHOOK_TOKEN="secret-token"):
            return self.client.post(
                reverse("join_perm"),
                {"body": {"Email": self.student.email, "ResponseID": response_id}},
                format="json",
                HTTP_X_JOIN_PERMISSION_TOKEN="secret-token",
            )

    def test_before_consent_the_change_applies_straight_away(self):
        self.profile.parent_guardian_flag = False
        self.profile.save()

        response = self.client.put(self.url, self.new_guardian, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.pg_first_name, "Robin")
        self.assertEqual(self.profile.pg_email, "robin.carer@test.com")
        self.assertTrue(self.profile.parent_guardian_flag)
        self.assertFalse(self.profile.has_pending_guardian)
        self.assertIsNone(response.json()["pending_guardian"])

    def test_changing_the_guardian_after_consent_clears_permission(self):
        self._grant_consent()

        response = self.client.put(self.url, self.new_guardian, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.pg_first_name, "Robin")
        self.assertEqual(self.profile.pg_email, "robin.carer@test.com")
        self.assertFalse(self.profile.has_join_permission)
        self.assertIsNone(self.profile.joinperm_granted_at)
        self.assertIsNone(self.profile.media_consent)
        self.assertFalse(self.profile.has_pending_guardian)
        self.assertIsNone(response.json()["pending_guardian"])

    def _managed_by_supervisor(self):
        from apps.users.models import StudentProfile

        self.profile.registered_by = StudentProfile.RegisteredBy.SUPERVISOR
        self.profile.save()

    def test_a_supervisors_student_cant_change_a_guardian_who_gave_permission(self):
        self._managed_by_supervisor()
        self._grant_consent()

        response = self.client.put(self.url, self.new_guardian, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Contact BIOTech Support", str(response.data))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.pg_first_name, "Pat")
        self.assertTrue(self.profile.has_join_permission)
        self.assertTrue(self.client.get(reverse("MeListHTMLView")).json()["guardian_locked"])

    def test_while_permission_is_pending_a_supervisors_student_still_can(self):
        self._managed_by_supervisor()

        self.assertFalse(self.client.get(reverse("MeListHTMLView")).json()["guardian_locked"])
        response = self.client.put(self.url, self.new_guardian, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.pg_first_name, "Robin")

    def test_saving_the_same_guardian_keeps_permission(self):
        self._grant_consent()
        self.profile.refresh_from_db()
        same = {
            "first_name": self.profile.pg_first_name, "last_name": self.profile.pg_last_name,
            "email": self.profile.pg_email,
        }

        self.client.put(self.url, same, format="json")

        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_join_permission)
        self.assertEqual(self.profile.joinperm_granted_at, self.granted_at)

    def test_new_guardians_consent_replaces_the_old_guardian(self):
        self._grant_consent()
        self.client.put(self.url, self.new_guardian, format="json")

        response = self._post_consent("R_new")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.pg_first_name, "Robin")
        self.assertEqual(self.profile.pg_last_name, "Carer")
        self.assertEqual(self.profile.pg_email, "robin.carer@test.com")
        self.assertFalse(self.profile.has_pending_guardian)
        self.assertEqual(self.profile.joinperm_responseID, "R_new")
        self.assertGreater(self.profile.joinperm_granted_at, self.granted_at)

    def test_resubmitting_the_consenting_guardian_drops_the_pending_change(self):
        self._grant_consent()
        self.client.put(self.url, self.new_guardian, format="json")

        self.client.put(
            self.url,
            {"first_name": "Pat", "last_name": "Parent", "email": "PAT.parent@test.com"},
            format="json",
        )

        self.profile.refresh_from_db()
        self.assertFalse(self.profile.has_pending_guardian)

    def test_withdrawing_a_pending_change(self):
        # A change still held as pending from before changes cleared permission.
        self._grant_consent()
        self.profile.refresh_from_db()
        self.profile.pending_pg_first_name = "Robin"
        self.profile.pending_pg_last_name = "Carer"
        self.profile.pending_pg_email = "robin.carer@test.com"
        self.profile.pending_pg_requested_at = timezone.now()
        self.profile.save()

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.has_pending_guardian)
        self.assertEqual(self.profile.pg_first_name, "Pat")

    def test_student_cannot_use_their_own_email(self):
        response = self.client.put(
            self.url,
            {**self.new_guardian, "email": "Guardian-Edit@test.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.pg_first_name, "Pat")

    def test_all_fields_are_required(self):
        response = self.client.put(
            self.url, {"first_name": "Robin", "last_name": "", "email": ""}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_student_is_forbidden(self):
        mentor = User.objects.create_user(
            email="mentor-guardian-edit@test.com",
            account_status=User.AccountStatus.ACTIVE,
        )
        self.client.force_authenticate(user=mentor)

        response = self.client.put(self.url, self.new_guardian, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class RegistrationThenConsentTests(TestCase):
    """A self-registered student must be able to receive consent through the
    webhook. Registration used to leave ``parent_guardian_flag`` False unless
    the guardian's email matched the supervisor's, so the consent save hit the
    ``permission_requires_parent_guardian`` constraint and the webhook 500'd."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

        self.client = APIClient()
        for name in [ROLE_STUDENT, ROLE_SUPERVISOR]:
            Roles.objects.get_or_create(role_name=name)
        payload = {
            "body": {
                "Title": "kid@example.com",
                "FirstName": "Kid",
                "Surname": "Student",
                "Country": "Australia",
                "Region": "NSW",
                "SupervisorEmail": "sup@example.com",
                "SupervisorFirstName": "Sam",
                "SupervisorSurname": "Super",
                "GuardianEmail": " Parent@Example.com ",
                "GuardianName": "Pat",
                "GuardianSurname": "Parent",
                "SchoolName": "Test High",
                "YearLevel": "10",
                "Areaofinterest": "Biotechnology",
            }
        }
        response = self.client.post(reverse("registration"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        from apps.users.models import StudentProfile
        self.profile = StudentProfile.objects.get(user__email="kid@example.com")

    def _post_consent(self):
        with self.settings(JOIN_PERMISSION_WEBHOOK_TOKEN="secret-token"):
            return self.client.post(
                reverse("join_perm"),
                {"body": {"Email": "kid@example.com", "ResponseID": "R_reg"}},
                format="json",
                HTTP_X_JOIN_PERMISSION_TOKEN="secret-token",
            )

    def test_registration_records_the_guardian(self):
        self.assertEqual(self.profile.pg_first_name, "Pat")
        self.assertEqual(self.profile.pg_last_name, "Parent")
        self.assertEqual(self.profile.pg_email, "parent@example.com")
        self.assertTrue(self.profile.parent_guardian_flag)
        self.assertFalse(self.profile.has_join_permission)

    def test_consent_is_recorded_for_a_registered_student(self):
        response = self._post_consent()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_join_permission)
        self.assertEqual(self.profile.joinperm_responseID, "R_reg")

    def test_consent_is_recorded_for_a_student_registered_before_the_fix(self):
        # Rows already stored with the flag off must not crash the webhook.
        self.profile.parent_guardian_flag = False
        self.profile.save()

        response = self._post_consent()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_join_permission)
        self.assertTrue(self.profile.parent_guardian_flag)
