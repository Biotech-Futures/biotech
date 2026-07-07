from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.admin.services.task import (
    list_admin_tasks, get_admin_task_by_id, create_admin_task,
    update_admin_task, delete_admin_task, toggle_admin_task,
)
from apps.groups.models import Groups
from apps.tasks.models import CreatorRole, Task, TaskType
from apps.users.models import AdminScope


User = get_user_model()


class AdminTaskTests(TestCase):
    def setUp(self):
        self.group = Groups.objects.create(group_name="Group A")
        self.admin = User.objects.create_user(email="admin@example.com", password="pw")
        AdminScope.objects.create(user=self.admin)

    def test_lists_tasks_by_created_at_desc(self):
        older = Task.objects.create(
            name="older",
            task_type=TaskType.GROUP,
            group=self.group,
            created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        newer = Task.objects.create(
            name="newer",
            task_type=TaskType.GROUP,
            group=self.group,
            created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        now = timezone.now()
        Task.objects.filter(id=older.id).update(created_at=now - timedelta(days=1))
        Task.objects.filter(id=newer.id).update(created_at=now)

        result = list_admin_tasks(self.admin)

        ids = [item["id"] for item in result["data"]["items"]]
        self.assertEqual(ids, [newer.id, older.id])

    def test_create_group_task(self):
        result = create_admin_task(self.admin, {
            "name": "New Group Task",
            "description": "Do something",
            "task_type": TaskType.GROUP,
            "group": self.group.id,
        })
        self.assertEqual(result["msg"], "Task created successfully")
        self.assertEqual(result["data"]["name"], "New Group Task")
        self.assertEqual(result["data"]["group"], self.group.id)

    def test_create_group_task_missing_group(self):
        result = create_admin_task(self.admin, {
            "name": "Bad Task",
            "task_type": TaskType.GROUP,
        })
        self.assertEqual(result["msg"], "Group task requires a group")
        self.assertIsNone(result["data"])

    def test_create_individual_task(self):
        user = User.objects.create_user(email="user@example.com", password="pw")
        result = create_admin_task(self.admin, {
            "name": "Individual Task",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_user": user.id,
        })
        self.assertEqual(result["msg"], "Task created successfully")
        self.assertEqual(result["data"]["assigned_user"], user.id)

    def test_create_individual_task_missing_user(self):
        result = create_admin_task(self.admin, {
            "name": "Bad Task",
            "task_type": TaskType.INDIVIDUAL,
        })
        self.assertEqual(result["msg"], "Individual task requires an assigned user")
        self.assertIsNone(result["data"])

    def test_get_admin_task_by_id_found(self):
        task = Task.objects.create(
            name="Find Me", task_type=TaskType.GROUP,
            group=self.group, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        result = get_admin_task_by_id(self.admin, task.id)
        self.assertEqual(result["msg"], "Task retrieved successfully")
        self.assertEqual(result["data"]["name"], "Find Me")

    def test_get_admin_task_by_id_not_found(self):
        result = get_admin_task_by_id(self.admin, 9999)
        self.assertEqual(result["msg"], "Task not found")
        self.assertIsNone(result["data"])

    def test_update_admin_task(self):
        task = Task.objects.create(
            name="Original", task_type=TaskType.GROUP,
            group=self.group, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        result = update_admin_task(self.admin, task.id, {"name": "Updated"})
        self.assertEqual(result["msg"], "Task updated successfully")
        self.assertEqual(result["data"]["name"], "Updated")

    def test_update_admin_task_not_found(self):
        result = update_admin_task(self.admin, 9999, {"name": "Ghost"})
        self.assertEqual(result["msg"], "Task not found")
        self.assertIsNone(result["data"])

    def test_delete_admin_task(self):
        task = Task.objects.create(
            name="Delete Me", task_type=TaskType.GROUP,
            group=self.group, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        result = delete_admin_task(self.admin, task.id)
        self.assertEqual(result["msg"], "Task deleted successfully")
        task.refresh_from_db()
        self.assertIsNotNone(task.deleted_at)

    def test_delete_admin_task_not_found(self):
        result = delete_admin_task(self.admin, 9999)
        self.assertEqual(result["msg"], "Task not found")
        self.assertIsNone(result["data"])

    def test_toggle_admin_task_complete(self):
        task = Task.objects.create(
            name="Toggle Me", task_type=TaskType.GROUP,
            group=self.group, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        result = toggle_admin_task(self.admin, task.id, True)
        self.assertEqual(result["msg"], "Task updated successfully")
        self.assertTrue(result["data"]["completed"])

    def test_toggle_admin_task_incomplete(self):
        task = Task.objects.create(
            name="Toggle Me 2", task_type=TaskType.GROUP,
            group=self.group, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
            completed=True,
        )
        result = toggle_admin_task(self.admin, task.id, False)
        self.assertFalse(result["data"]["completed"])

    def test_toggle_admin_task_not_found(self):
        result = toggle_admin_task(self.admin, 9999, True)
        self.assertEqual(result["msg"], "Task not found")
        self.assertIsNone(result["data"])
