from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.admin.services.task import list_admin_tasks, restore_admin_task
from apps.groups.models import Countries, CountryStates, Groups, Tracks
from apps.tasks.models import CreatorRole, Task, TaskType
from apps.users.models import AdminScope


User = get_user_model()


class AdminTaskListTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="AU")
        state = CountryStates.objects.create(country=country, state_name="VIC")
        track = Tracks.objects.create(track_name="VIC-01", state=state)
        self.group = Groups.objects.create(group_name="Group A", track=track)
        self.admin = User.objects.create_user(email="admin@example.com", password="pw")
        AdminScope.objects.create(user=self.admin, is_global=True)

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

    def test_lists_deleted_tasks_and_restores_task(self):
        deleted_at = timezone.now()
        active = Task.objects.create(
            name="active",
            task_type=TaskType.GROUP,
            group=self.group,
            created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        deleted = Task.objects.create(
            name="deleted",
            task_type=TaskType.GROUP,
            group=self.group,
            created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
            deleted_at=deleted_at,
        )

        result = list_admin_tasks(self.admin, deleted=True)

        self.assertEqual(result["data"]["total"], 1)
        self.assertEqual(result["data"]["items"][0]["id"], deleted.id)
        self.assertNotEqual(result["data"]["items"][0]["id"], active.id)

        restore_result = restore_admin_task(self.admin, deleted.id)

        self.assertEqual(restore_result["msg"], "Task restored successfully")
        deleted.refresh_from_db()
        self.assertIsNone(deleted.deleted_at)
