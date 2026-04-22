from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.groups.models import Countries, CountryStates, Groups, Tracks
from .models import Milestone, TaskAssignees, Tasks

User = get_user_model()

# ---------------------------------------------------------------------------
# Shared fixture mixin
# ---------------------------------------------------------------------------

class TaskFixtureMixin:
    """Creates a minimal set of DB objects shared across task test classes."""

    def _create_fixtures(self):
        self.user = User.objects.create_user(
            email="taskuser@test.com", password="pass", first_name="Task", last_name="User"
        )
        self.other_user = User.objects.create_user(
            email="other@test.com", password="pass", first_name="Other", last_name="User"
        )
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="TEST-TRACK", state=state)
        self.group = Groups.objects.create(group_name="Test Group", track=self.track)

        self.milestone = Milestone.objects.create(
            group=self.group,
            milestone_name="Check-in #1",
            sort_order=10,
            due_date=timezone.now() + timezone.timedelta(days=7),
            start_date=timezone.now(),
        )

        self.active_task = Tasks.objects.create(
            task_name="Active task",
            due_date=timezone.now() + timezone.timedelta(days=3),
            milestone=self.milestone,
            deleted_flag=False,
            completed=False,
            status=Tasks.Status.TODO,
        )
        self.deleted_task = Tasks.objects.create(
            task_name="Deleted task",
            due_date=timezone.now() + timezone.timedelta(days=5),
            milestone=self.milestone,
            deleted_flag=True,
            completed=False,
            status=Tasks.Status.TODO,
        )
        self.done_task = Tasks.objects.create(
            task_name="Done task",
            due_date=timezone.now() + timezone.timedelta(days=1),
            milestone=self.milestone,
            deleted_flag=False,
            completed=True,
            status=Tasks.Status.DONE,
        )


# ---------------------------------------------------------------------------
# #4 – Boolean query parameter bug fix
# ---------------------------------------------------------------------------

