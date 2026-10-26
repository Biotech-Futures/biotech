from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import AdminScope

User = get_user_model()

URL = "/api/v1/assistant/ask/"


class AssistantAskTests(APITestCase):
    def setUp(self):
        # The throttle counter lives in the cache and outlives each test.
        cache.clear()

    def user_with_role(self, email, role_name):
        user = User.objects.create_user(email=email, password="pass1234")
        RoleAssignmentHistory.objects.create(
            user=user,
            role=Roles.objects.get_or_create(role_name=role_name)[0],
            valid_from=datetime(2025, 1, 1, tzinfo=datetime_timezone.utc),
        )
        return user

    def ask(self, user, question):
        self.client.force_login(user)
        return self.client.post(URL, {"question": question}, format="json")

    def test_anonymous_is_refused(self):
        response = self.client.post(URL, {"question": "Where are resources?"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_or_long_question_is_rejected(self):
        student = self.user_with_role("s@example.com", "student")
        self.assertEqual(self.ask(student, "  ").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.ask(student, "a" * 501).status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_gets_admin_answer(self):
        admin = self.user_with_role("a@example.com", "admin")
        response = self.ask(admin, "How do I import mentors from a CSV?")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["matched"])
        self.assertIn({"label": "Users", "to": "/admin/users"}, response.data["links"])

    def test_admin_scope_without_admin_role_counts_as_admin(self):
        user = User.objects.create_user(email="scope@example.com", password="pass1234")
        AdminScope.objects.create(user=user)
        response = self.ask(user, "Where do I mark submissions?")
        self.assertIn({"label": "Grading", "to": "/grading"}, response.data["links"])

    def test_student_never_gets_admin_pages(self):
        student = self.user_with_role("s@example.com", "student")
        response = self.ask(student, "How do I import mentors from a CSV?")
        self.assertFalse(any(link["to"].startswith("/admin") for link in response.data["links"]))

    def test_student_contact_mentor_points_to_group(self):
        student = self.user_with_role("s@example.com", "student")
        response = self.ask(student, "How do I contact my mentor?")
        self.assertTrue(response.data["matched"])
        self.assertEqual(response.data["links"], [{"label": "Groups", "to": "/groups"}])

    def test_lead_questions_are_answered_for_each_role(self):
        for role in ("admin", "student", "mentor", "supervisor"):
            user = self.user_with_role(f"{role}@example.com", role)
            for question in ("What should I do?", "What features does the platform have?", "How do I get help?"):
                with self.subTest(role=role, question=question):
                    self.assertTrue(self.ask(user, question).data["matched"])

    def test_unrelated_question_falls_back_to_support(self):
        student = self.user_with_role("s@example.com", "student")
        response = self.ask(student, "What's the weather in Sydney tomorrow?")
        self.assertFalse(response.data["matched"])
        self.assertIn(settings.SUPPORT_EMAIL, response.data["answer"])
        self.assertEqual(response.data["links"], [{"label": "Support", "to": "/support"}])
