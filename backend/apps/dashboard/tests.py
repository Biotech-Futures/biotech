from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


def _make_group(**overrides):
    """Build a lightweight stand-in for an annotated ``Groups`` instance."""
    defaults = {
        "id": 1,
        "group_name": "BTF046",
        "track_id": 1,
        "track": SimpleNamespace(track_name="AUS-NSW"),
        "member_count": 4,
        "lead_user_id": 3,
        "lead_first_name": "Anita",
        "lead_last_name": "Pickard",
        "deleted_at": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class GroupsPreviewViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "/dashboard/v1/groups-preview/"

        self.user = User.objects.create_user(
            email="test@test.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    def test_unauthenticated_returns_403(self):
        """Unauthenticated users should be blocked."""
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.dashboard.views.get_groups_preview")
    def test_returns_paginated_response(self, mock_service):
        """Response should have the flattened UI-specific shape."""
        mock_service.return_value = [_make_group(id=12)]

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertIn("next", data)
        self.assertIn("previous", data)
        self.assertEqual(data["count"], 1)

        row = data["results"][0]
        self.assertEqual(row["id"], 12)
        self.assertEqual(row["group_name"], "BTF046")
        self.assertEqual(row["track_id"], 1)
        self.assertEqual(row["track_name"], "AUS-NSW")
        self.assertEqual(row["member_count"], 4)
        self.assertEqual(
            row["lead_user"],
            {"id": 3, "first_name": "Anita", "last_name": "Pickard"},
        )
        self.assertEqual(row["lead_name"], "Anita Pickard")
        self.assertEqual(row["status"], "active")

    @patch("apps.dashboard.views.get_groups_preview")
    def test_lead_user_null_when_no_mentor(self, mock_service):
        """Groups without an active mentor expose a null lead."""
        mock_service.return_value = [
            _make_group(lead_user_id=None, lead_first_name=None, lead_last_name=None)
        ]

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        row = response.json()["results"][0]
        self.assertIsNone(row["lead_user"])
        self.assertIsNone(row["lead_name"])

    @patch("apps.dashboard.views.get_groups_preview")
    def test_mine_param_passed_to_service(self, mock_service):
        """mine=true query param should be passed to service as True."""
        mock_service.return_value = []

        self.client.get(self.url + "?mine=true")
        mock_service.assert_called_once_with(user=self.user, mine=True, track_id=None)

    @patch("apps.dashboard.views.get_groups_preview")
    def test_mine_false_by_default(self, mock_service):
        """mine should default to False if not provided."""
        mock_service.return_value = []

        self.client.get(self.url)
        mock_service.assert_called_once_with(user=self.user, mine=False, track_id=None)

    @patch("apps.dashboard.views.get_groups_preview")
    def test_track_id_param_passed_to_service(self, mock_service):
        """track_id query param should be coerced to int and forwarded."""
        mock_service.return_value = []

        self.client.get(self.url + "?track_id=1")
        mock_service.assert_called_once_with(user=self.user, mine=False, track_id=1)

    def test_track_id_must_be_integer(self):
        """A non-integer track_id should yield 400."""
        response = self.client.get(self.url + "?track_id=abc")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.dashboard.views.get_groups_preview")
    def test_pagination_page_size(self, mock_service):
        """page_size param should control number of results returned."""
        mock_service.return_value = [
            _make_group(id=i, group_name=f"Group{i}", lead_user_id=None,
                        lead_first_name=None, lead_last_name=None)
            for i in range(10)
        ]

        response = self.client.get(self.url + "?page_size=3")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 3)
        self.assertEqual(data["count"], 10)
        self.assertIsNotNone(data["next"])

    @patch("apps.dashboard.views.get_groups_preview")
    def test_empty_results(self, mock_service):
        """Empty group list should return valid paginated response."""
        mock_service.return_value = []

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["results"], [])