class TaskBooleanFilterTests(TaskFixtureMixin, APITestCase):
    """
    Regression tests for the ?deleted= query parameter on GET /tasks/api/v1/tasks/.

    Before the fix, passing lowercase 'false' caused a 500 because Django's
    PostgreSQL adapter could not coerce an arbitrary string to boolean.
    After the fix, all common casing variants are accepted and invalid values
    return HTTP 400 instead of 500.
    """

    def setUp(self):
        self._create_fixtures()
        self.url = "/tasks/api/v1/tasks/"

    def _ids(self, response):
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        return [row["id"] for row in results]

    # --- Values that should resolve to deleted_flag=False ---

    def test_deleted_false_lowercase(self):
        """?deleted=false (lowercase) must work — was the original 500 trigger."""
        response = self.client.get(self.url, {"deleted": "false"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._ids(response)
        self.assertIn(self.active_task.id, ids)
        self.assertNotIn(self.deleted_task.id, ids)

    def test_deleted_False_capital(self):
        """?deleted=False (original casing) must continue to work."""
        response = self.client.get(self.url, {"deleted": "False"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.deleted_task.id, self._ids(response))

    def test_deleted_0(self):
        response = self.client.get(self.url, {"deleted": "0"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.deleted_task.id, self._ids(response))

    def test_deleted_no(self):
        response = self.client.get(self.url, {"deleted": "no"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.deleted_task.id, self._ids(response))

    # --- Values that should resolve to deleted_flag=True ---

    def test_deleted_true_lowercase(self):
        response = self.client.get(self.url, {"deleted": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._ids(response)
        self.assertIn(self.deleted_task.id, ids)
        self.assertNotIn(self.active_task.id, ids)

    def test_deleted_True_capital(self):
        response = self.client.get(self.url, {"deleted": "True"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.deleted_task.id, self._ids(response))

    def test_deleted_1(self):
        response = self.client.get(self.url, {"deleted": "1"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.deleted_task.id, self._ids(response))

    def test_deleted_yes(self):
        response = self.client.get(self.url, {"deleted": "yes"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.deleted_task.id, self._ids(response))

    # --- Invalid values must return 400, not 500 ---

    def test_deleted_invalid_returns_400(self):
        """An unrecognised value must return HTTP 400 with a descriptive message."""
        response = self.client.get(self.url, {"deleted": "maybe"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid deleted value", str(response.json()))

    def test_deleted_gibberish_returns_400(self):
        response = self.client.get(self.url, {"deleted": "xyz"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- No parameter means no filter (all tasks returned) ---

    def test_no_deleted_param_returns_all(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._ids(response)
        self.assertIn(self.active_task.id, ids)
        self.assertIn(self.deleted_task.id, ids)


# ---------------------------------------------------------------------------
# #1 – New task fields: completed, status, group, assignees
# ---------------------------------------------------------------------------

class TaskNewFieldsTests(TaskFixtureMixin, APITestCase):
    """
    Tests that TaskSerializer exposes the new fields added for the Progress
    Snapshot requirement: completed, status, group (derived from milestone),
    and assignees (from TaskAssignees).
    """

    def setUp(self):
        self._create_fixtures()
        self.url = "/tasks/api/v1/tasks/"
        TaskAssignees.objects.create(task=self.active_task, user=self.user)

    def _get_task(self, task_id):
        data = self.client.get(self.url).json()
        results = data.get("results", data) if isinstance(data, dict) else data
        return next((r for r in results if r["id"] == task_id), None)

    def test_response_includes_completed_field(self):
        row = self._get_task(self.active_task.id)
        self.assertIsNotNone(row)
        self.assertIn("completed", row)
        self.assertFalse(row["completed"])

    def test_response_includes_status_field(self):
        row = self._get_task(self.active_task.id)
        self.assertEqual(row["status"], Tasks.Status.TODO)

    def test_done_task_has_correct_completed_and_status(self):
        row = self._get_task(self.done_task.id)
        self.assertTrue(row["completed"])
        self.assertEqual(row["status"], Tasks.Status.DONE)

    def test_response_includes_group_derived_from_milestone(self):
        """group field should contain the milestone's group id."""
        row = self._get_task(self.active_task.id)
        self.assertEqual(row["group"], self.group.id)

    def test_group_is_null_when_task_has_no_milestone(self):
        orphan = Tasks.objects.create(
            task_name="Orphan",
            due_date=timezone.now() + timezone.timedelta(days=1),
            milestone=None,
        )
        row = self._get_task(orphan.id)
        self.assertIsNone(row["group"])

    def test_response_includes_assignees(self):
        row = self._get_task(self.active_task.id)
        self.assertIn("assignees", row)
        self.assertEqual(len(row["assignees"]), 1)
        assignee = row["assignees"][0]
        self.assertEqual(assignee["id"], self.user.id)
        self.assertEqual(assignee["email"], self.user.email)

    def test_soft_deleted_assignee_excluded_from_assignees(self):
        """TaskAssignees with deleted_flag=True must not appear in the list."""
        TaskAssignees.objects.filter(task=self.active_task, user=self.user).update(deleted_flag=True)
        row = self._get_task(self.active_task.id)
        self.assertEqual(len(row["assignees"]), 0)

    def test_task_without_assignees_returns_empty_list(self):
        row = self._get_task(self.done_task.id)
        self.assertEqual(row["assignees"], [])


# ---------------------------------------------------------------------------
# #1 – assigned_to=me and group_id filters on the task list
# ---------------------------------------------------------------------------

class TaskListFilterTests(TaskFixtureMixin, APITestCase):
    """Tests for the new ?assigned_to=me and ?group_id= filters."""

    def setUp(self):
        self._create_fixtures()
        self.url = "/tasks/api/v1/tasks/"
        # Assign active_task to self.user only
        TaskAssignees.objects.create(task=self.active_task, user=self.user)

    def _ids(self, response):
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        return [r["id"] for r in results]

    def test_assigned_to_me_returns_only_users_tasks(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"assigned_to": "me"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._ids(response)
        self.assertIn(self.active_task.id, ids)
        self.assertNotIn(self.done_task.id, ids)

    def test_assigned_to_me_unauthenticated_returns_all(self):
        """Without auth, assigned_to=me is silently ignored and all tasks are returned."""
        response = self.client.get(self.url, {"assigned_to": "me"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._ids(response)
        self.assertIn(self.done_task.id, ids)

    def test_group_id_filter_returns_only_group_tasks(self):
        other_group = Groups.objects.create(group_name="Other Group", track=self.track)
        other_milestone = Milestone.objects.create(
            group=other_group, milestone_name="Other MS", sort_order=1
        )
        other_task = Tasks.objects.create(
            task_name="Other task",
            due_date=timezone.now() + timezone.timedelta(days=2),
            milestone=other_milestone,
        )

        response = self.client.get(self.url, {"group_id": self.group.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = self._ids(response)
        self.assertIn(self.active_task.id, ids)
        self.assertNotIn(other_task.id, ids)


# ---------------------------------------------------------------------------
# #1 – PATCH keeps completed and status in sync
# ---------------------------------------------------------------------------

class TaskPatchSyncTests(TaskFixtureMixin, APITestCase):
    """
    Patching `completed` must update `status` and vice versa so the two fields
    never diverge in the database.
    """

    def setUp(self):
        self._create_fixtures()

    def test_patch_completed_true_sets_status_done(self):
        url = f"/tasks/api/v1/tasks/{self.active_task.id}/"
        response = self.client.patch(url, {"completed": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_task.refresh_from_db()
        self.assertTrue(self.active_task.completed)
        self.assertEqual(self.active_task.status, Tasks.Status.DONE)

    def test_patch_completed_false_sets_status_todo(self):
        url = f"/tasks/api/v1/tasks/{self.done_task.id}/"
        response = self.client.patch(url, {"completed": False}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.done_task.refresh_from_db()
        self.assertFalse(self.done_task.completed)
        self.assertEqual(self.done_task.status, Tasks.Status.TODO)

    def test_patch_status_done_sets_completed_true(self):
        url = f"/tasks/api/v1/tasks/{self.active_task.id}/"
        response = self.client.patch(url, {"status": "done"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_task.refresh_from_db()
        self.assertTrue(self.active_task.completed)
        self.assertEqual(self.active_task.status, Tasks.Status.DONE)

    def test_patch_status_todo_sets_completed_false(self):
        url = f"/tasks/api/v1/tasks/{self.done_task.id}/"
        response = self.client.patch(url, {"status": "todo"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.done_task.refresh_from_db()
        self.assertFalse(self.done_task.completed)


# ---------------------------------------------------------------------------
# #1 – Milestone new fields and group_id filter
# ---------------------------------------------------------------------------

class MilestoneTests(TaskFixtureMixin, APITestCase):
    """
    Tests that MilestoneSerializer exposes start_date, due_date, sort_order
    and that the ?group_id= filter works on the milestone list endpoint.
    """

    def setUp(self):
        self._create_fixtures()
        self.url = "/tasks/api/v1/milestones/"

    def _get_milestone(self, ms_id, params=None):
        data = self.client.get(self.url, params or {}).json()
        results = data.get("results", data) if isinstance(data, dict) else data
        return next((r for r in results if r["id"] == ms_id), None)

    def test_milestone_list_includes_start_date(self):
        row = self._get_milestone(self.milestone.id)
        self.assertIsNotNone(row)
        self.assertIn("start_date", row)

    def test_milestone_list_includes_due_date(self):
        row = self._get_milestone(self.milestone.id)
        self.assertIn("due_date", row)
        self.assertIsNotNone(row["due_date"])

    def test_milestone_list_includes_sort_order(self):
        row = self._get_milestone(self.milestone.id)
        self.assertEqual(row["sort_order"], 10)

    def test_milestone_group_id_filter(self):
        other_group = Groups.objects.create(group_name="Other Group", track=self.track)
        other_ms = Milestone.objects.create(
            group=other_group, milestone_name="Other MS", sort_order=1
        )

        response = self.client.get(self.url, {"group_id": self.group.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        ids = [r["id"] for r in results]
        self.assertIn(self.milestone.id, ids)
        self.assertNotIn(other_ms.id, ids)

    def test_milestone_ordered_by_sort_order(self):
        ms_low = Milestone.objects.create(
            group=self.group, milestone_name="First", sort_order=1
        )
        ms_high = Milestone.objects.create(
            group=self.group, milestone_name="Last", sort_order=99
        )
        response = self.client.get(self.url, {"group_id": self.group.id})
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        ids = [r["id"] for r in results]
        self.assertLess(ids.index(ms_low.id), ids.index(ms_high.id))
