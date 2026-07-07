from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.groups.models import GroupMembership, Groups
from apps.tasks.models import CreatorRole, Task, TaskType
from apps.users.models import AdminScope, StudentProfile, SupervisorProfile

User = get_user_model()

LIST_URL = "/api/v1/tasks/"


def _detail_url(pk):
    return f"/api/v1/tasks/{pk}/"


def _restore_url(pk):
    return f"/api/v1/tasks/{pk}/restore/"


def _toggle_url(pk):
    return f"/api/v1/tasks/{pk}/check/"


class _World:
    """Shared fixture. Geography (tracks/states) was removed from the domain;
    task visibility is now driven purely by group membership and supervision,
    and admin is a single global tier (any AdminScope row = admin)."""

    def _build(self):
        self.group_a = Groups.objects.create(group_name="Group-A")
        self.group_b = Groups.objects.create(group_name="Group-B")
        self.group_c = Groups.objects.create(group_name="Group-C")

        self.admin = User.objects.create_user(email="ga@t.com", password="pw")
        self.mentor_a = User.objects.create_user(email="ma@t.com", password="pw")
        self.mentor_b = User.objects.create_user(email="mb@t.com", password="pw")
        self.supervisor_a = User.objects.create_user(email="sa@t.com", password="pw")
        self.supervisor_b = User.objects.create_user(email="sb@t.com", password="pw")
        self.student_x = User.objects.create_user(email="sx@t.com", password="pw")
        self.student_y = User.objects.create_user(email="sy@t.com", password="pw")
        self.student_z = User.objects.create_user(email="sz@t.com", password="pw")
        self.outsider = User.objects.create_user(email="out@t.com", password="pw")

        # Single-tier admin: one AdminScope row is all admin-ness there is.
        AdminScope.objects.create(user=self.admin)

        GroupMembership.objects.create(
            group=self.group_a,
            user=self.mentor_a,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        GroupMembership.objects.create(
            group=self.group_c,
            user=self.mentor_b,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        for stu, group in (
            (self.student_x, self.group_a),
            (self.student_y, self.group_a),
            (self.student_z, self.group_c),
        ):
            GroupMembership.objects.create(
                group=group,
                user=stu,
                membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            )

        sup_a_profile = SupervisorProfile.objects.create(user=self.supervisor_a, school_name="S")
        sup_b_profile = SupervisorProfile.objects.create(user=self.supervisor_b, school_name="S")

        StudentProfile.objects.create(
            user=self.student_x, pg_first_name="P", pg_last_name="G",
            school_name="School", year_lvl="9", supervisor=sup_a_profile,
        )
        StudentProfile.objects.create(
            user=self.student_y, pg_first_name="P", pg_last_name="G",
            school_name="School", year_lvl="9", supervisor=sup_a_profile,
        )
        StudentProfile.objects.create(
            user=self.student_z, pg_first_name="P", pg_last_name="G",
            school_name="School", year_lvl="9", supervisor=sup_b_profile,
        )


class TaskListVisibilityTests(_World, APITestCase):
    def setUp(self):
        self._build()

        self.task_a_group = Task.objects.create(
            name="GA-task-A", task_type=TaskType.GROUP, group=self.group_a,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.task_c_group = Task.objects.create(
            name="GA-task-C", task_type=TaskType.GROUP, group=self.group_c,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.task_x_indiv = Task.objects.create(
            name="GA-indiv-X", task_type=TaskType.INDIVIDUAL, assigned_user=self.student_x,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )

    def test_anonymous_blocked(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_sees_all(self):
        # Single global admin tier sees every task regardless of group.
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(LIST_URL)
        ids = {r["id"] for r in response.data["results"]}
        self.assertIn(self.task_a_group.id, ids)
        self.assertIn(self.task_c_group.id, ids)
        self.assertIn(self.task_x_indiv.id, ids)

    def test_mentor_sees_their_group_and_assigned_individuals(self):
        self.client.force_authenticate(user=self.mentor_a)
        response = self.client.get(LIST_URL)
        ids = {r["id"] for r in response.data["results"]}
        self.assertIn(self.task_a_group.id, ids)
        self.assertIn(self.task_x_indiv.id, ids)
        self.assertNotIn(self.task_c_group.id, ids)

    def test_supervisor_sees_supervised_students(self):
        self.client.force_authenticate(user=self.supervisor_a)
        response = self.client.get(LIST_URL)
        ids = {r["id"] for r in response.data["results"]}
        self.assertIn(self.task_a_group.id, ids)
        self.assertIn(self.task_x_indiv.id, ids)
        self.assertNotIn(self.task_c_group.id, ids)

    def test_student_sees_own_group_and_own_individual(self):
        self.client.force_authenticate(user=self.student_x)
        response = self.client.get(LIST_URL)
        ids = {r["id"] for r in response.data["results"]}
        self.assertIn(self.task_a_group.id, ids)
        self.assertIn(self.task_x_indiv.id, ids)
        self.assertNotIn(self.task_c_group.id, ids)

    def test_outsider_sees_nothing(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(LIST_URL)
        ids = {r["id"] for r in response.data["results"]}
        self.assertEqual(ids, set())


class TaskCreateTests(_World, APITestCase):
    def setUp(self):
        self._build()

    def _group_payload(self, group):
        return {"name": "G-task", "task_type": "group", "group": group.id}

    def _individual_payload(self, user):
        return {"name": "I-task", "task_type": "individual", "assigned_user": user.id}

    def test_admin_creates_anywhere(self):
        self.client.force_authenticate(user=self.admin)
        for group in (self.group_a, self.group_c):
            r = self.client.post(LIST_URL, self._group_payload(group), format="json")
            self.assertEqual(r.status_code, status.HTTP_201_CREATED)
            self.assertEqual(r.data["creator_role"], CreatorRole.GLOBAL_ADMIN)
        r = self.client.post(LIST_URL, self._individual_payload(self.student_z), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_mentor_creates_group_task_in_own_group(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(LIST_URL, self._group_payload(self.group_a), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["creator_role"], CreatorRole.MENTOR)

    def test_mentor_blocked_group_task_outside_own_group(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(LIST_URL, self._group_payload(self.group_c), format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_mentor_creates_individual_for_student_in_their_group(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(LIST_URL, self._individual_payload(self.student_x), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["creator_role"], CreatorRole.MENTOR)

    def test_mentor_blocked_individual_outside_group(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(LIST_URL, self._individual_payload(self.student_z), format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_blocked_creating_group_task_for_group_with_supervisee(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.post(LIST_URL, self._group_payload(self.group_a), format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_creates_individual_for_supervisee(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.post(LIST_URL, self._individual_payload(self.student_x), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["creator_role"], CreatorRole.SUPERVISOR)

    def test_supervisor_blocked_individual_for_unrelated_student(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.post(LIST_URL, self._individual_payload(self.student_z), format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_can_create_individual_for_self(self):
        self.client.force_authenticate(user=self.student_x)
        r = self.client.post(LIST_URL, self._individual_payload(self.student_x), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["creator_role"], CreatorRole.STUDENT)
        self.assertEqual(r.data["assigned_user"], self.student_x.id)

    def test_student_blocked_creating_for_other_user(self):
        self.client.force_authenticate(user=self.student_x)
        r = self.client.post(LIST_URL, self._individual_payload(self.student_y), format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_blocked_creating_group_task(self):
        self.client.force_authenticate(user=self.student_x)
        r = self.client.post(LIST_URL, self._group_payload(self.group_a), format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_create(self):
        r = self.client.post(LIST_URL, self._group_payload(self.group_a), format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_rejects_group_with_assigned_user(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(
            LIST_URL,
            {
                "name": "bad",
                "task_type": "group",
                "group": self.group_a.id,
                "assigned_user": self.student_x.id,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_rejects_individual_with_group(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(
            LIST_URL,
            {
                "name": "bad",
                "task_type": "individual",
                "group": self.group_a.id,
                "assigned_user": self.student_x.id,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class TaskOwnershipTests(_World, APITestCase):
    def setUp(self):
        self._build()
        self.admin_task = Task.objects.create(
            name="admin-G-A", task_type=TaskType.GROUP, group=self.group_a,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.mentor_task = Task.objects.create(
            name="mentor-G-A", task_type=TaskType.GROUP, group=self.group_a,
            created_by=self.mentor_a, creator_role=CreatorRole.MENTOR,
        )
        self.supervisor_task = Task.objects.create(
            name="sup-G-A", task_type=TaskType.GROUP, group=self.group_a,
            created_by=self.supervisor_a, creator_role=CreatorRole.SUPERVISOR,
        )
        self.student_indiv = Task.objects.create(
            name="student-self", task_type=TaskType.INDIVIDUAL, assigned_user=self.student_x,
            created_by=self.student_x, creator_role=CreatorRole.STUDENT,
        )

    def test_admin_can_edit_anything(self):
        self.client.force_authenticate(user=self.admin)
        for t in (self.admin_task, self.mentor_task, self.supervisor_task, self.student_indiv):
            r = self.client.patch(_detail_url(t.id), {"name": "renamed"}, format="json")
            self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_mentor_creator_can_edit_own_task(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.patch(_detail_url(self.mentor_task.id), {"name": "renamed"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_mentor_can_edit_supervisor_task_within_group(self):
        # Mentor of group_a can edit any group_a task regardless of creator role.
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.patch(_detail_url(self.supervisor_task.id), {"name": "x"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_supervisor_cannot_edit_group_task_within_supervised_group(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.patch(_detail_url(self.mentor_task.id), {"name": "x"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_creator_can_edit_own_task(self):
        self.client.force_authenticate(user=self.student_x)
        r = self.client.patch(_detail_url(self.student_indiv.id), {"name": "x"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_mentor_can_edit_student_task_within_reach(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.patch(_detail_url(self.student_indiv.id), {"name": "x"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_supervisor_can_edit_student_task_within_reach(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.patch(_detail_url(self.student_indiv.id), {"name": "x"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_unrelated_mentor_cannot_edit_student_task(self):
        self.client.force_authenticate(user=self.mentor_b)
        r = self.client.patch(_detail_url(self.student_indiv.id), {"name": "x"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_unrelated_supervisor_cannot_edit_student_task(self):
        self.client.force_authenticate(user=self.supervisor_b)
        r = self.client.patch(_detail_url(self.student_indiv.id), {"name": "x"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_cannot_edit_admin_task(self):
        self.client.force_authenticate(user=self.student_x)
        r = self.client.patch(_detail_url(self.admin_task.id), {"name": "x"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class TaskDeleteTests(_World, APITestCase):
    def setUp(self):
        self._build()
        self.parent = Task.objects.create(
            name="parent", task_type=TaskType.GROUP, group=self.group_a,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.child = Task.objects.create(
            name="child", task_type=TaskType.GROUP, group=self.group_a,
            parent=self.parent,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )

    def test_soft_delete_returns_object_and_marks_deleted(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.delete(_detail_url(self.parent.id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r.data["deleted_at"])

    def test_soft_delete_cascades_to_children(self):
        self.client.force_authenticate(user=self.admin)
        self.client.delete(_detail_url(self.parent.id))
        self.parent.refresh_from_db()
        self.child.refresh_from_db()
        self.assertIsNotNone(self.parent.deleted_at)
        self.assertIsNotNone(self.child.deleted_at)

    def test_restore_parent_cascades_matching_deleted_children(self):
        # Restore cascades only through children tombstoned by the same delete.
        self.client.force_authenticate(user=self.admin)
        self.client.delete(_detail_url(self.parent.id))

        r = self.client.post(_restore_url(self.parent.id))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.parent.refresh_from_db()
        self.child.refresh_from_db()
        self.assertIsNone(self.parent.deleted_at)
        self.assertIsNone(self.child.deleted_at)

    def test_deleted_filter_returns_deleted_tasks(self):
        # deleted=true is the recovery list for tasks visible to the caller.
        self.client.force_authenticate(user=self.admin)
        self.client.delete(_detail_url(self.parent.id))

        r = self.client.get(LIST_URL + "?deleted=true")

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in r.data["results"]}
        self.assertIn(self.parent.id, ids)
        self.assertIn(self.child.id, ids)

    def test_student_cannot_delete_admin_task(self):
        self.client.force_authenticate(user=self.student_x)
        r = self.client.delete(_detail_url(self.parent.id))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_assignee_can_restore_own_deleted_individual_task(self):
        task = Task.objects.create(
            name="mine",
            task_type=TaskType.INDIVIDUAL,
            assigned_user=self.student_x,
            created_by=self.mentor_a,
            creator_role=CreatorRole.MENTOR,
        )
        task.soft_delete()

        self.client.force_authenticate(user=self.student_x)
        r = self.client.post(_restore_url(task.id))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.data["deleted_at"])

    def test_supervisor_cannot_delete_group_task(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.delete(_detail_url(self.parent.id))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class GroupTaskToggleTests(_World, APITestCase):
    def setUp(self):
        self._build()
        self.gtask = Task.objects.create(
            name="gtask", task_type=TaskType.GROUP, group=self.group_a,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )

    def test_admin_can_toggle(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(_toggle_url(self.gtask.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["completed"])

    def test_mentor_can_toggle(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(_toggle_url(self.gtask.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_supervisor_of_group_member_can_toggle(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.post(_toggle_url(self.gtask.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_student_cannot_toggle_group_task(self):
        self.client.force_authenticate(user=self.student_x)
        r = self.client.post(_toggle_url(self.gtask.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_explicit_set(self):
        self.gtask.completed = True
        self.gtask.save(update_fields=["completed"])
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(_toggle_url(self.gtask.id), {"completed": False}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data["completed"])


class IndividualToggleStudentAssigneeTests(_World, APITestCase):
    """Case 1: assignee is a Student."""

    def setUp(self):
        self._build()
        self.admin_indiv = Task.objects.create(
            name="ai", task_type=TaskType.INDIVIDUAL, assigned_user=self.student_x,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.mentor_indiv = Task.objects.create(
            name="mi", task_type=TaskType.INDIVIDUAL, assigned_user=self.student_x,
            created_by=self.mentor_a, creator_role=CreatorRole.MENTOR,
        )
        self.sup_indiv = Task.objects.create(
            name="si", task_type=TaskType.INDIVIDUAL, assigned_user=self.student_x,
            created_by=self.supervisor_a, creator_role=CreatorRole.SUPERVISOR,
        )
        self.student_indiv = Task.objects.create(
            name="stui", task_type=TaskType.INDIVIDUAL, assigned_user=self.student_x,
            created_by=self.student_x, creator_role=CreatorRole.STUDENT,
        )

    def test_assignee_can_always_toggle(self):
        self.client.force_authenticate(user=self.student_x)
        for t in (self.admin_indiv, self.mentor_indiv, self.sup_indiv, self.student_indiv):
            r = self.client.post(_toggle_url(t.id), {}, format="json")
            self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_mentor_can_toggle_admin_or_mentor_created(self):
        self.client.force_authenticate(user=self.mentor_a)
        for t in (self.admin_indiv, self.mentor_indiv, self.student_indiv):
            r = self.client.post(_toggle_url(t.id), {}, format="json")
            self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_mentor_cannot_toggle_supervisor_created(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(_toggle_url(self.sup_indiv.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_can_toggle_admin_or_supervisor_created(self):
        self.client.force_authenticate(user=self.supervisor_a)
        for t in (self.admin_indiv, self.sup_indiv, self.student_indiv):
            r = self.client.post(_toggle_url(t.id), {}, format="json")
            self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_supervisor_cannot_toggle_mentor_created(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.post(_toggle_url(self.mentor_indiv.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class IndividualToggleNonStudentAssigneeTests(_World, APITestCase):
    """Case 2: assignee is a Mentor / Supervisor / Admin — only assignee + Admin toggles."""

    def setUp(self):
        self._build()
        self.mentor_assigned = Task.objects.create(
            name="m-assigned", task_type=TaskType.INDIVIDUAL, assigned_user=self.mentor_a,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )

    def test_assignee_mentor_can_toggle(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(_toggle_url(self.mentor_assigned.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_admin_can_toggle(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(_toggle_url(self.mentor_assigned.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_other_mentor_cannot_toggle(self):
        self.client.force_authenticate(user=self.mentor_b)
        r = self.client.post(_toggle_url(self.mentor_assigned.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_cannot_toggle(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.post(_toggle_url(self.mentor_assigned.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_toggle(self):
        self.client.force_authenticate(user=self.student_x)
        r = self.client.post(_toggle_url(self.mentor_assigned.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# New filters (status / completed / due_date_*) + search + ordering + bulk
# toggle. Covers shape, not the visibility rules retested above.
# ---------------------------------------------------------------------------


class TaskListNewFiltersTests(_World, APITestCase):
    def setUp(self):
        self._build()
        now = timezone.now()
        self.todo = Task.objects.create(
            name="todo task", task_type=TaskType.GROUP, group=self.group_a,
            status="todo", completed=False,
            due_date=now + timezone.timedelta(days=7),
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.done = Task.objects.create(
            name="done task", task_type=TaskType.GROUP, group=self.group_a,
            status="done", completed=True,
            due_date=now - timezone.timedelta(days=1),
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.client.force_authenticate(user=self.admin)

    def test_filter_status(self):
        r = self.client.get(LIST_URL + "?status=done")
        ids = {row["id"] for row in r.data["results"]}
        self.assertEqual(ids, {self.done.id})

    def test_filter_completed(self):
        r = self.client.get(LIST_URL + "?completed=true")
        ids = {row["id"] for row in r.data["results"]}
        self.assertEqual(ids, {self.done.id})

    def test_filter_due_date_before_returns_overdue(self):
        # Use a "Z" suffix so `+` URL-decoding doesn't mangle the offset.
        cutoff = timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        r = self.client.get(LIST_URL + f"?due_date_before={cutoff}")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        ids = {row["id"] for row in r.data["results"]}
        self.assertIn(self.done.id, ids)
        self.assertNotIn(self.todo.id, ids)

    def test_search_matches_name(self):
        r = self.client.get(LIST_URL + "?search=done")
        ids = {row["id"] for row in r.data["results"]}
        self.assertEqual(ids, {self.done.id})

    def test_ordering_by_due_date(self):
        r = self.client.get(LIST_URL + "?ordering=due_date")
        ids = [row["id"] for row in r.data["results"] if row["id"] in {self.todo.id, self.done.id}]
        self.assertEqual(ids, [self.done.id, self.todo.id])


class TaskBulkToggleTests(_World, APITestCase):
    def setUp(self):
        self._build()
        # Two group tasks under group_a (mentor_a is mentor) and one
        # individual task assigned to student_x.
        self.t1 = Task.objects.create(
            name="bt1", task_type=TaskType.GROUP, group=self.group_a, completed=False,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.t2 = Task.objects.create(
            name="bt2", task_type=TaskType.GROUP, group=self.group_a, completed=False,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.t_indiv = Task.objects.create(
            name="bt-indiv", task_type=TaskType.INDIVIDUAL, assigned_user=self.student_x,
            completed=False, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )

    def _url(self):
        return "/api/v1/tasks/bulk/check/"

    def test_admin_bulk_set_completed_true(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(
            self._url(),
            {"task_ids": [self.t1.id, self.t2.id], "completed": True},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(len(r.data["updated"]), 2)
        self.t1.refresh_from_db(); self.t2.refresh_from_db()
        self.assertTrue(self.t1.completed and self.t2.completed)

    def test_bulk_flips_when_no_completed_provided(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(self._url(), {"task_ids": [self.t1.id]}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.t1.refresh_from_db()
        self.assertTrue(self.t1.completed)

    def test_unknown_ids_go_to_not_found(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(
            self._url(),
            {"task_ids": [self.t1.id, 999999]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn(999999, r.data["not_found"])

    def test_forbidden_ids_listed_separately(self):
        # student_x cannot toggle a group task (only the assigned indiv).
        self.client.force_authenticate(user=self.student_x)
        r = self.client.post(
            self._url(),
            {"task_ids": [self.t1.id, self.t_indiv.id]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn(self.t1.id, r.data["forbidden"])
        self.assertEqual([row["id"] for row in r.data["updated"]], [self.t_indiv.id])

    def test_empty_task_ids_rejected(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(self._url(), {"task_ids": []}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


def _status_url(pk):
    return f"/api/v1/tasks/{pk}/status/"


class TaskStatusUpdateTests(_World, APITestCase):
    """POST /api/v1/tasks/<id>/status/ -- in-place status change.

    Permissions mirror the toggle endpoint (CanToggleTask). Setting status to
    'done' also flips `completed=True`; any other status flips it to False.
    """

    def setUp(self):
        self._build()
        self.group_task = Task.objects.create(
            name="Status A1", task_type=TaskType.GROUP, group=self.group_a,
            created_by=self.mentor_a, creator_role=CreatorRole.MENTOR,
            status="todo", completed=False,
        )
        self.indiv_task = Task.objects.create(
            name="Status X1", task_type=TaskType.INDIVIDUAL, assigned_user=self.student_x,
            created_by=self.student_x, creator_role=CreatorRole.STUDENT,
            status="todo", completed=False,
        )

    # --- happy paths -------------------------------------------------------
    def test_mentor_can_set_group_task_status(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(_status_url(self.group_task.id), {"status": "in_progress"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], "in_progress")
        self.assertFalse(r.data["completed"])

    def test_supervisor_can_set_group_task_status(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.post(_status_url(self.group_task.id), {"status": "in_progress"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], "in_progress")

    def test_assignee_can_set_their_own_individual_task_status(self):
        self.client.force_authenticate(user=self.student_x)
        r = self.client.post(_status_url(self.indiv_task.id), {"status": "blocked"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], "blocked")
        self.assertFalse(r.data["completed"])

    def test_setting_done_sets_completed_true(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(_status_url(self.group_task.id), {"status": "done"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], "done")
        self.assertTrue(r.data["completed"])

    def test_changing_done_to_other_clears_completed(self):
        self.group_task.status = "done"
        self.group_task.completed = True
        self.group_task.save()
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(_status_url(self.group_task.id), {"status": "in_progress"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], "in_progress")
        self.assertFalse(r.data["completed"])

    # --- forbidden paths ---------------------------------------------------
    def test_outsider_cannot_set_status(self):
        self.client.force_authenticate(user=self.outsider)
        r = self.client.post(_status_url(self.group_task.id), {"status": "done"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_unrelated_mentor_cannot_set_status(self):
        self.client.force_authenticate(user=self.mentor_b)  # mentor of group_c
        r = self.client.post(_status_url(self.group_task.id), {"status": "done"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    # --- validation --------------------------------------------------------
    def test_invalid_status_rejected(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(_status_url(self.group_task.id), {"status": "nonsense"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_status_rejected(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(_status_url(self.group_task.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class SupervisorCannotEditGroupTaskTests(_World, APITestCase):
    """Group task create/delete/restore is limited to mentors and admins."""

    def setUp(self):
        self._build()
        self.mentor_created = Task.objects.create(
            name="Mentor task", task_type=TaskType.GROUP, group=self.group_a,
            created_by=self.mentor_a, creator_role=CreatorRole.MENTOR,
        )
        self.admin_created = Task.objects.create(
            name="Admin task", task_type=TaskType.GROUP, group=self.group_a,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )

    def test_supervisor_cannot_patch_mentor_created_group_task(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.patch(
            _detail_url(self.mentor_created.id), {"name": "Renamed by supervisor"}, format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_cannot_patch_admin_created_group_task(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.patch(
            _detail_url(self.admin_created.id), {"name": "Renamed"}, format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_unrelated_supervisor_cannot_patch_group_task(self):
        # supervisor_b supervises student_z (group_c) only, not group_a. The
        # visibility filter excludes the task from their queryset, so the
        # detail view returns 404 rather than 403.
        self.client.force_authenticate(user=self.supervisor_b)
        r = self.client.patch(
            _detail_url(self.mentor_created.id), {"name": "Nope"}, format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_supervisor_cannot_delete_group_task(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.delete(_detail_url(self.mentor_created.id))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
