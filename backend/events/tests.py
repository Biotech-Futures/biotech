import io
import tempfile
from datetime import date, timedelta

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from events.models import Event, EventRegistration
from users.models import User


class EventAPITests(APITestCase):
    def setUp(self):
        super().setUp()
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)

        self.admin = User.objects.create_user(
            email="admin@example.com",
            username="admin@example.com",
            password="testpass123",
            role="admin",
        )
        self.student = User.objects.create_user(
            email="student@example.com",
            username="student@example.com",
            password="testpass123",
            role="student",
        )

        self.event = Event.objects.create(
            title="Program Kickoff",
            description="Kickoff session",
            long_description="Detailed overview",
            date=date.today() + timedelta(days=3),
            time="10:00 AM",
            location="Main Hall",
            type="in-person",
            register_link="https://example.com/register",
        )

    def authenticate_as_student(self):
        self.client.force_authenticate(user=self.student)

    def authenticate_as_admin(self):
        self.client.force_authenticate(user=self.admin)

    def _create_test_image(self, name="cover.png"):
        buffer = io.BytesIO()
        image = Image.new("RGB", (2, 2), color="blue")
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.read(), content_type="image/png")

    def test_list_events_filters_upcoming(self):
        past_event = Event.objects.create(
            title="Past Meetup",
            description="Already happened",
            date=date.today() - timedelta(days=2),
            time="12:00 PM",
            location="Online",
            type="virtual",
        )

        self.authenticate_as_student()
        url = reverse("events:event-list")
        response = self.client.get(url, {"upcoming": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item["title"] for item in response.data["results"]]
        self.assertIn(self.event.title, titles)
        self.assertNotIn(past_event.title, titles)

    def test_get_event_detail(self):
        self.authenticate_as_student()
        url = reverse("events:event-detail", kwargs={"pk": self.event.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], self.event.title)
        self.assertIn("longDescription", response.data)

    def test_register_for_event(self):
        self.authenticate_as_student()
        url = reverse("events:event-register", kwargs={"pk": self.event.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            EventRegistration.objects.filter(event=self.event, user=self.student).exists()
        )

        # Duplicate registration should fail
        response_dup = self.client.post(url)
        self.assertEqual(response_dup.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_create_event(self):
        self.authenticate_as_admin()
        url = reverse("events:event-list")
        payload = {
            "title": "Mentor Workshop",
            "description": "Guidance session",
            "longDescription": "Extended details",
            "date": (date.today() + timedelta(days=7)).isoformat(),
            "time": "4:00 PM",
            "location": "Online",
            "type": "virtual",
            "registerLink": "https://example.com/mentor-workshop",
            "capacity": 100,
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Event.objects.filter(title="Mentor Workshop").exists())

    def test_update_cover_requires_admin(self):
        self.authenticate_as_student()
        url = reverse("events:event-update-cover", kwargs={"pk": self.event.id})
        response = self.client.put(url, {"coverImage": self._create_test_image()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate_as_admin()
        response_admin = self.client.put(
            url,
            {"coverImage": self._create_test_image()},
            format="multipart",
        )
        self.assertEqual(response_admin.status_code, status.HTTP_200_OK)
        self.event.refresh_from_db()
        self.assertTrue(self.event.cover_image)
