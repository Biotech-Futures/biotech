from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import Events
from apps.users.models import AdminScope


User = get_user_model()


class AdminEventApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="event.admin@example.com",
            password="pass123",
            first_name="Event",
            last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin, is_global=True)
        self.url = "/api/v1/admin/event/"

    def test_admin_can_create_event_without_host_user_id(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.url,
            {
                "eventName": "Admin Created Event",
                "description": "Created from admin API",
                "startAt": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
                "endsAt": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
                "eventFormat": "virtual",
                "locationLink": "https://example.com/meeting",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = Events.objects.get(event_name="Admin Created Event")
        self.assertEqual(event.host_user, self.admin)
        self.assertIsNone(event.location)
        self.assertEqual(response.data["data"]["hostUserId"], self.admin.id)
        self.assertEqual(response.data["data"]["hostName"], "Event Admin")
        self.assertEqual(response.data["data"]["hostEmail"], self.admin.email)

    def test_create_event_returns_400_for_missing_datetimes(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.url,
            {"eventName": "Missing Dates"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["data"], None)
        self.assertFalse(Events.objects.filter(event_name="Missing Dates").exists())

    def test_admin_can_query_upcoming_events(self):
        self.client.force_authenticate(user=self.admin)
        Events.objects.create(
            event_name="Upcoming Event",
            start_datetime=timezone.now() + timezone.timedelta(days=1),
            ends_datetime=timezone.now() + timezone.timedelta(days=1, hours=2),
            event_format="virtual",
        )

        response = self.client.get(self.url, {"page": 1, "limit": 10, "upcoming": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["total"], 1)
        self.assertEqual(response.data["data"]["items"][0]["eventName"], "Upcoming Event")

    def test_event_list_returns_host_from_host_user_id(self):
        self.client.force_authenticate(user=self.admin)
        Events.objects.create(
            event_name="Hosted Event",
            host_user=self.admin,
            start_datetime=timezone.now() + timezone.timedelta(days=1),
            ends_datetime=timezone.now() + timezone.timedelta(days=1, hours=2),
            event_format="virtual",
        )

        response = self.client.get(self.url, {"page": 1, "limit": 10, "upcoming": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = response.data["data"]["items"][0]
        self.assertEqual(event["hostUserId"], self.admin.id)
        self.assertEqual(event["hostName"], "Event Admin")
        self.assertEqual(event["hostEmail"], self.admin.email)
