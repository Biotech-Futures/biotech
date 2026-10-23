from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.tasks.models import CreatorRole, Task, TaskType
from apps.users.models import AdminScope


class AdminTaskBooleanTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(email="toggle-admin@example.com", password="pw")
        AdminScope.objects.create(user=self.admin)
        self.task = Task.objects.create(
            name="Toggle", task_type=TaskType.INDIVIDUAL, assigned_user=self.admin,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN, completed=True,
        )
        self.url = f"/api/v1/admin/task/{self.task.pk}/toggle/"
        self.client.force_authenticate(self.admin)

    def test_boolean_strings_and_native_values_are_parsed(self):
        for value, expected in (("false", False), ("true", True), (False, False), (True, True)):
            with self.subTest(value=value):
                response = self.client.post(self.url, {"completed": value}, format="json")
                self.assertEqual(response.status_code, 200)
                self.task.refresh_from_db()
                self.assertIs(self.task.completed, expected)
                self.assertIs(response.data["data"]["completed"], expected)

    def test_invalid_values_return_400_without_changes(self):
        for value in (None, "invalid", [], {}, 2):
            with self.subTest(value=value):
                response = self.client.post(self.url, {"completed": value}, format="json")
                self.assertEqual(response.status_code, 400)
                self.task.refresh_from_db()
                self.assertTrue(self.task.completed)

    def test_completed_is_required(self):
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 400)
        self.task.refresh_from_db()
        self.assertTrue(self.task.completed)

    def test_multipart_requires_completed_and_parses_false(self):
        response = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.task.refresh_from_db()
        self.assertTrue(self.task.completed)
        response = self.client.post(self.url, {"completed": "false"}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertFalse(self.task.completed)

    def test_non_admin_is_forbidden(self):
        user = get_user_model().objects.create_user(email="toggle-user@example.com", password="pw")
        self.client.force_authenticate(user)
        self.assertEqual(self.client.post(self.url, {"completed": False}, format="json").status_code, 403)

    def test_missing_task_remains_404(self):
        response = self.client.post("/api/v1/admin/task/999999/toggle/", {"completed": False}, format="json")
        self.assertEqual(response.status_code, 404)
