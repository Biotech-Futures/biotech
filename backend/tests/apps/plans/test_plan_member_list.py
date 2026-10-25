"""GP3 member list: GET /api/v1/plans/groups/<group_id>/tasks/.

Fixtures are arranged to catch the easy mistakes: stages are created in the
reverse of their plan order, task positions disagree with creation order, and
another student's tick and another group's shared tick exist that must never
show. Tick/untick persistence and auditing belong to the completion endpoint.
"""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.groups.models import GroupMembership, Groups
from apps.plans.models import PlanStage, PlanTask, PlanTaskCompletion
from apps.users.models import AdminScope, StudentProfile, SupervisorProfile

ITEM_FIELDS = {
    "id", "stage_id", "position", "name", "description", "resource_url", "resource_label",
    "due_date", "audience_role", "completion_mode", "completed", "can_toggle",
}


class GroupPlanListTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.year = timezone.localdate().year
        self.group = Groups.objects.create(group_name="BTF1", year=self.year)
        self.other_group = Groups.objects.create(group_name="BTF2", year=self.year)

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
        self.admin = user("admin@test.com")
        AdminScope.objects.create(user=self.admin)
        self.outsider = user("outsider@test.com", "student", group=self.other_group)
        self.link(self.student, self.supervisor_member)
        self.link(self.other_student, self.supervisor_profile_only)

        # Created later-first, so ordering by id instead of position would show.
        later = PlanStage.objects.create(name="Developing", position=1)
        early = PlanStage.objects.create(name="Getting started", description="Start here", position=0)
        old_stage = PlanStage.objects.create(name="Retired", position=2, deleted_at=timezone.now())

        def task(stage, name, audience, mode, position, **extra):
            return PlanTask.objects.create(
                stage=stage, name=name, audience_role=audience, completion_mode=mode, position=position, **extra,
            )

        self.s_indiv = task(early, "s-indiv", "student", "per_person", 1,
                            resource_url="https://example.com/guide", resource_label="Guide",
                            due_date=timezone.localdate())
        self.s_shared = task(early, "s-shared", "student", "per_group", 0)
        self.m_indiv = task(later, "m-indiv", "mentor", "per_person", 0)
        self.m_shared = task(later, "m-shared", "mentor", "per_group", 1)
        self.sup_indiv = task(later, "sup-indiv", "supervisor", "per_person", 2)
        self.sup_shared = task(later, "sup-shared", "supervisor", "per_group", 3)
        task(early, "deleted-task", "student", "per_person", 2, deleted_at=timezone.now())
        task(old_stage, "in-deleted-stage", "student", "per_person", 0)

        done = dict(group=self.group, completed=True)
        PlanTaskCompletion.objects.create(task=self.s_indiv, user=self.other_student, **done)  # not the student's
        PlanTaskCompletion.objects.create(task=self.s_shared, user=None, **done)
        PlanTaskCompletion.objects.create(task=self.m_indiv, user=self.mentor, **done)
        PlanTaskCompletion.objects.create(task=self.sup_shared, user=None, group=self.group, completed=False)
        PlanTaskCompletion.objects.create(task=self.m_shared, user=None, group=self.other_group, completed=True)

    def link(self, student, supervisor):
        profile, _ = SupervisorProfile.objects.get_or_create(user=supervisor, defaults={"school_name": "S"})
        StudentProfile.objects.create(
            user=student, pg_first_name="P", pg_last_name="G", school_name="S", year_lvl="10", supervisor=profile,
        )

    def get(self, user, group=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client.get(reverse("plans:group-plan-tasks", kwargs={"group_id": (group or self.group).id}))

    def items(self, user):
        response = self.get(user)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def view(self, user):
        """``[(name, completed, can_toggle), ...]`` in response order."""
        return [(i["name"], i["completed"], i["can_toggle"]) for i in self.items(user)["items"]]

    # -- What each viewer gets ------------------------------------------------

    def test_student(self):
        self.assertEqual(self.view(self.student), [
            ("s-shared", True, True),  # Will's rule: students tick student shared tasks.
            ("s-indiv", False, True),  # Their own record: none yet, so not complete.
        ])

    def test_another_students_tick_is_their_own(self):
        self.assertEqual(dict((n, c) for n, c, _ in self.view(self.other_student))["s-indiv"], True)

    def test_mentor(self):
        self.assertEqual(self.view(self.mentor), [
            ("s-shared", True, True),
            ("m-indiv", True, True),
            ("m-shared", False, True),   # Another group's tick does not count here.
            ("sup-shared", False, True),
        ])

    def test_supervisor_member(self):
        self.assertEqual(self.view(self.supervisor_member), [
            ("s-shared", True, True),
            ("m-shared", False, True),
            ("sup-indiv", False, True),
            ("sup-shared", False, True),
        ])

    def test_supervisor_linked_only_through_a_student_profile(self):
        # Shared tasks only: no membership, so no supervisor individual task.
        self.assertEqual(self.view(self.supervisor_profile_only), [
            ("s-shared", True, True),
            ("m-shared", False, True),
            ("sup-shared", False, True),
        ])

    def test_admin_sees_everything_but_no_ones_individual_ticks(self):
        self.assertEqual(self.view(self.admin), [
            ("s-shared", True, True),
            ("s-indiv", None, False),
            ("m-indiv", None, False),
            ("m-shared", False, True),
            ("sup-indiv", None, False),
            ("sup-shared", False, True),
        ])

    def test_students_never_see_mentor_or_supervisor_shared_tasks(self):
        names = {name for name, _, _ in self.view(self.student)}
        self.assertNotIn("m-shared", names)
        self.assertNotIn("sup-shared", names)

    # -- Shape, stages and ordering -------------------------------------------

    def test_response_shape_and_item_fields(self):
        data = self.items(self.student)
        self.assertEqual(set(data), {"year", "stages", "items"})
        self.assertEqual(data["year"], self.year)
        item = next(i for i in data["items"] if i["name"] == "s-indiv")
        self.assertEqual(set(item), ITEM_FIELDS)
        self.assertEqual(item["stage_id"], self.s_indiv.stage_id)
        self.assertEqual(item["resource_url"], "https://example.com/guide")
        self.assertEqual(item["resource_label"], "Guide")
        self.assertEqual(item["due_date"], timezone.localdate().isoformat())
        self.assertEqual((item["audience_role"], item["completion_mode"]), ("student", "per_person"))

    def test_stages_are_only_those_with_visible_tasks_in_plan_order(self):
        self.assertEqual(
            self.items(self.admin)["stages"],
            [
                {"id": self.s_shared.stage_id, "name": "Getting started", "description": "Start here", "position": 0},
                {"id": self.m_indiv.stage_id, "name": "Developing", "description": "", "position": 1},
            ],
        )
        # A student sees nothing in "Developing", so it is left out.
        self.assertEqual([s["name"] for s in self.items(self.student)["stages"]], ["Getting started"])

    def test_deleted_tasks_and_stages_are_excluded(self):
        names = {name for name, _, _ in self.view(self.admin)}
        self.assertNotIn("deleted-task", names)
        self.assertNotIn("in-deleted-stage", names)
        self.assertNotIn("Retired", [s["name"] for s in self.items(self.admin)["stages"]])

    # -- Access and the current cohort ----------------------------------------

    def test_non_members_and_unknown_or_deleted_groups_get_404(self):
        self.assertEqual(self.get(self.outsider).status_code, 404)
        missing = Groups(pk=999999)
        self.assertEqual(self.get(self.student, group=missing).status_code, 404)
        Groups.objects.filter(pk=self.group.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.get(self.student).status_code, 404)

    def test_anonymous_requests_are_rejected(self):
        self.assertIn(self.get(None).status_code, (401, 403))

    def test_previous_year_group_returns_an_empty_plan(self):
        Groups.objects.filter(pk=self.group.pk).update(year=self.year - 1)
        for user in (self.student, self.admin):
            with self.subTest(user=user.email):
                self.assertEqual(self.items(user), {"year": self.year, "stages": [], "items": []})
        # Access is still checked first: an outsider gets 404, not an empty plan.
        self.assertEqual(self.get(self.outsider).status_code, 404)

    # -- Fixed query count ----------------------------------------------------

    def test_query_count_does_not_grow_with_tasks_or_completions(self):
        def count(user):
            with CaptureQueriesContext(connection) as queries:
                self.assertEqual(self.get(user).status_code, 200)
            return len(queries)

        before = {user.email: count(user) for user in (self.student, self.mentor, self.admin)}
        stage = PlanStage.objects.create(name="Extra", position=5)
        for n in range(8):
            for audience, mode in (("student", "per_person"), ("mentor", "per_group")):
                extra = PlanTask.objects.create(
                    stage=stage, name=f"extra-{audience}-{n}", audience_role=audience, completion_mode=mode,
                )
                owner = self.student if mode == "per_person" else None
                PlanTaskCompletion.objects.create(task=extra, group=self.group, user=owner, completed=True)
        after = {user.email: count(user) for user in (self.student, self.mentor, self.admin)}
        self.assertEqual(after, before)
