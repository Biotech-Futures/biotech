from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient

from apps.events.models import Events
from apps.groups.models import Countries, CountryStates, Groups, Tracks
from apps.matching_runtime.models import MatchRecommendation, MatchRun
from apps.users.models import AdminScope


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
        AdminScope.objects.create(user=self.admin_user, is_global=True)

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
        """Operational admin can filter for admin@admin.com"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("UserListHTMLView"), {"email": "admin@admin.com"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin@admin.com')
        self.assertContains(response, 'Admin')

    def test_email_filter_regular_user(self):
        """Operational admin can filter for user@example.com"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("UserListHTMLView"), {"email": "user@example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'user@example.com')
        self.assertContains(response, 'Regular')

    def test_email_filter_nonexistent(self):
        """Operational admin filtering for a non-existent email returns no rows."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("UserListHTMLView"), {"email": "notfound@example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'admin@admin.com')
        self.assertNotContains(response, 'user@example.com')

    def test_no_email_filter(self):
        """Operational admin without a filter sees all users."""
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
        AdminScope.objects.create(user=self.admin_user, is_global=True)
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="OPS-TRACK", state=self.state)

        self.target_user = User.objects.create_user(
            email="target@test.com",
            first_name="Target",
            last_name="User",
            track=self.track,
        )
        self.invited_user = User.objects.create_user(
            email="invited@test.com",
            first_name="Invited",
            last_name="User",
            track=self.track,
        )
        self.group = Groups.objects.create(group_name="Ops Group", track=self.track)
        self.match_run = MatchRun.objects.create(
            initiated_by_user=self.admin_user,
            track=self.track,
            run_type="initial",
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
            is_virtual=True,
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


class UserDetailLockdownTests(TestCase):
    """Regression tests for the legacy ``AllowAny`` on ``UsersRetrieveUpdateView``
    that let any anonymous caller PATCH ``account_status`` / ``role_id`` —
    CONSOLIDATED 1.2."""

    def setUp(self):
        self.client = APIClient()
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="LOCK-TRACK", state=self.state)

        self.admin_user = User.objects.create_user(
            email="admin-lockdown@test.com",
            first_name="Lock",
            last_name="Admin",
            track=self.track,
        )
        AdminScope.objects.create(user=self.admin_user, is_global=True)

        self.target_user = User.objects.create_user(
            email="target-lockdown@test.com",
            first_name="Lock",
            last_name="Target",
            track=self.track,
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
            email="random@test.com", first_name="Random", last_name="User", track=self.track,
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


class ReceiveJoinPermissionTokenTests(TestCase):
    """The legacy ``AllowAny`` on ``ReceiveJoinPermissionView`` let any anonymous
    caller flip ``has_join_permission`` for any student email — CONSOLIDATED 1.2.
    The endpoint now requires a shared-secret HMAC token."""

    def setUp(self):
        from apps.users.models import StudentProfile
        self.client = APIClient()
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="JOIN-TRACK", state=self.state)
        self.student = User.objects.create_user(
            email="student-joinperm@test.com",
            first_name="Join",
            last_name="Student",
            track=self.track,
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
