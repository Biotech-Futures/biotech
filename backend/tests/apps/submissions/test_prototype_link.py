"""Tests for the prototype link's length and format checks."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import Deadline, Submission
from apps.users.models import User

from .seed_data import install_question_set


class PrototypeLinkTests(TestCase):
    def setUp(self):
        role = Roles.objects.create(role_name="student")
        self.group = Groups.objects.create(group_name="BTF-LINK")
        student = User.objects.create_user(
            email="link@test.local", password="testUser@123", first_name="Test", last_name="Student"
        )
        RoleAssignmentHistory.objects.create(user=student, role=role, valid_from=timezone.now(), valid_to=None)
        GroupMembership.objects.create(group=self.group, user=student, membership_role="student")
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)
        install_question_set()

        self.client = APIClient()
        self.client.force_authenticate(user=student)
        self.url = reverse("group-submission", kwargs={"group_id": self.group.id})

    def _save(self, link):
        return self.client.put(self.url, {"prototype_url": link}, format="json")

    def test_a_link_of_500_characters_is_saved(self):
        link = "https://www.figma.com/design/" + "a" * (500 - 29)

        response = self._save(link)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.objects.get(group=self.group).prototype_url, link)

    def test_a_longer_link_is_refused_with_a_clear_message(self):
        response = self._save("https://www.figma.com/design/" + "a" * 472)

        self.assertEqual(response.status_code, 400)
        self.assertIn("longer than 500 characters", str(response.data))
        self.assertFalse(Submission.objects.filter(group=self.group).exclude(prototype_url="").exists())

    def test_text_that_is_not_a_link_is_refused(self):
        response = self._save("our prototype is on the drive")

        self.assertEqual(response.status_code, 400)
        self.assertIn("doesn't look like a web link", str(response.data))

    def test_the_submitted_copy_holds_a_long_link_too(self):
        field = Submission._meta.get_field("submitted_prototype_url")

        self.assertEqual(field.max_length, 500)
