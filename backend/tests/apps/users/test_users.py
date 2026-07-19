from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient

from apps.events.models import Events
from apps.groups.models import Groups
from apps.matching_runtime.models import MatchRecommendation, MatchRun
from apps.users.models import AdminScope
from apps.groups.models import Countries, CountryStates
from apps.resources.models import Roles
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

    def test_supervisor_inherits_the_students_geography(self):
        self._register("Australia", region="NSW")
        sup = User.objects.get(email="sup@example.com")
        student = User.objects.get(email="kid@example.com")
        self.assertEqual(sup.country_id, student.country_id)
        self.assertEqual(sup.state_id, student.state_id)

    def test_country_casing_variant_reuses_the_existing_country(self):
        Countries.objects.create(country_name="Australia")
        self._register("australia", region="NSW")
        user = User.objects.get(email="kid@example.com")
        self.assertEqual(user.country.country_name, "Australia")
        self.assertEqual(Countries.objects.filter(country_name__iexact="australia").count(), 1)
