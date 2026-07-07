from django.test import TestCase
from django.utils import timezone

from apps.groups.models import Groups

from .filters import TaskFilter
from .models import CreatorRole, Task, TaskType


class DeletedFilterTests(TestCase):
    def setUp(self):
        self.group = Groups.objects.create(group_name="DF-Group")
        self.active = Task.objects.create(
            name="active", task_type=TaskType.GROUP, group=self.group,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.deleted = Task.objects.create(
            name="deleted", task_type=TaskType.GROUP, group=self.group,
            creator_role=CreatorRole.GLOBAL_ADMIN, deleted_at=timezone.now(),
        )

    def _filter(self, value):
        return TaskFilter({"deleted": value}, queryset=Task.objects.all()).qs

    def test_true_returns_deleted_only(self):
        ids = set(self._filter("true").values_list("id", flat=True))
        self.assertEqual(ids, {self.deleted.id})

    def test_false_returns_active_only(self):
        ids = set(self._filter("false").values_list("id", flat=True))
        self.assertEqual(ids, {self.active.id})

    def test_omitted_returns_both(self):
        ids = set(TaskFilter({}, queryset=Task.objects.all()).qs.values_list("id", flat=True))
        self.assertEqual(ids, {self.active.id, self.deleted.id})

    def test_invalid_value_is_filtered_out(self):
        # django-filter's BooleanFilter coerces unrecognised strings to None,
        # which falls through to the no-op branch — meaning the filter does
        # not narrow the queryset. The FilterSet itself remains valid.
        fs = TaskFilter({"deleted": "maybe"}, queryset=Task.objects.all())
        self.assertEqual(set(fs.qs.values_list("id", flat=True)), {self.active.id, self.deleted.id})
