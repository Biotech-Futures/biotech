from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.tasks.models import CreatorRole, Task, TaskType
from apps.users.models import AdminScope


class AdminTaskPaginationTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(email="page-admin@example.com", password="pw")
        AdminScope.objects.create(user=self.admin)
        self.tasks = [Task.objects.create(
            name=f"Task {i}", task_type=TaskType.INDIVIDUAL, assigned_user=self.admin,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        ) for i in range(3)]
        self.url = "/api/v1/admin/task/"
        self.client.force_authenticate(self.admin)

    def test_invalid_and_out_of_range_parameters_return_400(self):
        self.client.raise_request_exception = False
        for field, values in {
            "page": ("abc", "", "1.5", "0", "-1", "2147483648"),
            "limit": ("abc", "", "1.5", "0", "-1", "10001"),
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    response = self.client.get(self.url, {field: value})
                    self.assertEqual(response.status_code, 400)

    def test_defaults_are_preserved(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["page"], 1)
        self.assertEqual(response.data["data"]["limit"], 10)
        self.assertEqual(response.data["data"]["total"], 3)

    def test_page_and_limit_control_the_slice(self):
        response = self.client.get(self.url, {"page": 2, "limit": 1, "sortBy": "name", "sortOrder": "asc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["data"]["items"]], [self.tasks[1].pk])
        self.assertTrue(response.data["data"]["has_more"])

    def test_upper_bounds_and_empty_pages_are_valid(self):
        response = self.client.get(self.url, {"page": 2147483647, "limit": 10000})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["items"], [])
        self.assertFalse(response.data["data"]["has_more"])

    def test_non_admin_is_forbidden(self):
        user = get_user_model().objects.create_user(email="page-user@example.com", password="pw")
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_search_is_preserved_with_pagination(self):
        response = self.client.get(self.url, {"search": " Task 1 ", "page": 1, "limit": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["total"], 1)
        self.assertEqual([row["id"] for row in response.data["data"]["items"]], [self.tasks[1].pk])
        self.assertFalse(response.data["data"]["has_more"])

    def test_role_task_list_validates_page_and_limit(self):
        self.client.raise_request_exception = False
        url = "/api/v1/admin/role-task/"
        for params in ({"page": "abc"}, {"page": "0"}, {"limit": "abc"}, {"limit": "10001"}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(url, params).status_code, 400)
        self.assertEqual(self.client.get(url, {"page": 1, "limit": 10000}).status_code, 200)
