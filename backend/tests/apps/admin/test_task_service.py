from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.admin.services.task import list_admin_tasks
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
