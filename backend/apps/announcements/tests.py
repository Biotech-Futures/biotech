from datetime import timedelta

from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from announcements.models import Announcement
from users.models import User


class AnnouncementAPITests(APITestCase):
    def setUp(self):
        super().setUp()

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

        self.announcement_all = Announcement.objects.create(
            title="Welcome",
            summary="Kickoff details",
            content="Full kickoff agenda",
            audience="all",
            created_at=timezone.now() - timedelta(days=1),
        )
        self.announcement_students = Announcement.objects.create(
            title="Student Only",
            summary="Student schedule",
            content="Details for students",
            audience="student",
            created_at=timezone.now(),
        )
        self.announcement_mentors = Announcement.objects.create(
            title="Mentor Briefing",
            summary="Mentor update",
            content="Details for mentors",
            audience="mentor",
            created_at=timezone.now(),
        )

    def authenticate_as_student(self):
        self.client.force_authenticate(user=self.student)

    def authenticate_as_admin(self):
        self.client.force_authenticate(user=self.admin)

    def test_list_announcements_filtered_by_role(self):
        self.authenticate_as_student()
        url = reverse("announcements:announcement-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item["title"] for item in response.data["results"]]
        self.assertIn(self.announcement_all.title, titles)
        self.assertIn(self.announcement_students.title, titles)
        self.assertNotIn(self.announcement_mentors.title, titles)

    def test_search_announcements(self):
        self.authenticate_as_student()
        url = reverse("announcements:announcement-list")
        response = self.client.get(url, {"search": "mentor"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, [])

        self.authenticate_as_admin()
        response_admin = self.client.get(url, {"search": "mentor"})
        self.assertEqual(response_admin.status_code, status.HTTP_200_OK)
        titles_admin = [item["title"] for item in response_admin.data["results"]]
        self.assertIn(self.announcement_mentors.title, titles_admin)

    def test_get_announcement_detail(self):
        self.authenticate_as_student()
        url = reverse("announcements:announcement-detail", kwargs={"pk": self.announcement_all.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.announcement_all.id)
        self.assertEqual(response.data["title"], self.announcement_all.title)

    def test_admin_can_create_announcement(self):
        self.authenticate_as_admin()
        payload = {
            "title": "New Announcement",
            "summary": "Summary",
            "content": "Full content",
            "audience": "all",
            "author": "Program Team",
        }
        url = reverse("announcements:announcement-list")
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Announcement.objects.filter(title="New Announcement").exists())

    def test_non_admin_cannot_create_announcement(self):
        self.authenticate_as_student()
        url = reverse("announcements:announcement-list")
        response = self.client.post(
            url,
            {
                "title": "Blocked",
                "summary": "Should not create",
                "audience": "all",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Announcement.objects.filter(title="Blocked").exists())
