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

    def test_admin_analytics_questions_point_to_the_relevant_report(self):
        admin = self.user_with_role("analytics@example.com", "admin")
        cases = [
            ("How can I export resource usage statistics as CSV?", "/analytics/resources", "Daily usage"),
            ("如何导出资源统计 CSV？", "/analytics/resources", "Daily usage"),
            ("What do daily active and monthly active users mean?", "/analytics/activity", "login"),
            ("Where are unassigned students in groups analytics?", "/analytics/groups", "Students without a group"),
            ("How does email monitoring track opened emails?", "/analytics/email", "unavailable"),
            ("How many active users do we have right now?", "/analytics", "cannot query"),
        ]
        for question, path, explanation in cases:
            with self.subTest(question=question):
                cache.clear()
                response = self.ask(admin, question)
                self.assertTrue(response.data["matched"])
                self.assertIn(path, [link["to"] for link in response.data["links"]])
                self.assertIn(explanation, response.data["answer"])

    def test_participant_cannot_receive_admin_analytics_guide(self):
        student = self.user_with_role("analytics-student@example.com", "student")
        response = self.ask(student, "How can I export resource usage statistics as CSV?")
        self.assertFalse(any(link["to"].startswith("/analytics") for link in response.data["links"]))

    def test_student_never_gets_admin_pages(self):
        student = self.user_with_role("s@example.com", "student")
        response = self.ask(student, "How do I import mentors from a CSV?")
        self.assertFalse(any(link["to"].startswith("/admin") for link in response.data["links"]))

    def test_student_contact_mentor_points_to_group(self):
        student = self.user_with_role("s@example.com", "student")
        response = self.ask(student, "How do I contact my mentor?")
        self.assertTrue(response.data["matched"])
        self.assertEqual(response.data["links"], [{"label": "Groups", "to": "/groups"}])

    def test_role_specific_topics(self):
        cases = [
            ("student", "Where can I download my certificate?", "/groups", "Results"),
            ("student", "My guardian never got the consent email", "/profile", "Guardian Details"),
            ("student", "Which steps does our submission have?", "/groups", "Poster"),
            ("mentor", "How do I set my weekly availability?", "/profile", "Weekly Availability"),
            ("mentor", "How do I schedule a meeting with my students?", "/groups", "join link"),
            ("supervisor", "How do I register my students?", "/supervisor/registration", "Registration"),
            ("admin", "Where do I set the certificate templates?", "/management", "Document Setup"),
        ]
        for role, question, link, phrase in cases:
            with self.subTest(role=role, question=question):
                user = User.objects.filter(email=f"{role}@example.com").first() or self.user_with_role(
                    f"{role}@example.com", role,
                )
                data = self.ask(user, question).data
                self.assertTrue(data["matched"])
                self.assertIn(link, [item["to"] for item in data["links"]])
                self.assertIn(phrase, data["answer"])

    def test_sign_in_help_mentions_magic_link(self):
        student = self.user_with_role("s@example.com", "student")
        self.assertIn("Magic Link", self.ask(student, "I forgot my password").data["answer"])

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
