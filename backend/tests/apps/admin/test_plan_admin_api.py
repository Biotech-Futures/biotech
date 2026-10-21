"""GP2 admin plan-builder API: stages, tasks, validation, locks and audit.

These exercise the services through the endpoints in apps/admin/views.py.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.audit.models import AuditLog
from apps.groups.models import Groups
from apps.plans.models import PlanStage, PlanTask, PlanTaskCompletion
from apps.submissions.services import current_cohort
from apps.users.models import AdminScope

STAGE_LIST_URL = "/api/v1/admin/plan-stage/"
TASK_LIST_URL = "/api/v1/admin/plan-task/"


def stage_url(stage_id):
    return f"{STAGE_LIST_URL}{stage_id}/"


def task_url(task_id):
    return f"{TASK_LIST_URL}{task_id}/"


class PlanAdminApiTestCase(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(email="plan.admin@example.com")
        AdminScope.objects.create(user=self.admin)
        self.client.force_authenticate(self.admin)

    def add_stage(self, name="Getting started", **overrides):
        payload = {"name": name}
        payload.update(overrides)
        return self.client.post(STAGE_LIST_URL, payload, format="json")

    def add_task(self, stage_id, name="Read the guide", **overrides):
        payload = {"name": name, "stage_id": stage_id, "audience_role": "student"}
        payload.update(overrides)
        return self.client.post(TASK_LIST_URL, payload, format="json")

    def make_stage(self, name="Stage", **overrides):
        stage = PlanStage.objects.create(name=name)
        for field, value in overrides.items():
            setattr(stage, field, value)
        if overrides:
            stage.save()
        return stage

    def make_task(self, stage, name="Task", **overrides):
        task = PlanTask.objects.create(
            stage=stage, name=name, audience_role="student"
        )
        for field, value in overrides.items():
            setattr(task, field, value)
        if overrides:
            task.save()
        return task

    def group_in(self, name="Group A", year=None, **overrides):
        group = Groups.objects.create(group_name=name, year=year or current_cohort())
        for field, value in overrides.items():
            setattr(group, field, value)
        if overrides:
            group.save()
        return group

    def assertRefused(self, response, code, msg_part):
        self.assertEqual(response.status_code, code, response.content)
        body = response.json()
        self.assertIsNone(body["data"])
        self.assertIn(msg_part, body["msg"])


class PlanPermissionTests(PlanAdminApiTestCase):
    def test_non_admins_are_refused_on_every_endpoint(self):
        stage = self.make_stage()
        task = self.make_task(stage)
        callers = {
            "anonymous": None,
            "student": get_user_model().objects.create_user(email="student@example.com"),
            "staff": get_user_model().objects.create_user(email="staff@example.com", is_staff=True),
        }
        for who, user in callers.items():
            self.client.force_authenticate(user)
            calls = (
                ("get", STAGE_LIST_URL, None),
                ("post", STAGE_LIST_URL, {"name": "S"}),
                ("patch", stage_url(stage.pk), {"name": "S"}),
                ("delete", stage_url(stage.pk), None),
                ("get", TASK_LIST_URL, None),
                ("post", TASK_LIST_URL, {"name": "T", "stage_id": stage.pk, "audience_role": "student"}),
                ("get", task_url(task.pk), None),
                ("patch", task_url(task.pk), {"name": "T"}),
                ("delete", task_url(task.pk), None),
            )
            for method, url, data in calls:
                with self.subTest(who=who, method=method, url=url):
                    response = getattr(self.client, method)(url, data, format="json")
                    self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PlanStageApiTests(PlanAdminApiTestCase):
    def test_list_is_in_plan_order_and_hides_deleted_stages(self):
        self.add_stage("Third", position=2)
        self.add_stage("First", position=0)
        self.add_stage("Second", position=1)
        deleted = self.make_stage("Gone", deleted_at=timezone.now())
        response = self.client.get(STAGE_LIST_URL)
        self.assertEqual(response.status_code, 200)
        items = response.json()["data"]["items"]
        self.assertEqual([item["name"] for item in items], ["First", "Second", "Third"])
        self.assertNotIn(deleted.pk, [item["id"] for item in items])
        # Empty stages are listed: none of these have tasks.

    def test_create_returns_201_with_defaults_and_trims_the_name(self):
        response = self.add_stage("  Getting started  ")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(
            data, {"id": data["id"], "name": "Getting started", "description": "", "position": 0}
        )
        log = AuditLog.objects.get(entity_type="plan_stage", action="create")
        self.assertEqual(log.actor_user, self.admin)
        self.assertEqual(log.entity_id, data["id"])
        self.assertEqual(log.after_state["name"], "Getting started")

    def test_create_validation_failures_return_400(self):
        cases = (
            ({}, "name is required"),
            ({"name": "   "}, "name is required"),
            ({"name": 7}, "name must be text"),
            ({"name": "x" * 256}, "255 characters or fewer"),
            ({"name": "S", "description": 5}, "description must be text"),
            ({"name": "S", "position": -1}, "non-negative"),
            ({"name": "S", "position": "1"}, "non-negative"),
            ({"name": "S", "position": True}, "non-negative"),
            ({"name": "S", "extra": 1}, "Unknown field: extra"),
        )
        for payload, msg_part in cases:
            with self.subTest(payload=payload):
                self.assertRefused(
                    self.client.post(STAGE_LIST_URL, payload, format="json"), 400, msg_part
                )

    def test_non_object_body_is_rejected(self):
        response = self.client.post(STAGE_LIST_URL, ["not-an-object"], format="json")
        self.assertRefused(response, 400, "Request body must be an object")

    def test_patch_edits_fields_and_audits_before_after(self):
        stage = self.make_stage("Old", description="intro", position=3)
        response = self.client.patch(
            stage_url(stage.pk), {"name": "New", "position": 1}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual((data["name"], data["description"], data["position"]), ("New", "intro", 1))
        log = AuditLog.objects.get(entity_type="plan_stage", action="update")
        self.assertEqual(log.before_state["name"], "Old")
        self.assertEqual(log.after_state["name"], "New")

    def test_patch_with_no_changes_returns_200_without_an_audit_entry(self):
        stage = self.make_stage("Same", description="x", position=2)
        response = self.client.patch(
            stage_url(stage.pk), {"name": "Same", "position": 2}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["msg"], "Stage unchanged")
        self.assertFalse(AuditLog.objects.filter(entity_type="plan_stage").exists())

    def test_patch_validation_and_not_found(self):
        stage = self.make_stage()
        self.assertRefused(
            self.client.patch(stage_url(stage.pk), {"name": " "}, format="json"),
            400, "name is required")
        self.assertRefused(
            self.client.patch(stage_url(stage.pk), {"nope": 1}, format="json"),
            400, "Unknown field")
        self.assertRefused(
            self.client.patch(stage_url(stage.pk + 999), {"name": "X"}, format="json"),
            404, "Stage not found")
        stage.deleted_at = timezone.now()
        stage.save(update_fields=["deleted_at"])
        self.assertRefused(
            self.client.patch(stage_url(stage.pk), {"name": "X"}, format="json"),
            404, "Stage not found")

    def test_delete_removes_an_empty_stage_and_returns_204(self):
        stage = self.make_stage()
        response = self.client.delete(stage_url(stage.pk))
        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(response.content)
        self.assertIsNotNone(PlanStage.objects.get(pk=stage.pk).deleted_at)
        self.assertFalse(PlanStage.objects.active().exists())
        log = AuditLog.objects.get(entity_type="plan_stage", action="delete")
        self.assertEqual(log.before_state["name"], "Stage")

    def test_delete_refuses_a_stage_with_live_tasks(self):
        stage = self.make_stage()
        self.make_task(stage)
        self.assertRefused(
            self.client.delete(stage_url(stage.pk)), 400, "still contains tasks"
        )
        self.assertIsNone(PlanStage.objects.get(pk=stage.pk).deleted_at)

    def test_delete_ignores_soft_deleted_tasks_and_404s_twice(self):
        stage = self.make_stage()
        task = self.make_task(stage)
        task.soft_delete()
        response = self.client.delete(stage_url(stage.pk))
        self.assertEqual(response.status_code, 204)
        self.assertRefused(
            self.client.delete(stage_url(stage.pk)), 404, "Stage not found"
        )


class PlanTaskApiTests(PlanAdminApiTestCase):
    def test_create_returns_the_full_admin_item_with_defaults(self):
        stage = self.make_stage()
        response = self.add_task(
            stage.pk, "  Read the guide  ",
            description="Do the reading.", position=2,
            completion_mode="per_group",
        )
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(data["name"], "Read the guide")
        self.assertEqual(data["stage_id"], stage.pk)
        self.assertEqual(data["description"], "Do the reading.")
        self.assertEqual(data["position"], 2)
        self.assertEqual(data["completion_mode"], "per_group")
        self.assertEqual(data["due_date"], None)
        self.assertEqual(data["resource_url"], "")
        self.assertEqual(data["resource_label"], "")
        self.assertFalse(data["has_completions"])
        self.assertEqual(data["created_by"], {"id": self.admin.pk, "name": None})
        self.assertEqual(
            sorted(data), sorted([
                "id", "stage_id", "position", "name", "description", "resource_url",
                "resource_label", "due_date", "audience_role", "completion_mode",
                "has_completions", "created_by", "created_at", "updated_at",
            ])
        )
        log = AuditLog.objects.get(entity_type="plan_task", action="create")
        self.assertEqual(log.after_state["audience_role"], "student")
        self.assertEqual(log.after_state["completion_mode"], "per_group")

    def test_create_validation_failures(self):
        stage = self.make_stage()
        deleted = self.make_stage("Deleted")
        deleted.deleted_at = timezone.now()
        deleted.save(update_fields=["deleted_at"])
        cases = (
            ({"stage_id": stage.pk, "audience_role": "student"}, "name is required"),
            ({"name": "T", "stage_id": stage.pk}, "audience_role is required"),
            ({"name": "T", "stage_id": stage.pk, "audience_role": "everyone"},
             "audience_role must be student, mentor or supervisor"),
            ({"name": "T", "audience_role": "student"}, "stage_id is required"),
            ({"name": "T", "stage_id": stage.pk, "audience_role": "student",
              "completion_mode": "sometimes"}, "completion_mode must be per_person or per_group"),
            ({"name": "T", "stage_id": stage.pk, "audience_role": "student",
              "due_date": "2026-01-01T00:00:00Z"}, "YYYY-MM-DD"),
            ({"name": "T", "stage_id": stage.pk, "audience_role": "student",
              "due_date": "not-a-date"}, "YYYY-MM-DD"),
            ({"name": "T", "stage_id": stage.pk, "audience_role": "student",
              "due_date": "2026-02-30"}, "real calendar date"),
            ({"name": "T", "stage_id": stage.pk, "audience_role": "student",
              "resource_url": "https://example.com/"}, "both a link and a label"),
            ({"name": "T", "stage_id": stage.pk, "audience_role": "student",
              "resource_label": "Guide"}, "both a link and a label"),
            ({"name": "T", "stage_id": stage.pk, "audience_role": "student",
              "resource_url": "javascript:alert(1)", "resource_label": "Guide"},
             "valid http:// or https://"),
            ({"name": "T", "stage_id": stage.pk + 999, "audience_role": "student"},
             "Select a stage that has not been deleted"),
            ({"name": "T", "stage_id": deleted.pk, "audience_role": "student"},
             "Select a stage that has not been deleted"),
            ({"name": "T", "stage_id": stage.pk, "audience_role": "student",
              "position": -1}, "non-negative"),
            ({"name": "T", "stage_id": stage.pk, "audience_role": "student",
              "extra": 1}, "Unknown field"),
        )
        for payload, msg_part in cases:
            with self.subTest(msg_part=msg_part):
                self.assertRefused(self.client.post(TASK_LIST_URL, payload, format="json"), 400, msg_part)
        self.assertEqual(PlanTask.objects.count(), 0)

    def test_create_accepts_a_valid_resource_pair_and_due_date(self):
        stage = self.make_stage()
        response = self.add_task(
            stage.pk,
            resource_url="https://example.org/guide",
            resource_label="Read this",
            due_date="2026-07-15",
        )
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(data["due_date"], "2026-07-15")
        self.assertEqual(data["resource_label"], "Read this")

    def test_list_paginates_in_plan_order(self):
        early = self.make_stage("Early", position=0)
        late = self.make_stage("Late", position=1)
        self.make_task(late, "Z task", position=0)
        self.make_task(early, "A task", position=0)
        self.make_task(early, "B task", position=1)
        response = self.client.get(TASK_LIST_URL, {"page": 1, "limit": 2})
        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertEqual(
            (body["total"], body["page"], body["limit"], body["has_more"]), (3, 1, 2, True)
        )
        self.assertEqual([item["name"] for item in body["items"]], ["A task", "B task"])
        response = self.client.get(TASK_LIST_URL, {"page": 2, "limit": 2})
        body = response.json()["data"]
        self.assertEqual((body["has_more"], [i["name"] for i in body["items"]]), (False, ["Z task"]))

    def test_list_sorting(self):
        stage = self.make_stage()
        self.make_task(stage, "Bravo", position=1, due_date=None)
        self.make_task(stage, "Alpha", position=0, due_date=date(2026, 1, 1))
        self.make_task(stage, "Charlie", position=2, due_date=date(2026, 3, 1))
        cases = (
            ({"sortBy": "name"}, ["Alpha", "Bravo", "Charlie"]),
            ({"sortBy": "name", "sortOrder": "desc"}, ["Charlie", "Bravo", "Alpha"]),
            ({"sortBy": "due"}, ["Alpha", "Charlie", "Bravo"]),  # undated last
            ({"sortBy": "due", "sortOrder": "desc"}, ["Charlie", "Alpha", "Bravo"]),
        )
        for params, expected in cases:
            with self.subTest(params=params):
                response = self.client.get(TASK_LIST_URL, params)
                self.assertEqual(
                    [item["name"] for item in response.json()["data"]["items"]], expected
                )

    def test_list_rejects_invalid_query_values(self):
        cases = (
            ({"page": "0"}, "positive"),
            ({"page": "abc"}, "whole numbers"),
            ({"limit": "101"}, "100 or fewer"),
            ({"limit": "0"}, "positive"),
            ({"sortBy": "dueDate"}, "sortBy must be one of"),
            ({"sortOrder": "sideways"}, "sortOrder must be asc or desc"),
        )
        for params, msg_part in cases:
            with self.subTest(params=params):
                self.assertRefused(self.client.get(TASK_LIST_URL, params), 400, msg_part)

    def test_detail_returns_item_and_hides_deleted_tasks(self):
        stage = self.make_stage()
        task = self.make_task(stage)
        response = self.client.get(task_url(task.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["id"], task.pk)
        self.assertRefused(
            self.client.get(task_url(task.pk + 999)), 404, "Task not found"
        )
        task.soft_delete()
        self.assertRefused(self.client.get(task_url(task.pk)), 404, "Task not found")

    def test_patch_edits_fields_and_moves_a_task_keeping_its_id(self):
        stage = self.make_stage("First", position=0)
        other = self.make_stage("Second", position=1)
        task = self.make_task(stage, "Old name", position=0)
        response = self.client.patch(
            task_url(task.pk),
            {"name": "New name", "stage_id": other.pk, "due_date": "2026-08-01"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(data["id"], task.pk)
        self.assertEqual(data["name"], "New name")
        self.assertEqual(data["stage_id"], other.pk)
        self.assertEqual(data["due_date"], "2026-08-01")
        log = AuditLog.objects.get(entity_type="plan_task", action="update")
        self.assertEqual(log.before_state["name"], "Old name")
        self.assertEqual(log.after_state["name"], "New name")
        self.assertIn("audience_role", log.before_state)
        self.assertIn("completion_mode", log.after_state)

    def test_patch_with_no_changes_returns_200_without_an_audit_entry(self):
        stage = self.make_stage()
        task = self.make_task(stage, "Same")
        response = self.client.patch(task_url(task.pk), {"name": "Same"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["msg"], "Task unchanged")
        self.assertFalse(AuditLog.objects.filter(entity_type="plan_task").exists())

    def test_patch_clears_a_due_date_with_null_and_rejects_datetime_strings(self):
        stage = self.make_stage()
        task = self.make_task(stage, due_date=date(2026, 5, 5))
        self.assertRefused(
            self.client.patch(
                task_url(task.pk), {"due_date": "2026-05-05T00:00:00Z"}, format="json"
            ),
            400, "YYYY-MM-DD")
        response = self.client.patch(task_url(task.pk), {"due_date": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"]["due_date"])

    def test_patch_404s_for_missing_and_deleted_tasks(self):
        stage = self.make_stage()
        task = self.make_task(stage)
        self.assertRefused(
            self.client.patch(task_url(task.pk + 999), {"name": "X"}, format="json"),
            404, "Task not found")
        task.soft_delete()
        self.assertRefused(
            self.client.patch(task_url(task.pk), {"name": "X"}, format="json"),
            404, "Task not found")

    def test_completion_record_locks_audience_and_mode_but_nothing_else(self):
        stage = self.make_stage()
        task = self.make_task(stage, "Locked")
        group = self.group_in()
        PlanTaskCompletion.objects.create(task=task, group=group, user=None, completed=False)

        self.assertRefused(
            self.client.patch(task_url(task.pk), {"audience_role": "mentor"}, format="json"),
            400, "Audience cannot be changed")
        self.assertRefused(
            self.client.patch(task_url(task.pk), {"completion_mode": "per_group"}, format="json"),
            400, "Completion mode cannot be changed")
        # Everything else stays editable, and the lock flag is reported.
        response = self.client.patch(task_url(task.pk), {"name": "Still editable"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["data"]["has_completions"])
        self.assertEqual(response.json()["data"]["audience_role"], "student")
        self.assertEqual(response.json()["data"]["completion_mode"], "per_person")

    def test_previous_year_and_soft_deleted_group_records_do_not_lock(self):
        stage = self.make_stage()
        old_group = self.group_in(year=current_cohort() - 1)
        task = self.make_task(stage)
        PlanTaskCompletion.objects.create(task=task, group=old_group, user=None, completed=True)
        response = self.client.patch(task_url(task.pk), {"audience_role": "mentor"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["data"]["has_completions"])

        gone_group = self.group_in("Deleted group")
        gone_group.deleted_at = timezone.now()
        gone_group.save(update_fields=["deleted_at"])
        task2 = self.make_task(stage, "Unlocked task")
        PlanTaskCompletion.objects.create(task=task2, group=gone_group, user=None, completed=True)
        response = self.client.patch(task_url(task2.pk), {"completion_mode": "per_group"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["data"]["has_completions"])

    def test_list_and_detail_report_has_completions_from_current_year_groups(self):
        stage = self.make_stage()
        task = self.make_task(stage)
        group = self.group_in()
        self.assertFalse(self.client.get(task_url(task.pk)).json()["data"]["has_completions"])
        self.assertFalse(
            self.client.get(TASK_LIST_URL).json()["data"]["items"][0]["has_completions"]
        )
        PlanTaskCompletion.objects.create(task=task, group=group, user=None, completed=True)
        self.assertTrue(self.client.get(task_url(task.pk)).json()["data"]["has_completions"])
        self.assertTrue(
            self.client.get(TASK_LIST_URL).json()["data"]["items"][0]["has_completions"]
        )

    def test_delete_soft_deletes_and_retains_completion_records(self):
        stage = self.make_stage()
        task = self.make_task(stage)
        group = self.group_in()
        completion = PlanTaskCompletion.objects.create(
            task=task, group=group, user=None, completed=True
        )
        response = self.client.delete(task_url(task.pk))
        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(response.content)
        self.assertIsNotNone(PlanTask.objects.get(pk=task.pk).deleted_at)
        self.assertTrue(PlanTaskCompletion.objects.filter(pk=completion.pk).exists())
        log = AuditLog.objects.get(entity_type="plan_task", action="delete")
        self.assertEqual(log.before_state["id"], task.pk)
        self.assertRefused(self.client.delete(task_url(task.pk)), 404, "Task not found")
