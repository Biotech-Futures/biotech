"""GP3 plan permissions: who sees a group's plan, which tasks, and what they may tick.

One task exists for every audience/mode pair, named "<audience>/<mode>". Each
viewer's visible and tickable sets are checked against the rules in
``apps.plans.permissions``, including Will's confirmed answer that students may
tick student-audience shared tasks. Persistence and audit of ticks belong to
the completion-endpoint tests.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.groups.models import GroupMembership, Groups
from apps.plans.models import PlanStage, PlanTask
from apps.plans.permissions import (
    can_tick_plan_task,
    can_view_group_plan,
    viewer_facts,
    visible_plan_tasks,
)
from apps.users.models import AdminScope, StudentProfile, SupervisorProfile

AUDIENCES = ("student", "mentor", "supervisor")
MODES = ("per_person", "per_group")
ALL = {f"{audience}/{mode}" for audience in AUDIENCES for mode in MODES}
SHARED = {f"{audience}/per_group" for audience in AUDIENCES}


class PlanPermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.group = Groups.objects.create(group_name="BTF1", year=timezone.localdate().year)
        other_group = Groups.objects.create(group_name="BTF2", year=timezone.localdate().year)

        def member(email, role, group=self.group):
            user = User.objects.create_user(email=email, password="pw")
            if role:
                GroupMembership.objects.create(user=user, group=group, membership_role=role)
            return user

        self.student = member("student@test.com", "student")
        self.other_student = member("student2@test.com", "student")
        self.mentor = member("mentor@test.com", "mentor")
        self.admin = member("admin@test.com", None)
        AdminScope.objects.create(user=self.admin)
        self.non_member = member("outsider@test.com", "student", group=other_group)

        # Supervisors: linked to a student in the group through StudentProfile.
        self.supervisor_member = member("sup.member@test.com", "supervisor")
        self.supervisor_profile_only = member("sup.profile@test.com", None)
        # A supervisor member of the group with no supervisee in it.
        self.supervisor_unlinked = member("sup.unlinked@test.com", "supervisor")
        self.link_student(self.student, self.supervisor_member)
        self.link_student(self.other_student, self.supervisor_profile_only)
        SupervisorProfile.objects.create(user=self.supervisor_unlinked, school_name="School")

        stage = PlanStage.objects.create(name="Getting started")
        self.tasks = {
            f"{audience}/{mode}": PlanTask.objects.create(
                stage=stage, name=f"{audience}/{mode}", audience_role=audience, completion_mode=mode,
            )
            for audience in AUDIENCES
            for mode in MODES
        }

    def link_student(self, student, supervisor):
        profile, _ = SupervisorProfile.objects.get_or_create(user=supervisor, defaults={"school_name": "School"})
        StudentProfile.objects.create(
            user=student, pg_first_name="P", pg_last_name="G", school_name="School", year_lvl="10",
            supervisor=profile,
        )

    def facts(self, user):
        return viewer_facts(user, self.group)

    def visible(self, user):
        return set(visible_plan_tasks(self.facts(user)).values_list("name", flat=True))

    def tickable(self, user):
        facts = self.facts(user)
        return {
            task.name for task in visible_plan_tasks(facts) if can_tick_plan_task(task, facts)
        }

    # -- Viewer facts and plan access --------------------------------------

    def test_viewer_facts(self):
        expected = {
            "student": (self.student, False, "student", False),
            "mentor": (self.mentor, False, "mentor", True),
            "supervisor member": (self.supervisor_member, False, "supervisor", True),
            "supervisor via profile only": (self.supervisor_profile_only, False, None, True),
            "unlinked supervisor member": (self.supervisor_unlinked, False, "supervisor", False),
            "admin": (self.admin, True, None, True),
            "non-member": (self.non_member, False, None, False),
        }
        for label, (user, admin, role, tick_right) in expected.items():
            with self.subTest(label):
                facts = self.facts(user)
                self.assertEqual(
                    (facts.is_admin, facts.membership_role, facts.holds_tick_right), (admin, role, tick_right)
                )

    def test_who_may_open_the_plan(self):
        for user in (
            self.student, self.mentor, self.supervisor_member, self.supervisor_profile_only,
            self.supervisor_unlinked, self.admin,
        ):
            with self.subTest(user=user.email):
                self.assertTrue(can_view_group_plan(self.facts(user)))
        self.assertFalse(can_view_group_plan(self.facts(self.non_member)))

    def test_a_member_who_has_left_is_a_non_member(self):
        GroupMembership.objects.filter(user=self.student, group=self.group).update(left_at=timezone.now())
        facts = self.facts(self.student)
        self.assertIsNone(facts.membership_role)
        self.assertFalse(can_view_group_plan(facts))
        self.assertEqual(self.visible(self.student), set())

    # -- Visibility and tick rights per viewer ------------------------------

    def test_visible_and_tickable_tasks_per_viewer(self):
        cases = {
            # Own audience only; may tick the student shared task (Will's answer).
            "student": (self.student, {"student/per_person", "student/per_group"},
                        {"student/per_person", "student/per_group"}),
            "mentor": (self.mentor, {"mentor/per_person"} | SHARED, {"mentor/per_person"} | SHARED),
            "supervisor member": (self.supervisor_member, {"supervisor/per_person"} | SHARED,
                                  {"supervisor/per_person"} | SHARED),
            # Shared tasks only: no membership, so no supervisor individual tasks.
            "supervisor via profile only": (self.supervisor_profile_only, SHARED, SHARED),
            # A supervisor member without a supervisee here holds no shared-tick
            # right: they see their audience's tasks but tick only their own.
            "unlinked supervisor member": (self.supervisor_unlinked,
                                           {"supervisor/per_person", "supervisor/per_group"},
                                           {"supervisor/per_person"}),
            # Everything visible; shared tasks only, never someone's own record.
            "admin": (self.admin, ALL, SHARED),
        }
        for label, (user, visible, tickable) in cases.items():
            with self.subTest(label):
                self.assertEqual(self.visible(user), visible)
                self.assertEqual(self.tickable(user), tickable)

    def test_students_cannot_reach_mentor_or_supervisor_shared_tasks(self):
        # Ticking a student shared task must not widen what a student sees, so
        # these stay out of the visible set and their requests 404.
        visible = self.visible(self.student)
        self.assertNotIn("mentor/per_group", visible)
        self.assertNotIn("supervisor/per_group", visible)

    def test_soft_deleted_tasks_are_not_visible_even_to_admins(self):
        self.tasks["student/per_group"].soft_delete()
        self.assertNotIn("student/per_group", self.visible(self.admin))
        self.assertNotIn("student/per_group", self.visible(self.student))

    # -- Individual tasks belong to their own person -------------------------

    def test_nobody_ticks_an_individual_task_outside_their_own_audience(self):
        student_task = self.tasks["student/per_person"]
        for user in (self.admin, self.mentor, self.supervisor_member, self.supervisor_profile_only):
            with self.subTest(user=user.email):
                self.assertFalse(can_tick_plan_task(student_task, self.facts(user)))

    def test_an_admin_who_is_a_group_member_ticks_only_their_own_audience(self):
        GroupMembership.objects.create(user=self.admin, group=self.group, membership_role="mentor")
        facts = self.facts(self.admin)
        self.assertTrue(can_tick_plan_task(self.tasks["mentor/per_person"], facts))
        self.assertFalse(can_tick_plan_task(self.tasks["student/per_person"], facts))
        self.assertTrue(can_tick_plan_task(self.tasks["supervisor/per_group"], facts))

    # -- can_tick_plan_task makes no queries ---------------------------------

    def test_can_tick_plan_task_makes_no_queries(self):
        tasks = list(PlanTask.objects.all())
        all_facts = [
            self.facts(user)
            for user in (
                self.student, self.mentor, self.supervisor_member, self.supervisor_profile_only,
                self.supervisor_unlinked, self.admin, self.non_member,
            )
        ]
        with self.assertNumQueries(0):
            for facts in all_facts:
                for task in tasks:
                    can_tick_plan_task(task, facts)
