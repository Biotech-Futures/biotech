from django.test import TestCase

# Create your tests here.
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Events

User = get_user_model()

class EventAPITests(APITestCase):
    """
    Minimal test suite for /events/v1 endpoints.
    Covers:
    - GET returns only upcoming events
    - POST works for admin/staff only
    - POST rejected for regular user
    - Validation rules (end time after start time)
    """

    def setUp(self):
        # Create regular and admin users
        self.user = User.objects.create_user(email="user2@gmail.com", password="pass123")
        self.admin = User.objects.create_user(
            email="test_admin@gmail.com", password="admin123", is_staff=True
        )

        # Base URL (adjust if prefix changed)
        self.url = "/events/v1/"

        # Create one upcoming and one past event
        self.future_event = Events.objects.create(
            event_name="Future Event",
            description="Coming soon!",
            start_datetime=timezone.now() + timezone.timedelta(days=3),
            ends_datetime=timezone.now() + timezone.timedelta(days=3, hours=2),
            location="Sydney",
        )
        self.past_event = Events.objects.create(
            event_name="Past Event",
            description="Already happened.",
            start_datetime=timezone.now() - timezone.timedelta(days=5),
            ends_datetime=timezone.now() - timezone.timedelta(days=5, hours=-2),
            location="Melbourne",
        )

    # --- GET TESTS ---

    def test_get_events_returns_only_upcoming(self):
        """GET /events/v1/ should return only upcoming events"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle paginated response
        results = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        event_names = [e["event_name"] for e in results]
        self.assertIn("Future Event", event_names)
        self.assertNotIn("Past Event", event_names)

    # --- POST TESTS ---

    def test_admin_can_create_event(self):
        """Admin/staff user can POST successfully"""
        self.client.force_authenticate(user=self.admin)
        data = {
            "event_name": "Admin Created Event",
            "description": "By staff",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            "ends_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
            "location": "Sydney",
            "is_virtual": False,
            "humanitix_link": "https://example.com/event",
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Events.objects.filter(event_name="Admin Created Event").exists())

    def test_non_admin_cannot_create_event(self):
        """Regular user cannot POST"""
        self.client.force_authenticate(user=self.user)
        data = {
            "event_name": "Admin Created Event",
            "description": "By staff",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            "ends_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
            "location": "Sydney",
            "is_virtual": False,
            "humanitix_link": "https://example.com/event"
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Events.objects.filter(event_name="User Created Event").exists())

    def test_validation_error_if_end_before_start(self):
        """POST with invalid datetime order should fail"""
        self.client.force_authenticate(user=self.admin)
        data = {
            "event_name": "Admin Created Event",
            "description": "By staff",
            "start_datetime": (timezone.now() + timezone.timedelta(days=1, hours=2)).isoformat(),
            "ends_datetime": (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            "location": "Sydney",
            "is_virtual": False,
            "humanitix_link": "https://example.com/event"
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ends_datetime", str(response.data))

    def test_cannot_create_event_in_past(self):
        """POST with start_datetime in the past should fail"""
        self.client.force_authenticate(user=self.admin)
        data = {
            "event_name": "Past Event",
            "description": "This event is in the past",
            "start_datetime": (timezone.now() - timezone.timedelta(days=1)).isoformat(),
            "ends_datetime": (timezone.now() - timezone.timedelta(hours=22)).isoformat(),
            "location": "Sydney",
            "is_virtual": False,
            "humanitix_link": "https://example.com/event"
        }
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("start_datetime", str(response.data))
        self.assertIn("Cannot create events in the past", str(response.data))
