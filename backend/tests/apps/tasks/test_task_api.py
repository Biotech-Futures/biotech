from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.tasks.models import CreatorRole, Task, TaskType
from apps.users.models import AdminScope, StudentProfile, SupervisorProfile

User = get_user_model()

LIST_URL = "/api/v1/tasks/"


def _detail_url(pk):
    return f"/api/v1/tasks/{pk}/"


def _toggle_url(pk):
    return f"/api/v1/tasks/{pk}/check/"


class _World:
    def _build(self):
        country = Countries.objects.create(country_name="AU-T")
        state = CountryStates.objects.create(country=country, state_name="VIC-T")
        self.track_one = Tracks.objects.create(track_name="VIC-T-01", state=state)
        self.track_two = Tracks.objects.create(track_name="VIC-T-02", state=state)
        self.group_a = Groups.objects.create(group_name="T-Group-A", track=self.track_one)
        self.group_b = Groups.objects.create(group_name="T-Group-B", track=self.track_one)
        self.group_c = Groups.objects.create(group_name="T-Group-C", track=self.track_two)

        self.global_admin = User.objects.create_user(
            email="ga@t.com", password="pw", is_staff=True
        )
        self.track_one_admin = User.objects.create_user(email="t1a@t.com", password="pw")
        self.track_two_admin = User.objects.create_user(email="t2a@t.com", password="pw")
        self.mentor_a = User.objects.create_user(email="ma@t.com", password="pw")
        self.mentor_b = User.objects.create_user(email="mb@t.com", password="pw")
        self.supervisor_a = User.objects.create_user(email="sa@t.com", password="pw")
        self.supervisor_b = User.objects.create_user(email="sb@t.com", password="pw")
        self.student_x = User.objects.create_user(email="sx@t.com", password="pw")
        self.student_y = User.objects.create_user(email="sy@t.com", password="pw")
        self.student_z = User.objects.create_user(email="sz@t.com", password="pw")
        self.outsider = User.objects.create_user(email="out@t.com", password="pw")

        AdminScope.objects.create(user=self.track_one_admin, track=self.track_one, is_global=False)
        AdminScope.objects.create(user=self.track_two_admin, track=self.track_two, is_global=False)

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
            created_by=self.global_admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.task_c_group = Task.objects.create(
            name="GA-task-C", task_type=TaskType.GROUP, group=self.group_c,
            created_by=self.global_admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.task_x_indiv = Task.objects.create(
            name="GA-indiv-X", task_type=TaskType.INDIVIDUAL, assigned_user=self.student_x,
            created_by=self.global_admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )

    def test_anonymous_blocked(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_global_admin_sees_all(self):
        self.client.force_authenticate(user=self.global_admin)
        response = self.client.get(LIST_URL)
        ids = {r["id"] for r in response.data["results"]}
        self.assertIn(self.task_a_group.id, ids)
        self.assertIn(self.task_c_group.id, ids)
        self.assertIn(self.task_x_indiv.id, ids)

    def test_track_admin_scoped_to_track(self):
        self.client.force_authenticate(user=self.track_one_admin)
        response = self.client.get(LIST_URL)
        ids = {r["id"] for r in response.data["results"]}
        self.assertIn(self.task_a_group.id, ids)
        self.assertIn(self.task_x_indiv.id, ids)
        self.assertNotIn(self.task_c_group.id, ids)

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

    def test_global_admin_creates_anywhere(self):
        self.client.force_authenticate(user=self.global_admin)
        for group in (self.group_a, self.group_c):
            r = self.client.post(LIST_URL, self._group_payload(group), format="json")
            self.assertEqual(r.status_code, status.HTTP_201_CREATED)
            self.assertEqual(r.data["creator_role"], CreatorRole.GLOBAL_ADMIN)
        r = self.client.post(LIST_URL, self._individual_payload(self.student_z), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_track_admin_creates_in_track(self):
        self.client.force_authenticate(user=self.track_one_admin)
        r = self.client.post(LIST_URL, self._group_payload(self.group_a), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["creator_role"], CreatorRole.TRACK_ADMIN)

    def test_track_admin_blocked_outside_track(self):
        self.client.force_authenticate(user=self.track_one_admin)
        r = self.client.post(LIST_URL, self._group_payload(self.group_c), format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_mentor_creates_group_task_in_own_group(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(LIST_URL, self._group_payload(self.group_a), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["creator_role"], CreatorRole.MENTOR)

    def test_mentor_creates_individual_for_student_in_their_group(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(LIST_URL, self._individual_payload(self.student_x), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["creator_role"], CreatorRole.MENTOR)

    def test_mentor_blocked_individual_outside_group(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(LIST_URL, self._individual_payload(self.student_z), format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_creates_group_task_for_group_with_supervisee(self):
        self.client.force_authenticate(user=self.supervisor_a)
        r = self.client.post(LIST_URL, self._group_payload(self.group_a), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["creator_role"], CreatorRole.SUPERVISOR)

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
        self.client.force_authenticate(user=self.global_admin)
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
        self.client.force_authenticate(user=self.global_admin)
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
            created_by=self.global_admin, creator_role=CreatorRole.GLOBAL_ADMIN,
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

    def test_global_admin_can_edit_anything(self):
        self.client.force_authenticate(user=self.global_admin)
        for t in (self.admin_task, self.mentor_task, self.supervisor_task, self.student_indiv):
            r = self.client.patch(_detail_url(t.id), {"name": "renamed"}, format="json")
            self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_track_admin_in_scope_can_edit_anything_in_track(self):
        self.client.force_authenticate(user=self.track_one_admin)
        r = self.client.patch(_detail_url(self.mentor_task.id), {"name": "renamed"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_track_admin_outside_scope_blocked(self):
        self.client.force_authenticate(user=self.track_two_admin)
        r = self.client.patch(_detail_url(self.mentor_task.id), {"name": "x"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_mentor_creator_can_edit_own_task(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.patch(_detail_url(self.mentor_task.id), {"name": "renamed"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_mentor_cannot_edit_supervisor_task(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.patch(_detail_url(self.supervisor_task.id), {"name": "x"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_cannot_edit_mentor_task(self):
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
            created_by=self.global_admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        self.child = Task.objects.create(
            name="child", task_type=TaskType.GROUP, group=self.group_a,
            parent=self.parent,
            created_by=self.global_admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )

    def test_soft_delete_returns_object_and_marks_deleted(self):
        self.client.force_authenticate(user=self.global_admin)
        r = self.client.delete(_detail_url(self.parent.id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r.data["deleted_at"])

    def test_soft_delete_cascades_to_children(self):
        self.client.force_authenticate(user=self.global_admin)
        self.client.delete(_detail_url(self.parent.id))
        self.parent.refresh_from_db()
        self.child.refresh_from_db()
        self.assertIsNotNone(self.parent.deleted_at)
        self.assertIsNotNone(self.child.deleted_at)

    def test_student_cannot_delete_admin_task(self):
        self.client.force_authenticate(user=self.student_x)
        r = self.client.delete(_detail_url(self.parent.id))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class GroupTaskToggleTests(_World, APITestCase):
    def setUp(self):
        self._build()
        self.gtask = Task.objects.create(
            name="gtask", task_type=TaskType.GROUP, group=self.group_a,
            created_by=self.global_admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )

    def test_admin_can_toggle(self):
        self.client.force_authenticate(user=self.global_admin)
        r = self.client.post(_toggle_url(self.gtask.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["completed"])

    def test_mentor_can_toggle(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(_toggle_url(self.gtask.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_supervisor_auto_added_can_toggle(self):
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
        self.client.force_authenticate(user=self.global_admin)
        r = self.client.post(_toggle_url(self.gtask.id), {"completed": False}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data["completed"])


class IndividualToggleStudentAssigneeTests(_World, APITestCase):
    """Case 1: assignee is a Student."""

    def setUp(self):
        self._build()
        self.admin_indiv = Task.objects.create(
            name="ai", task_type=TaskType.INDIVIDUAL, assigned_user=self.student_x,
            created_by=self.global_admin, creator_role=CreatorRole.GLOBAL_ADMIN,
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
            created_by=self.global_admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )

    def test_assignee_mentor_can_toggle(self):
        self.client.force_authenticate(user=self.mentor_a)
        r = self.client.post(_toggle_url(self.mentor_assigned.id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_admin_can_toggle(self):
        self.client.force_authenticate(user=self.global_admin)
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
