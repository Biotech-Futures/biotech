from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.admin.services.user import update_user
from apps.groups.models import Countries, CountryStates, Tracks
from apps.resources.models import RoleAssignmentHistory
from apps.users.models import AdminProfile, User
from apps.users.models.admin_scope import AdminScope


class AdminUserServiceTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=state)
        self.user = User.objects.create_user(
            email="supervisor@example.com",
            first_name="Chen",
            last_name="Supervisor",
            password="testpass",
        )

    def test_update_user_assigns_incoming_role_when_current_role_is_missing(self):
        result = update_user(
            self.user.id,
            {
                "firstName": "Chen",
                "lastName": "Supervisor",
                "role": "admin",
                "track": None,
                "adminTracks": ["AUS-NSW"],
                "interests": [],
                "joinPermissionReceived": False,
            },
        )

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertEqual(result["data"]["role"], "admin")
        self.assertEqual(result["data"]["adminTracks"], ["AUS-NSW"])
        self.assertTrue(
            RoleAssignmentHistory.objects.filter(
                user=self.user,
                role__role_name="admin",
                valid_to__isnull=True,
            ).exists()
        )
        self.assertTrue(AdminProfile.objects.filter(admin=self.user).exists())
        self.assertTrue(
            AdminScope.objects.filter(user=self.user, track=self.track).exists()
        )


class AdminUserBulkCreateViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="bulk-admin@example.com",
            first_name="Bulk",
            last_name="Admin",
            password="testpass",
        )
        AdminScope.objects.create(user=self.admin_user, is_global=True)
        self.client.force_authenticate(user=self.admin_user)
        self.url = "/api/v1/admin/user/bulk/"
        self.payload = [
            {
                "firstName": "Ava",
                "lastName": "Nguyen",
                "email": "ava.nguyen@example.com",
                "role": "student",
            }
        ]

    @patch("apps.admin.views.bulk_create_users")
    def test_accepts_json_array_payload(self, mock_bulk_create_users):
        mock_bulk_create_users.return_value = {
            "msg": "Bulk import complete: 1 created, 0 skipped",
            "data": {"created": [], "skipped": []},
        }

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_bulk_create_users.assert_called_once_with(self.payload, "")

    @patch("apps.admin.views.bulk_create_users")
    def test_accepts_wrapped_users_payload_for_compatibility(self, mock_bulk_create_users):
        mock_bulk_create_users.return_value = {
            "msg": "Bulk import complete: 1 created, 0 skipped",
            "data": {"created": [], "skipped": []},
        }

        response = self.client.post(
            self.url,
            {"users": self.payload},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_bulk_create_users.assert_called_once_with(self.payload, "")

    @patch("apps.admin.views.bulk_create_users")
    def test_rejects_non_array_payload(self, mock_bulk_create_users):
        response = self.client.post(self.url, {"email": "bad@example.com"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "Expected a JSON array of users")
        mock_bulk_create_users.assert_not_called()
