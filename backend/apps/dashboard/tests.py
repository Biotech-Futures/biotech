
# Create your tests here.
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class GroupsPreviewViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "/dashboard/v1/groups-preview/"

        # Create test user
        self.user = User.objects.create_user(
            email="test@test.com",
            password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_unauthenticated_returns_403(self):
        """Unauthenticated users should be blocked."""
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.dashboard.views.get_groups_preview")
    def test_returns_paginated_response(self, mock_service):
        """Response should have correct paginated shape."""
        mock_service.return_value = [
            {
                "id": 1,
                "name": "BTF046",
                "track_id": 1,
                "track_name": "AUS-NSW",
                "member_count": 4,
                "lead_name": "Anita Pickard",
                "status": "active",
            }
        ]

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIn("count", data)
        self.assertIn("results", data)
        self.assertIn("next", data)
        self.assertIn("previous", data)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "BTF046")
        self.assertEqual(data["results"][0]["track_name"], "AUS-NSW")
        self.assertEqual(data["results"][0]["member_count"], 4)
        self.assertEqual(data["results"][0]["lead_name"], "Anita Pickard")
        self.assertEqual(data["results"][0]["status"], "active")

    @patch("apps.dashboard.views.get_groups_preview")
    def test_mine_param_passed_to_service(self, mock_service):
        """mine=true query param should be passed to service as True."""
        mock_service.return_value = []

        self.client.get(self.url + "?mine=true")
        mock_service.assert_called_once_with(user=self.user, mine=True)

    @patch("apps.dashboard.views.get_groups_preview")
    def test_mine_false_by_default(self, mock_service):
        """mine should default to False if not provided."""
        mock_service.return_value = []

        self.client.get(self.url)
        mock_service.assert_called_once_with(user=self.user, mine=False)

    @patch("apps.dashboard.views.get_groups_preview")
    def test_pagination_page_size(self, mock_service):
        """page_size param should control number of results returned."""
        mock_service.return_value = [
            {
                "id": i,
                "name": f"Group{i}",
                "track_id": 1,
                "track_name": "AUS-NSW",
                "member_count": 2,
                "lead_name": None,
                "status": "active",
            }
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