from __future__ import annotations

from datetime import timedelta

from importlib import import_module

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.tasks.models import CreatorRole, RoleTask, RoleTaskCompletion, Task, TaskType
from apps.users.models import AdminScope

User = get_user_model()

MINE_URL = "/api/v1/tasks/role-tasks/mine/"


def _toggle_url(pk):
    return f"/api/v1/tasks/role-tasks/{pk}/check/"


class _World:
    def _build(self):
        self.admin = User.objects.create_user(email="admin@t.com", password="pw")
        AdminScope.objects.create(user=self.admin)
        self.mentor_role = Roles.objects.create(role_name="mentor")
        self.student_role = Roles.objects.create(role_name="student")

    def _grant_role(self, user, role, *, valid_to=None):
        RoleAssignmentHistory.objects.create(
            user=user,
            role=role,
            valid_from=timezone.now() - timedelta(days=1),
            valid_to=valid_to,
        )

    def _make_role_task(self, name, role):
        return RoleTask.objects.create(
            name=name,
            role=role,
            created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )


class RoleTaskMineVisibilityTests(_World, APITestCase):
    def setUp(self):
        self._build()

    def test_anonymous_blocked(self):
        response = self.client.get(MINE_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_sees_role_task_for_their_current_role(self):
        mentor_task = self._make_role_task("Mentor Onboarding", self.mentor_role)
        self._make_role_task("Student Handbook", self.student_role)

        mentor = User.objects.create_user(email="mentor@t.com", password="pw")
        self._grant_role(mentor, self.mentor_role)

        self.client.force_authenticate(user=mentor)
        response = self.client.get(MINE_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data]
        self.assertEqual(ids, [mentor_task.id])
        self.assertEqual(response.data[0]["role"], "mentor")
        # No completion row yet — defaults to not-started rather than erroring.
        self.assertEqual(response.data[0]["status"], "todo")
        self.assertFalse(response.data[0]["completed"])

    def test_new_role_holder_auto_receives_a_role_task_created_before_they_had_the_role(self):
        # This is the ticket's actual point: no fan-out happened at creation
        # time, so a user who gains the role AFTER the task was defined must
        # still see it, with no backfill/migration step required.
        role_task = self._make_role_task("Mentor Training", self.mentor_role)

        late_mentor = User.objects.create_user(email="late@t.com", password="pw")
        self.client.force_authenticate(user=late_mentor)
        self.assertEqual(self.client.get(MINE_URL).data, [])

        self._grant_role(late_mentor, self.mentor_role)

        response = self.client.get(MINE_URL)
        self.assertEqual([item["id"] for item in response.data], [role_task.id])

    def test_revoked_role_drops_visibility_on_next_read(self):
        role_task = self._make_role_task("Mentor Training", self.mentor_role)
        mentor = User.objects.create_user(email="mentor@t.com", password="pw")
        self._grant_role(mentor, self.mentor_role)

        self.client.force_authenticate(user=mentor)
        self.assertEqual([item["id"] for item in self.client.get(MINE_URL).data], [role_task.id])

        RoleAssignmentHistory.objects.filter(user=mentor, role=self.mentor_role).update(
            valid_to=timezone.now() - timedelta(minutes=1)
        )

        self.assertEqual(self.client.get(MINE_URL).data, [])

    def test_soft_deleted_role_task_is_not_visible(self):
        role_task = self._make_role_task("Gone", self.mentor_role)
        role_task.soft_delete()
        mentor = User.objects.create_user(email="mentor@t.com", password="pw")
        self._grant_role(mentor, self.mentor_role)

        self.client.force_authenticate(user=mentor)
        self.assertEqual(self.client.get(MINE_URL).data, [])


class RoleTaskToggleTests(_World, APITestCase):
    def setUp(self):
        self._build()
        self.role_task = self._make_role_task("Mentor Training", self.mentor_role)
        self.mentor = User.objects.create_user(email="mentor@t.com", password="pw")
        self._grant_role(self.mentor, self.mentor_role)

    def test_first_toggle_lazily_creates_the_completion_row(self):
        self.assertFalse(
            RoleTaskCompletion.objects.filter(role_task=self.role_task, user=self.mentor).exists()
        )

        self.client.force_authenticate(user=self.mentor)
        response = self.client.post(_toggle_url(self.role_task.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["completed"])
        completion = RoleTaskCompletion.objects.get(role_task=self.role_task, user=self.mentor)
        self.assertTrue(completion.completed)

    def test_toggle_flips_back(self):
        self.client.force_authenticate(user=self.mentor)
        self.client.post(_toggle_url(self.role_task.id))
        response = self.client.post(_toggle_url(self.role_task.id))
        self.assertFalse(response.data["completed"])

    def test_explicit_completed_value_is_respected(self):
        self.client.force_authenticate(user=self.mentor)
        response = self.client.post(_toggle_url(self.role_task.id), {"completed": True})
        self.assertTrue(response.data["completed"])
        # Setting the same value again is idempotent, not a flip.
        response = self.client.post(_toggle_url(self.role_task.id), {"completed": True})
        self.assertTrue(response.data["completed"])

    def test_completions_are_independent_per_user(self):
        other_mentor = User.objects.create_user(email="other@t.com", password="pw")
        self._grant_role(other_mentor, self.mentor_role)

        self.client.force_authenticate(user=self.mentor)
        self.client.post(_toggle_url(self.role_task.id), {"completed": True})

        self.client.force_authenticate(user=other_mentor)
        response = self.client.get(MINE_URL)
        self.assertFalse(response.data[0]["completed"])

    def test_user_without_the_role_cannot_toggle(self):
        outsider = User.objects.create_user(email="outsider@t.com", password="pw")
        self.client.force_authenticate(user=outsider)
        response = self.client.post(_toggle_url(self.role_task.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_toggle_without_holding_the_role(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(_toggle_url(self.role_task.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_toggling_twice_does_not_create_duplicate_completion_rows(self):
        self.client.force_authenticate(user=self.mentor)
        self.client.post(_toggle_url(self.role_task.id), {"completed": True})
        self.client.post(_toggle_url(self.role_task.id), {"completed": True})
        self.assertEqual(
            RoleTaskCompletion.objects.filter(role_task=self.role_task, user=self.mentor).count(),
            1,
        )

    def test_completion_persists_after_role_revocation_but_task_stops_appearing(self):
        # Judgment call (flagged separately for confirmation): revoking a role
        # does NOT delete the user's completion history for tasks under that
        # role. It just becomes unreachable via /mine/ until — if ever — they
        # regain the role, at which point their old completion state resurfaces
        # unchanged. This mirrors Task's own never-hard-delete philosophy.
        self.client.force_authenticate(user=self.mentor)
        self.client.post(_toggle_url(self.role_task.id), {"completed": True})

        RoleAssignmentHistory.objects.filter(user=self.mentor, role=self.mentor_role).update(
            valid_to=timezone.now() - timedelta(minutes=1)
        )

        # The row is untouched in the database...
        completion = RoleTaskCompletion.objects.get(role_task=self.role_task, user=self.mentor)
        self.assertTrue(completion.completed)
        # ...but no longer visible or reachable through the API.
        self.assertEqual(self.client.get(MINE_URL).data, [])
        response = self.client.post(_toggle_url(self.role_task.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Regaining the role brings the old completion state straight back.
        self._grant_role(self.mentor, self.mentor_role)
        response = self.client.get(MINE_URL)
        self.assertTrue(response.data[0]["completed"])


class RoleTaskMultipleRolesAndOrderingTests(_World, APITestCase):
    def setUp(self):
        self._build()

    def test_user_with_two_roles_sees_role_tasks_for_both_with_no_duplicates(self):
        # RoleAssignmentHistory has no exclusivity constraint — nothing stops a
        # user holding two roles at once (e.g. a mentor who is also a
        # supervisor). Confirm the list covers both roles and never double-lists.
        supervisor_role = Roles.objects.create(role_name="supervisor")
        mentor_task = self._make_role_task("Mentor Training", self.mentor_role)
        supervisor_task = self._make_role_task("Supervisor Training", supervisor_role)
        self._make_role_task("Student Handbook", self.student_role)

        user = User.objects.create_user(email="dual@t.com", password="pw")
        self._grant_role(user, self.mentor_role)
        self._grant_role(user, supervisor_role)

        self.client.force_authenticate(user=user)
        ids = [item["id"] for item in self.client.get(MINE_URL).data]
        self.assertCountEqual(ids, [mentor_task.id, supervisor_task.id])
        self.assertEqual(len(ids), len(set(ids)))

    def test_overlapping_duplicate_role_assignments_do_not_duplicate_the_role_task(self):
        # Two live RoleAssignmentHistory rows for the SAME role (a redundant
        # grant) must still surface the role task exactly once.
        role_task = self._make_role_task("Mentor Training", self.mentor_role)
        user = User.objects.create_user(email="twice@t.com", password="pw")
        self._grant_role(user, self.mentor_role)
        self._grant_role(user, self.mentor_role)

        self.client.force_authenticate(user=user)
        ids = [item["id"] for item in self.client.get(MINE_URL).data]
        self.assertEqual(ids, [role_task.id])

    def test_user_with_no_matching_role_sees_zero_role_tasks_but_keeps_their_own_tasks(self):
        # No merge exists between Task and RoleTask (see conversation) — this
        # proves the two endpoints independently give a user their full
        # picture: role_task list is empty, but their ordinary Task rows
        # (from the untouched general /api/v1/tasks/ pipeline) still show.
        self._make_role_task("Mentor Training", self.mentor_role)
        group = Groups.objects.create(group_name="Group-X")
        student = User.objects.create_user(email="student@t.com", password="pw")
        GroupMembership.objects.create(
            group=group, user=student,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        own_task = Task.objects.create(
            name="My individual task", task_type=TaskType.INDIVIDUAL,
            assigned_user=student, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )

        self.client.force_authenticate(user=student)
        self.assertEqual(self.client.get(MINE_URL).data, [])
        general_response = self.client.get("/api/v1/tasks/")
        self.assertEqual(
            [t["id"] for t in general_response.data["results"]], [own_task.id]
        )

    def test_ordering_by_due_date_is_correct_among_dated_role_tasks(self):
        # NULL-due-date ordering is a DB-default discrepancy (SQLite sorts
        # NULL first ascending; Postgres sorts NULL last) that nothing in the
        # application explicitly decided — flagged separately. This test only
        # asserts ordering among role tasks that DO have a due date, which is
        # identical on both engines.
        later = self._make_role_task("Later", self.mentor_role)
        later.due_date = timezone.now() + timedelta(days=10)
        later.save(update_fields=["due_date"])

        sooner = self._make_role_task("Sooner", self.mentor_role)
        sooner.due_date = timezone.now() + timedelta(days=1)
        sooner.save(update_fields=["due_date"])

        no_date = self._make_role_task("No date", self.mentor_role)

        user = User.objects.create_user(email="orderer@t.com", password="pw")
        self._grant_role(user, self.mentor_role)
        self.client.force_authenticate(user=user)

        ids = [item["id"] for item in self.client.get(MINE_URL).data]
        dated_ids = [i for i in ids if i != no_date.id]
        self.assertEqual(dated_ids, [sooner.id, later.id])
        # Document (not assert a specific position for) the DB-default split:
        self.assertEqual(set(ids), {sooner.id, later.id, no_date.id})


class RoleTaskModelTests(TestCase):
    """Model-level behavior, independent of the API surface."""

    def setUp(self):
        self.admin = User.objects.create_user(email="admin@t.com", password="pw")
        AdminScope.objects.create(user=self.admin)
        self.mentor_role = Roles.objects.create(role_name="mentor")

    def test_create_with_valid_role_succeeds(self):
        role_task = RoleTask.objects.create(
            name="Onboarding", role=self.mentor_role,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.assertIsNotNone(role_task.id)
        self.assertEqual(role_task.role_id, self.mentor_role.id)

    def test_soft_delete_excludes_from_active_queryset(self):
        role_task = RoleTask.objects.create(
            name="Onboarding", role=self.mentor_role,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.assertIn(role_task, RoleTask.objects.active())

        role_task.soft_delete()

        self.assertNotIn(role_task, RoleTask.objects.active())
        # Soft delete, not hard delete — the row still exists.
        self.assertTrue(RoleTask.objects.filter(id=role_task.id).exists())

    def test_role_task_completion_unique_constraint_holds(self):
        role_task = RoleTask.objects.create(
            name="Onboarding", role=self.mentor_role,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        user = User.objects.create_user(email="mentor@t.com", password="pw")
        RoleTaskCompletion.objects.create(role_task=role_task, user=user)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RoleTaskCompletion.objects.create(role_task=role_task, user=user)

        # The failed insert didn't corrupt the surviving row.
        self.assertEqual(
            RoleTaskCompletion.objects.filter(role_task=role_task, user=user).count(), 1
        )


class RoleTaskMigrationTests(TestCase):
    """`config.settings_test` disables MIGRATION_MODULES (tables are built
    straight from current model state), so migration 0012 never actually runs
    in this suite — see conversation. What we CAN verify without a real
    migration run: the migration is additive-only and never touches the
    existing `task` table, so it cannot be the thing that corrupts pre-existing
    fanned-out Task rows if it were applied to a database that has them."""

    def test_migration_0012_never_touches_the_task_model(self):
        module = import_module(
            "apps.tasks.migrations.0012_roletask_roletaskcompletion_and_more"
        )
        touched_models = {
            op.model_name.lower()
            for op in module.Migration.operations
            if hasattr(op, "model_name")
        }
        self.assertEqual(touched_models, {"roletask", "roletaskcompletion"})
        self.assertNotIn("task", touched_models)
