from django.test import TestCase

from datetime import date, datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.apps import apps as dj_apps

from .models import Roles, RoleAssignmentHistory

# Create your tests here.


class RolesApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()

        # Auth user to hit endpoints guarded by IsAuthenticated
        self.me = User.objects.create_user(username="me@example.com", password="pw12345")

        # Some roles (unordered on purpose to check ordering in response)
        self.viewer = Roles.objects.create(role_name="viewer")
        self.admin = Roles.objects.create(role_name="admin")

    def test_roles_requires_auth(self):
        url = reverse("roles-list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_roles_list_ok_and_ordered(self):
        self.client.force_authenticate(self.me)
        url = reverse("roles-list")  # -> /resources/roles/ with your current config
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data), 2)
        # Should be ordered by role_name per view
        self.assertEqual([r["role_name"] for r in data], ["admin", "viewer"])


class RoleAssignmentsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Auth user (whatever your AUTH_USER_MODEL is)
        AuthUser = get_user_model()
        self.me = AuthUser.objects.create_user(username="me", password="pw12345")
        self.client.force_authenticate(self.me)

        # Assignment users must be from your custom users app
        # Users = dj_apps.get_model('users', 'Users')
        # try:
        #     self.u1 = Users.objects.create_user(username="u1", email="u1@example.com", password="pw")
        #     self.u2 = Users.objects.create_user(username="u2", email="u2@example.com", password="pw")
        # except TypeError:
        #     try:
        #         self.u1 = Users.objects.create_user(email="u1@example.com", password="pw")
        #         self.u2 = Users.objects.create_user(email="u2@example.com", password="pw")
        #     except Exception:
        #         self.u1 = Users.objects.create(email="u1@example.com", username="u1")
        #         self.u2 = Users.objects.create(email="u2@example.com", username="u2")
        Users = dj_apps.get_model('users', 'Users')
        Countries = dj_apps.get_model('groups', 'Countries')
        CountryStates = dj_apps.get_model('groups', 'CountryStates')
        Tracks = dj_apps.get_model('groups', 'Tracks')

        # Step 1: Minimal chain to satisfy FKs
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        track = Tracks.objects.create(track_name="Data Science", state=state)

        self.r_admin = Roles.objects.create(role_name="admin")
        self.r_view  = Roles.objects.create(role_name="viewer")

        # Step 2: Create Users with required fields
        self.u1 = Users.objects.create(
            first_name="Alice",
            last_name="Tester",
            email="u1@example.com",
            track=track,
            state=state,
        )

        self.u2 = Users.objects.create(
            first_name="Bob",
            last_name="Tester",
            email="u2@example.com",
            track=track,
            state=state,
        )

        # Step 3: Create role assignment history (with timezone-aware datetimes)
        self.a1 = RoleAssignmentHistory.objects.create(
            user=self.u1,
            role=self.r_admin,
            valid_from=timezone.make_aware(datetime(2025, 1, 1)),
            valid_to=timezone.make_aware(datetime(2025, 6, 30)),
        )
        self.a2 = RoleAssignmentHistory.objects.create(
            user=self.u1,
            role=self.r_view,
            valid_from=timezone.make_aware(datetime(2025, 7, 1)),
            valid_to=None,
        )
        self.a3 = RoleAssignmentHistory.objects.create(
            user=self.u2,
            role=self.r_view,
            valid_from=timezone.make_aware(datetime(2025, 3, 1)),
            valid_to=timezone.make_aware(datetime(2025, 3, 31)),
        )

    def _get(self, **params):
        url = reverse("role-assignments-list")  # -> /resources/role-assignments/
        return self.client.get(url, params)

    def test_list_all(self):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json()), 3)

    def test_filter_by_user(self):
        resp = self._get(user_id=self.u1.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data), 2)
        # all items belong to u1
        self.assertTrue(all(item["user"]["id"] == self.u1.id or item["user"] == self.u1.id for item in data))

    def test_filter_by_role(self):
        resp = self._get(role_id=self.r_view.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertTrue(all(
            (item.get("role", {}).get("id") == self.r_view.id) or (item.get("role") == self.r_view.id)
            for item in data
        ))

    def test_filter_by_validity_window_overlap(self):
        # Window that overlaps a1 (ends 2025-06-30) and a2 (starts 2025-07-01) differently
        resp = self._get(valid_from="2025-06-15", valid_to="2025-07-15")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in resp.json()}
        # Overlap logic should include a1 (ends after 06-15) and a2 (starts before 07-15)
        self.assertIn(self.a1.id, ids)
        self.assertIn(self.a2.id, ids)

    def test_only_valid_from(self):
        # “still valid on/after” 2025-07-01 should include a2 (open-ended) and exclude a1 (ended 2025-06-30)
        resp = self._get(valid_from="2025-07-01")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in resp.json()}
        self.assertIn(self.a2.id, ids)
        self.assertNotIn(self.a1.id, ids)

    def test_only_valid_to(self):
        # “started on/before” 2025-03-15 → includes a1 (from Jan) and a3 (from Mar 1), may exclude a2 (starts July)
        resp = self._get(valid_to="2025-03-15")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in resp.json()}
        self.assertIn(self.a1.id, ids)
        self.assertIn(self.a3.id, ids)
        self.assertNotIn(self.a2.id, ids)

    def test_invalid_dates_are_ignored(self):
        # parse_date(None/invalid) yields None; our view skips date filters in that case
        resp = self._get(valid_from="not-a-date", valid_to="also-bad")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json()), 3)

    def test_ordering_is_stable(self):
        # Expect ordering by user_id, role_id, valid_from (see view)
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Quick sanity: first element should be the smallest (user_id, role_id, valid_from)
        # Not strict equality check (since PKs depend on DB), but check monotonic non-decreasing triplets
        def key(row):
            # Handle nested vs PK-only serializers gracefully
            user_id = row["user"]["id"] if isinstance(row.get("user"), dict) else row.get("user")
            role_id = row["role"]["id"] if isinstance(row.get("role"), dict) else row.get("role")
            return (user_id, role_id, row["valid_from"])
        keys = [key(r) for r in data]
        self.assertEqual(keys, sorted(keys))