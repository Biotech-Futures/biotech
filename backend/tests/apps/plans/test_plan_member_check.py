"""GP3 completion: POST /api/v1/plans/groups/<group_id>/tasks/<task_id>/check/.

Covers who may tick what (including Will's rule that students tick
student-audience shared tasks), the 404 -> 403 -> 400 order, own-record
ownership, no-op unticks, auditing, and the transaction around the change.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.groups.models import GroupMembership, Groups
from apps.plans.models import PlanStage, PlanTask, PlanTaskCompletion
from apps.users.models import AdminScope, StudentProfile, SupervisorProfile


class GroupPlanCheckTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.group = Groups.objects.create(group_name="BTF1", year=timezone.localdate().year)
        self.other_group = Groups.objects.create(group_name="BTF2", year=timezone.localdate().year)

        def user(email, role=None, group=None):
            account = User.objects.create_user(email=email, password="pw")
            if role:
                GroupMembership.objects.create(user=account, group=group or self.group, membership_role=role)
            return account

        self.student = user("student@test.com", "student")
        self.other_student = user("student2@test.com", "student")
        self.mentor = user("mentor@test.com", "mentor")
        self.supervisor_member = user("sup.member@test.com", "supervisor")
        self.supervisor_profile_only = user("sup.profile@test.com")
        self.supervisor_unlinked = user("sup.unlinked@test.com", "supervisor")
        self.admin = user("admin@test.com")
        AdminScope.objects.create(user=self.admin)
        self.outsider = user("outsider@test.com", "student", group=self.other_group)
        self.link(self.student, self.supervisor_member)
        self.link(self.other_student, self.supervisor_profile_only)

        self.stage = PlanStage.objects.create(name="Getting started")

        def task(name, audience, mode):
            return PlanTask.objects.create(stage=self.stage, name=name, audience_role=audience, completion_mode=mode)

        self.s_indiv = task("s-indiv", "student", "per_person")
        self.s_shared = task("s-shared", "student", "per_group")
        self.m_indiv = task("m-indiv", "mentor", "per_person")
        self.m_shared = task("m-shared", "mentor", "per_group")
        self.sup_indiv = task("sup-indiv", "supervisor", "per_person")
        self.sup_shared = task("sup-shared", "supervisor", "per_group")

    def link(self, student, supervisor):
        profile, _ = SupervisorProfile.objects.get_or_create(user=supervisor, defaults={"school_name": "S"})
        StudentProfile.objects.create(
            user=student, pg_first_name="P", pg_last_name="G", school_name="S", year_lvl="10", supervisor=profile,
        )

    def check(self, user, task, body=None, group=None, task_id=None):
        client = APIClient()
        client.force_authenticate(user)
        url = reverse(
            "plans:group-plan-task-check",
            kwargs={"group_id": (group or self.group).id, "task_id": task_id or task.id},
        )
        return client.post(url, body if body is not None else {}, format="json")

    def record(self, task, user=None, group=None):
        return PlanTaskCompletion.objects.filter(task=task, group=group or self.group, user=user).first()

    def audits(self, task):
        return list(AuditLog.objects.filter(entity_type="plan_task", entity_id=task.id).order_by("id"))

    def assert_ok(self, response, completed):
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["completed"], completed)
        self.assertTrue(response.data["can_toggle"])

    # -- Individual tasks ------------------------------------------------------

    def test_student_ticks_and_unticks_their_own_individual_task(self):
        self.assert_ok(self.check(self.student, self.s_indiv, {"completed": True}), True)
        self.assertTrue(self.record(self.s_indiv, self.student).completed)

        self.assert_ok(self.check(self.student, self.s_indiv, {"completed": False}), False)
        # A tick followed by an untick keeps its record.
        self.assertFalse(self.record(self.s_indiv, self.student).completed)
        self.assertEqual(PlanTaskCompletion.objects.filter(task=self.s_indiv).count(), 1)

    def test_empty_body_flips_the_current_value(self):
        self.assert_ok(self.check(self.student, self.s_indiv), True)
        self.assert_ok(self.check(self.student, self.s_indiv), False)
        self.assert_ok(self.check(self.student, self.s_indiv), True)

    def test_only_the_requesting_users_record_changes(self):
        PlanTaskCompletion.objects.create(task=self.s_indiv, group=self.group, user=self.other_student, completed=True)
        self.assert_ok(self.check(self.student, self.s_indiv, {"completed": True}), True)
        self.assert_ok(self.check(self.student, self.s_indiv, {"completed": False}), False)
        self.assertTrue(self.record(self.s_indiv, self.other_student).completed)

    def test_a_user_id_in_the_body_is_rejected_and_changes_nothing(self):
        for body in ({"completed": True, "user_id": self.other_student.id}, {"user": self.other_student.id}):
            with self.subTest(body=body):
                self.assertEqual(self.check(self.student, self.s_indiv, body).status_code, 400)
        self.assertFalse(PlanTaskCompletion.objects.exists())
        self.assertEqual(self.audits(self.s_indiv), [])

    def test_nobody_ticks_someone_elses_individual_task(self):
        # Visible to an admin but not theirs: 403. Not visible to the others: 404.
        self.assertEqual(self.check(self.admin, self.s_indiv, {"completed": True}).status_code, 403)
        for user in (self.mentor, self.supervisor_member, self.supervisor_profile_only):
            with self.subTest(user=user.email):
                self.assertEqual(self.check(user, self.s_indiv, {"completed": True}).status_code, 404)
        self.assertFalse(PlanTaskCompletion.objects.exists())

    # -- Shared tasks ----------------------------------------------------------

    def test_students_share_the_student_audience_shared_task(self):
        # Will's rule: one student ticks, another can untick the same record.
        self.assert_ok(self.check(self.student, self.s_shared, {"completed": True}), True)
        self.assertTrue(self.record(self.s_shared).completed)
        self.assert_ok(self.check(self.other_student, self.s_shared, {"completed": False}), False)
        self.assertFalse(self.record(self.s_shared).completed)
        self.assertEqual(PlanTaskCompletion.objects.filter(task=self.s_shared).count(), 1)

        tick, untick = self.audits(self.s_shared)
        self.assertEqual(tick.actor_user, self.student)
        self.assertEqual(untick.actor_user, self.other_student)
        self.assertEqual(untick.before_state["completed"], True)
        self.assertEqual(untick.after_state["completed"], False)
        self.assertIsNone(untick.after_state["completion_user_id"])

    def test_students_cannot_reach_mentor_or_supervisor_shared_tasks(self):
        for task in (self.m_shared, self.sup_shared, self.m_indiv, self.sup_indiv):
            with self.subTest(task=task.name):
                self.assertEqual(self.check(self.student, task, {"completed": True}).status_code, 404)
        self.assertFalse(PlanTaskCompletion.objects.exists())

    def test_mentor(self):
        self.assert_ok(self.check(self.mentor, self.m_indiv, {"completed": True}), True)
        self.assertTrue(self.record(self.m_indiv, self.mentor).completed)
        for task in (self.s_shared, self.m_shared, self.sup_shared):
            with self.subTest(task=task.name):
                self.assert_ok(self.check(self.mentor, task, {"completed": True}), True)
                self.assertTrue(self.record(task).completed)

    def test_supervisor_member(self):
        self.assert_ok(self.check(self.supervisor_member, self.sup_indiv, {"completed": True}), True)
        self.assertTrue(self.record(self.sup_indiv, self.supervisor_member).completed)
        self.assert_ok(self.check(self.supervisor_member, self.m_shared, {"completed": True}), True)

    def test_supervisor_linked_only_through_a_student_profile(self):
        for task in (self.s_shared, self.m_shared, self.sup_shared):
            with self.subTest(task=task.name):
                self.assert_ok(self.check(self.supervisor_profile_only, task, {"completed": True}), True)
        # No supervisor membership, so no supervisor individual task to see.
        self.assertEqual(self.check(self.supervisor_profile_only, self.sup_indiv).status_code, 404)

    def test_admin_ticks_shared_tasks(self):
        self.assert_ok(self.check(self.admin, self.sup_shared, {"completed": True}), True)
        audit = self.audits(self.sup_shared)[0]
        self.assertEqual(audit.actor_user, self.admin)

    def test_visible_but_not_tickable_is_403(self):
        # A supervisor member with no supervisee here sees supervisor shared
        # tasks but holds no shared-tick right.
        self.assertEqual(self.check(self.supervisor_unlinked, self.sup_shared, {"completed": True}).status_code, 403)
        self.assertIsNone(self.record(self.sup_shared))

    # -- Status-code order: 404, then 403, then 400 ----------------------------

    def test_hidden_or_missing_tasks_and_groups_are_404(self):
        self.assertEqual(self.check(self.outsider, self.s_shared).status_code, 404)
        self.assertEqual(self.check(self.student, self.s_shared, task_id=999999).status_code, 404)
        self.assertEqual(self.check(self.student, self.s_shared, group=Groups(pk=999999)).status_code, 404)
        # A real group the student isn't in.
        self.assertEqual(self.check(self.student, self.s_shared, group=self.other_group).status_code, 404)

    def test_deleted_tasks_stages_and_groups_are_404(self):
        self.s_indiv.soft_delete()
        self.assertEqual(self.check(self.student, self.s_indiv).status_code, 404)

        PlanStage.objects.filter(pk=self.stage.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.check(self.student, self.s_shared).status_code, 404)

        PlanStage.objects.filter(pk=self.stage.pk).update(deleted_at=None)
        Groups.objects.filter(pk=self.group.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.check(self.student, self.s_shared).status_code, 404)
        self.assertFalse(PlanTaskCompletion.objects.exists())

    def test_previous_year_group_is_404(self):
        Groups.objects.filter(pk=self.group.pk).update(year=self.group.year - 1)
        self.assertEqual(self.check(self.student, self.s_indiv, {"completed": True}).status_code, 404)
        self.assertFalse(PlanTaskCompletion.objects.exists())

    def test_invalid_bodies_are_400(self):
        for value in (1, 0, "true", "false", None, [], {}):
            with self.subTest(value=value):
                response = self.check(self.student, self.s_indiv, {"completed": value})
                self.assertEqual(response.status_code, 400)
                self.assertIn("true or false", response.data["error"])
        self.assertEqual(self.check(self.student, self.s_indiv, ["completed"]).status_code, 400)
        self.assertEqual(self.check(self.student, self.s_indiv, {"done": True}).status_code, 400)
        self.assertFalse(PlanTaskCompletion.objects.exists())

    def test_a_bad_body_does_not_hide_a_404_or_403(self):
        bad = {"completed": "yes"}
        self.assertEqual(self.check(self.student, self.m_shared, bad).status_code, 404)
        self.assertEqual(self.check(self.admin, self.s_indiv, bad).status_code, 403)

    # -- No-ops, audit and transaction ----------------------------------------

    def test_unticking_with_no_record_creates_nothing_and_audits_nothing(self):
        for task in (self.s_indiv, self.s_shared):
            with self.subTest(task=task.name):
                self.assert_ok(self.check(self.student, task, {"completed": False}), False)
        self.assertFalse(PlanTaskCompletion.objects.exists())
        self.assertFalse(AuditLog.objects.filter(entity_type="plan_task").exists())

    def test_repeating_the_current_value_is_not_audited(self):
        self.check(self.student, self.s_indiv, {"completed": True})
        self.check(self.student, self.s_indiv, {"completed": True})
        self.assertEqual(len(self.audits(self.s_indiv)), 1)
        self.assertEqual(PlanTaskCompletion.objects.filter(task=self.s_indiv).count(), 1)

    def test_audit_records_actor_task_group_and_result(self):
        self.check(self.student, self.s_indiv, {"completed": True})
        [audit] = self.audits(self.s_indiv)
        self.assertEqual((audit.actor_user, audit.action, audit.entity_id), (self.student, "toggle", self.s_indiv.id))
        expected = {"group_id": self.group.id, "completion_mode": "per_person", "completion_user_id": self.student.id}
        self.assertEqual(audit.before_state, {**expected, "completed": False})
        self.assertEqual(audit.after_state, {**expected, "completed": True})

    def test_a_failed_audit_rolls_back_the_completion(self):
        # The project's exception handler turns the error into a 500 response.
        with patch("apps.plans.views.log_audit_event", side_effect=RuntimeError("audit down")):
            self.assertEqual(self.check(self.student, self.s_indiv, {"completed": True}).status_code, 500)
        self.assertFalse(PlanTaskCompletion.objects.exists())

    def test_the_task_row_is_locked_before_the_change(self):
        with patch.object(PlanTask.objects, "select_for_update", wraps=PlanTask.objects.select_for_update) as lock:
            self.assert_ok(self.check(self.student, self.s_shared, {"completed": True}), True)
        lock.assert_called_once_with()

    # -- Access that ends while the request waits for the task lock -----------
    # The change is made as the lock is taken: after the first access check
    # passed, before the request reads access again. It runs inside the
    # request's transaction (SQLite tests share one connection), so a refused
    # request rolls it back and each case starts from setUp's state. SQLite
    # can't make a request wait for a row lock or see another transaction's
    # commit; test_plan_member_check_postgres.py does that on PostgreSQL.

    def tick_while_waiting(self, change, user, task):
        lock = PlanTask.objects.select_for_update

        def change_then_lock():
            change()
            return lock()

        with patch.object(PlanTask.objects, "select_for_update", side_effect=change_then_lock) as spy:
            response = self.check(user, task, {"completed": True})
        spy.assert_called_once_with()
        return response

    def assert_refused(self, response, task):
        self.assertEqual(response.status_code, 404, response.data)
        self.assertFalse(PlanTaskCompletion.objects.exists())
        self.assertEqual(self.audits(task), [])

    def end_membership(self, user):
        GroupMembership.objects.filter(user=user, group=self.group).update(left_at=timezone.now())

    def test_a_membership_ended_while_waiting_is_refused(self):
        for user, task in (
            (self.student, self.s_indiv),
            (self.student, self.s_shared),  # Will's rule: theirs only while a member.
            (self.mentor, self.m_shared),
            (self.supervisor_member, self.sup_indiv),
        ):
            with self.subTest(user=user.email, task=task.name):
                self.assert_refused(self.tick_while_waiting(lambda: self.end_membership(user), user, task), task)

    def test_a_supervisor_link_removed_while_waiting_is_refused(self):
        def unlink():
            StudentProfile.objects.filter(user=self.other_student).update(supervisor=None)

        self.assert_refused(self.tick_while_waiting(unlink, self.supervisor_profile_only, self.s_shared), self.s_shared)

    def test_admin_access_removed_while_waiting_is_refused(self):
        def revoke():
            AdminScope.objects.filter(user=self.admin).delete()

        self.assert_refused(self.tick_while_waiting(revoke, self.admin, self.m_shared), self.m_shared)

    def test_a_group_deleted_while_waiting_is_refused(self):
        def delete():
            Groups.objects.filter(pk=self.group.pk).update(deleted_at=timezone.now())

        self.assert_refused(self.tick_while_waiting(delete, self.mentor, self.s_shared), self.s_shared)

    def test_a_group_out_of_the_cohort_while_waiting_is_refused(self):
        def move():
            Groups.objects.filter(pk=self.group.pk).update(year=self.group.year - 1)

        self.assert_refused(self.tick_while_waiting(move, self.student, self.s_indiv), self.s_indiv)

    def test_access_unchanged_while_waiting_still_ticks(self):
        response = self.tick_while_waiting(lambda: None, self.student, self.s_shared)
        self.assert_ok(response, True)
        self.assertEqual(len(self.audits(self.s_shared)), 1)

    def test_response_matches_the_list_item(self):
        response = self.check(self.student, self.s_indiv, {"completed": True})
        listed = APIClient()
        listed.force_authenticate(self.student)
        items = listed.get(reverse("plans:group-plan-tasks", kwargs={"group_id": self.group.id})).data["items"]
        self.assertEqual(response.data, next(i for i in items if i["id"] == self.s_indiv.id))
