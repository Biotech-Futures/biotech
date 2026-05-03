from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient

from apps.events.models import Events
from apps.groups.models import Countries, CountryStates, Groups, Tracks
from apps.matching_runtime.models import MatchRecommendation, MatchRun


User = get_user_model()


class AdminUserEmailFilterTestCase(TestCase):
    """Email filtering should only be exercised through the canonical JSON admin surface."""

    def setUp(self):
        self.client = APIClient()

        # Create admin user
        self.admin_user = User.objects.create_user(
            email="admin@admin.com",
            first_name="Admin",
            last_name="User",
            is_active=True,
            is_staff=True,
        )
        self.client.force_authenticate(user=self.admin_user)

        # Create another user
        self.regular_user = User.objects.create_user(
            email="user@example.com",
            first_name="Regular",
            last_name="User",
            is_active=False,
        )

    def test_email_filter_admin(self):
        response = self.client.get(reverse("user-list"), {"email": "admin@admin.com"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["email"], "admin@admin.com")
        self.assertEqual(response.data["results"][0]["first_name"], "Admin")

    def test_email_filter_regular_user(self):
        response = self.client.get(reverse("user-list"), {"email": "user@example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["email"], "user@example.com")
        self.assertEqual(response.data["results"][0]["first_name"], "Regular")

    def test_email_filter_nonexistent(self):
        response = self.client.get(reverse("user-list"), {"email": "notfound@example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_no_email_filter(self):
        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, 200)
        returned_emails = [item["email"] for item in response.data["results"]]
        self.assertEqual(response.data["count"], 2)
        self.assertCountEqual(returned_emails, ["admin@admin.com", "user@example.com"])

    def test_legacy_html_users_route_is_removed(self):
        response = self.client.get("/users/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminWorkflowApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="ops-admin@test.com",
            password="adminpass123",
            first_name="Ops",
            last_name="Admin",
            is_staff=True,
        )
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="OPS-TRACK", state=self.state)
        self.other_track = Tracks.objects.create(track_name="OPS-TRACK-2", state=self.state)

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
        self.assertIn("track_name", response.data[0])

    def test_admin_summary_returns_operational_counts(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse("admin-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["active_groups"], 1)
        self.assertEqual(response.data["groups_without_mentor"], 1)
        self.assertEqual(response.data["unassigned_match_recommendations"], 1)
        self.assertGreaterEqual(response.data["upcoming_events"], 1)

    def test_admin_user_list_returns_paginated_json_surface(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse("admin-user-list"), {"email": "target@test.com", "page_size": 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["email"], "target@test.com")
        self.assertEqual(response.data["results"][0]["track_name"], self.track.track_name)
        self.assertIn("current_role_name", response.data["results"][0])

    def test_admin_user_detail_patch_updates_status_and_track(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            reverse("user-detail", kwargs={"pk": self.target_user.id}),
            {
                "account_status": User.AccountStatus.ACTIVE,
                "track_id": self.other_track.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.account_status, User.AccountStatus.ACTIVE)
        self.assertEqual(self.target_user.track_id, self.other_track.id)
        self.assertEqual(response.data["track"], self.other_track.id)
        self.assertEqual(response.data["track_name"], self.other_track.track_name)

    def test_admin_user_list_rejects_non_admin(self):
        self.client.force_authenticate(user=self.target_user)
        response = self.client.get(reverse("admin-user-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


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
        self.target_user.account_status = User.AccountStatus.DEACTIVATED
        self.target_user.is_active = False
        self.target_user.save(update_fields=["account_status", "is_active"])

        response = self.client.post(
            reverse("password-login"),
            {"email": self.user_email, "password": self.user_pass},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_legacy_login_route_is_removed(self):
        response = self.client.post(
            "/api/v1/login/",
            {"email": self.user_email, "password": self.user_pass},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
