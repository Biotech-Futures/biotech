"""GP5 roster-aware progress, access control and bounded query counts."""
from datetime import date, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.admin.services.plan_progress import get_plan_progress
from apps.groups.models import GroupMembership, Groups
from apps.plans.models import PlanStage, PlanTask, PlanTaskCompletion
from apps.submissions.models import Deadline
from apps.users.models import AdminScope

URL = "/api/v1/admin/plan-task/progress/"


class PlanProgressTests(APITestCase):
    def setUp(self):
        self.year = timezone.localdate().year
        self.admin = get_user_model().objects.create_user(email="progress.admin@test.com")
        AdminScope.objects.create(user=self.admin)
        self.client.force_authenticate(self.admin)
        self.group = Groups.objects.create(group_name="BTF2", year=self.year)
        self.other = Groups.objects.create(group_name="BTF10", year=self.year)
        self.stage = PlanStage.objects.create(name="Start", description="Meet the group", position=0)
        self.tasks = {
            (role, mode): PlanTask.objects.create(
                stage=self.stage, name=f"{role} {mode}", audience_role=role, completion_mode=mode,
            )
            for role in ("student", "mentor", "supervisor")
            for mode in ("per_person", "per_group")
        }

    def member(self, name, role="student", group=None, **user_fields):
        user = get_user_model().objects.create_user(email=f"{name}@test.com", **user_fields)
        GroupMembership.objects.create(user=user, group=group or self.group, membership_role=role)
        return user

    def tick(self, user=None, role="student", mode="per_person", group=None, completed=True):
        return PlanTaskCompletion.objects.create(
            task=self.tasks[role, mode], group=group or self.group, user=user, completed=completed,
        )

    def progress(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["msg"], "Plan progress retrieved successfully")
        return response.json()["data"]

    def cell(self, data, role="student", mode="per_person", group=None):
        group_id = (group or self.group).pk
        return next(row for row in data["groups"] if row["id"] == group_id)["cells"][str(self.tasks[role, mode].pk)]

    def test_only_scoped_admins_can_read_progress(self):
        for index, fields in enumerate(({}, {"is_staff": True}, {"is_superuser": True})):
            user = get_user_model().objects.create_user(email=f"denied{index}@test.com", **fields)
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(URL).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_response_contract_and_natural_group_order(self):
        task = self.tasks["student", "per_person"]
        task.due_date = date(self.year, 11, 5)
        task.save()
        data = self.progress()
        self.assertEqual(set(data), {"year", "stages", "tasks", "groups"})
        self.assertEqual(data["year"], self.year)
        self.assertEqual([g["name"] for g in data["groups"]], ["BTF2", "BTF10"])
        self.assertEqual(data["stages"], [{
            "id": self.stage.pk, "name": "Start", "description": "Meet the group", "position": 0,
        }])
        self.assertEqual(data["tasks"][0], {
            "id": task.pk, "stage_id": self.stage.pk, "position": 0, "name": task.name,
            "audience_role": "student", "completion_mode": "per_person", "due_date": f"{self.year}-11-05",
        })
        self.assertEqual(set(data["groups"][0]["cells"]), {str(t.pk) for t in self.tasks.values()})

    def test_personal_progress_counts_each_active_audience_separately(self):
        for role in ("student", "mentor", "supervisor"):
            self.tick(self.member(f"done-{role}", role), role)
            self.member(f"pending-{role}", role)
        data = self.progress()
        for role in ("student", "mentor", "supervisor"):
            self.assertEqual(self.cell(data, role), {"completed": 1, "total": 2})

    def test_suspended_and_deactivated_accounts_still_count(self):
        for state in ("suspended", "deactivated"):
            self.tick(self.member(state, account_status=state))
        self.assertEqual(self.cell(self.progress()), {"completed": 2, "total": 2})

    def test_unticked_records_and_missing_records_are_not_completed(self):
        self.tick(self.member("unticked"), completed=False)
        self.member("missing")
        self.assertEqual(self.cell(self.progress()), {"completed": 0, "total": 2})

    def test_leavers_stop_counting_and_returners_recover_their_tick(self):
        user = self.member("returner")
        self.tick(user)
        membership = GroupMembership.objects.get(user=user)
        membership.left_at = timezone.now()
        membership.save()
        self.assertEqual(self.cell(self.progress()), {"completed": 0, "total": 0})
        GroupMembership.objects.create(user=user, group=self.group, membership_role="student")
        self.assertEqual(self.cell(self.progress()), {"completed": 1, "total": 1})

    def test_late_joiners_increase_the_total_without_inheriting_ticks(self):
        self.tick(self.member("original"))
        self.member("late")
        self.assertEqual(self.cell(self.progress()), {"completed": 1, "total": 2})

    def test_role_changes_do_not_count_a_tick_for_the_old_audience(self):
        user = self.member("changed-role")
        self.tick(user)
        GroupMembership.objects.filter(user=user).update(membership_role="mentor")
        data = self.progress()
        self.assertEqual(self.cell(data), {"completed": 0, "total": 0})
        self.assertEqual(self.cell(data, "mentor"), {"completed": 0, "total": 1})

    def test_moving_between_groups_does_not_carry_personal_progress(self):
        user = self.member("moving")
        self.tick(user)
        GroupMembership.objects.filter(user=user).update(left_at=timezone.now())
        GroupMembership.objects.create(user=user, group=self.other, membership_role="student")
        data = self.progress()
        self.assertEqual(self.cell(data), {"completed": 0, "total": 0})
        self.assertEqual(self.cell(data, group=self.other), {"completed": 0, "total": 1})

    def test_replacement_mentor_starts_unticked(self):
        old = self.member("old-mentor", "mentor")
        self.tick(old, "mentor")
        GroupMembership.objects.filter(user=old).update(left_at=timezone.now())
        self.member("new-mentor", "mentor")
        self.assertEqual(self.cell(self.progress(), "mentor"), {"completed": 0, "total": 1})

    def test_shared_progress_ignores_audience_size_and_survives_members_leaving(self):
        self.tick(role="mentor", mode="per_group")
        user = self.member("leaving")
        self.tick(mode="per_group")
        GroupMembership.objects.filter(user=user).update(left_at=timezone.now())
        data = self.progress()
        self.assertEqual(self.cell(data, "mentor", "per_group"), {"completed": 1, "total": 1})
        self.assertEqual(self.cell(data, "student", "per_group"), {"completed": 1, "total": 1})
        self.assertEqual(self.cell(data, "supervisor", "per_group"), {"completed": 0, "total": 1})

    def test_empty_personal_audiences_show_zero_over_zero(self):
        data = self.progress()
        for role in ("student", "mentor", "supervisor"):
            self.assertEqual(self.cell(data, role), {"completed": 0, "total": 0})

    def test_mismatched_record_types_are_ignored(self):
        user = self.member("mismatched")
        self.tick(user, mode="per_group")
        self.tick()  # A shared/null owner on a personal task is not a personal tick.
        self.assertEqual(self.cell(self.progress()), {"completed": 0, "total": 1})
        self.assertEqual(self.cell(self.progress(), mode="per_group"), {"completed": 0, "total": 1})

    def test_old_and_deleted_groups_are_excluded_but_unmentored_groups_are_included(self):
        old = Groups.objects.create(group_name="Old", year=self.year - 1)
        deleted = Groups.objects.create(group_name="Deleted", year=self.year)
        Groups.objects.filter(pk=deleted.pk).update(deleted_at=timezone.now())
        self.tick(self.member("old", group=old), group=old)
        self.tick(self.member("deleted", group=deleted), group=deleted)
        self.assertEqual([g["id"] for g in self.progress()["groups"]], [self.group.pk, self.other.pk])

    def test_deleted_tasks_and_stages_and_empty_stages_are_excluded(self):
        dead = PlanStage.objects.create(name="Deleted stage", deleted_at=timezone.now())
        PlanStage.objects.create(name="Empty stage")
        PlanTask.objects.create(stage=dead, name="Hidden", audience_role="student")
        self.tick(self.member("deleted-task"))
        self.tasks["student", "per_person"].soft_delete()
        data = self.progress()
        self.assertEqual(len(data["stages"]), 1)
        self.assertEqual(len(data["tasks"]), 5)
        self.assertNotIn(str(self.tasks["student", "per_person"].pk), data["groups"][0]["cells"])

    def test_tasks_follow_stage_and_task_positions_with_id_ties(self):
        first = PlanStage.objects.create(name="Earlier", position=0)
        self.stage.position = 10
        self.stage.save()
        later_task = PlanTask.objects.create(stage=first, name="Later", position=1, audience_role="student")
        earlier_task = PlanTask.objects.create(stage=first, name="Earlier", position=0, audience_role="student")
        data = self.progress()
        self.assertEqual([s["id"] for s in data["stages"]], [first.pk, self.stage.pk])
        self.assertEqual([t["id"] for t in data["tasks"][:2]], [earlier_task.pk, later_task.pk])

    def test_moving_tasks_keeps_progress_and_replacements_start_at_zero(self):
        self.tick(self.member("completed"))
        new_stage = PlanStage.objects.create(name="Moved")
        original = self.tasks["student", "per_person"]
        original.stage = new_stage
        original.save()
        self.assertEqual(self.cell(self.progress()), {"completed": 1, "total": 1})
        original.soft_delete()
        replacement = PlanTask.objects.create(stage=new_stage, name=original.name, audience_role="student")
        group = self.progress()["groups"][0]
        self.assertEqual(group["cells"][str(replacement.pk)], {"completed": 0, "total": 1})

    def test_no_tasks_returns_groups_with_empty_cells(self):
        PlanTask.objects.all().delete()
        data = self.progress()
        self.assertEqual(data["stages"], [])
        self.assertEqual(data["tasks"], [])
        self.assertEqual(data["groups"][0]["cells"], {})

    def test_no_groups_returns_tasks_and_empty_groups(self):
        Groups.objects.all().delete()
        self.assertEqual(len(self.progress()["tasks"]), 6)
        self.assertEqual(self.progress()["groups"], [])

    def test_active_deadline_year_drives_the_cohort(self):
        next_year = self.year + 1
        Deadline.objects.create(closes_at=timezone.make_aware(datetime(next_year, 11, 5)), is_active=True)
        group = Groups.objects.create(group_name="Next", year=next_year)
        data = self.progress()
        self.assertEqual(data["year"], next_year)
        self.assertEqual([g["id"] for g in data["groups"]], [group.pk])

    def test_builder_member_completion_and_reporting_work_together(self):
        user = self.member("handover")
        stage = self.client.post("/api/v1/admin/plan-stage/", {"name": "Handover"}, format="json")
        self.assertEqual(stage.status_code, 201, stage.data)
        for mode in ("per_person", "per_group"):
            with self.subTest(mode=mode):
                created = self.client.post("/api/v1/admin/plan-task/", {
                    "name": f"Integrated {mode}", "stage_id": stage.data["data"]["id"],
                    "audience_role": "student", "completion_mode": mode,
                }, format="json")
                self.assertEqual(created.status_code, 201, created.data)
                task_id = created.data["data"]["id"]
                self.client.force_authenticate(user)
                check_url = f"/api/v1/plans/groups/{self.group.pk}/tasks/{task_id}/check/"
                checked = self.client.post(check_url, {"completed": True}, format="json")
                self.assertEqual(checked.status_code, 200, checked.data)
                self.client.force_authenticate(self.admin)
                data = self.progress()
                group = next(g for g in data["groups"] if g["id"] == self.group.pk)
                self.assertEqual(group["cells"][str(task_id)], {"completed": 1, "total": 1})
                self.client.force_authenticate(user)
                self.assertEqual(self.client.post(check_url, {"completed": False}, format="json").status_code, 200)
                self.client.force_authenticate(self.admin)
                group = next(g for g in self.progress()["groups"] if g["id"] == self.group.pk)
                self.assertEqual(group["cells"][str(task_id)], {"completed": 0, "total": 1})

    def test_cohort_is_read_once_and_queries_are_bounded_at_scale(self):
        self.tick(self.member("one"))
        with patch("apps.admin.services.plan_progress.current_cohort", return_value=self.year) as cohort:
            with CaptureQueriesContext(connection) as small:
                get_plan_progress()
            cohort.assert_called_once_with()
        Groups.objects.bulk_create([
            Groups(group_name=f"BTF{100 + index}", year=self.year) for index in range(248)
        ])
        PlanTask.objects.bulk_create([
            PlanTask(stage=self.stage, name=f"Task {index}", audience_role="student") for index in range(54)
        ])
        with patch("apps.admin.services.plan_progress.current_cohort", return_value=self.year):
            with CaptureQueriesContext(connection) as large:
                result = get_plan_progress()["data"]
        self.assertEqual(len(small), len(large))
        self.assertLessEqual(len(large), 5)
        self.assertEqual((len(result["groups"]), len(result["tasks"])), (250, 60))
        self.assertEqual(sum(len(g["cells"]) for g in result["groups"]), 15000)
        self.assertLess(len(self.client.get(URL).content), 2 * 1024 * 1024)
