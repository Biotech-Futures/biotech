from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.admin.services.role_task import (
    count_role_recipients,
    create_admin_role_task,
    delete_admin_role_task,
    get_admin_role_task_by_id,
    list_admin_role_tasks,
    update_admin_role_task,
)
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.tasks.models import CreatorRole, RoleTask, RoleTaskCompletion
from apps.users.models import AdminScope


User = get_user_model()


class AdminRoleTaskServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="admin@example.com", password="pw")
        AdminScope.objects.create(user=self.admin)
        self.mentor_role = Roles.objects.create(role_name="mentor")

    def _make_role_holder(self, email, role, *, valid_to=None):
        user = User.objects.create_user(email=email, password="pw")
        RoleAssignmentHistory.objects.create(
            user=user,
            role=role,
            valid_from=timezone.now() - timedelta(days=1),
            valid_to=valid_to,
        )
        return user

    # ─── create ──────────────────────────────────────────────────────────

    def test_create_role_task(self):
        result = create_admin_role_task(self.admin, {
            "name": "Mentor Onboarding",
            "description": "Complete the onboarding checklist",
            "role": "mentor",
        })
        self.assertEqual(result["msg"], "Role task created successfully")
        self.assertEqual(result["data"]["name"], "Mentor Onboarding")
        self.assertEqual(result["data"]["role"]["roleName"], "mentor")
        self.assertEqual(result["data"]["creator_role"], CreatorRole.GLOBAL_ADMIN)

    def test_create_role_task_requires_a_role(self):
        result = create_admin_role_task(self.admin, {"name": "No Role"})
        self.assertEqual(result["msg"], "Role task requires a role")
        self.assertIsNone(result["data"])

    def test_create_and_update_trim_text(self):
        created = create_admin_role_task(self.admin, {
            "name": "  Original  ", "description": "  First description  ", "role": "mentor",
        })
        self.assertEqual(created["data"]["name"], "Original")
        self.assertEqual(created["data"]["description"], "First description")
        result = update_admin_role_task(self.admin, created["data"]["id"], {
            "name": "  Updated  ", "description": "  Updated description  ",
        })
        task = RoleTask.objects.get(id=created["data"]["id"])
        self.assertEqual(result["data"]["name"], "Updated")
        self.assertEqual(task.name, "Updated")
        self.assertEqual(task.description, "Updated description")
        update_admin_role_task(self.admin, task.id, {"description": None})
        task.refresh_from_db()
        self.assertEqual(task.description, "")

    def test_api_rejects_blank_names_without_creating_or_changing_tasks(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        created = create_admin_role_task(self.admin, {
            "name": "Original", "description": "Keep this", "role": "mentor",
        })
        task_id = created["data"]["id"]
        for name in ("", "   ", None):
            with self.subTest(name=name):
                response = client.post("/api/v1/admin/role-task/", {
                    "name": name, "role": "mentor",
                }, format="json")
                self.assertEqual(response.status_code, 400)
                response = client.patch(f"/api/v1/admin/role-task/{task_id}/", {
                    "name": name, "description": "Do not save this",
                }, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["msg"], "Role task name is required")
        self.assertEqual(RoleTask.objects.count(), 1)
        task = RoleTask.objects.get(id=task_id)
        self.assertEqual(task.name, "Original")
        self.assertEqual(task.description, "Keep this")

    def test_create_role_task_rejects_unknown_role(self):
        result = create_admin_role_task(self.admin, {"name": "Nope", "role": "wizard"})
        self.assertEqual(result["msg"], "Unknown role 'wizard'")
        self.assertIsNone(result["data"])
        self.assertFalse(RoleTask.objects.filter(name="Nope").exists())

    def test_create_role_task_rejects_admin_role_when_not_seeded(self):
        # `admin` passes _is_targetable_role via the AdminScope special case,
        # but RoleTask.role is a real FK — it still needs a seeded Roles row.
        self.assertFalse(Roles.objects.filter(role_name="admin").exists())
        result = create_admin_role_task(self.admin, {"name": "Admin Chore", "role": "admin"})
        self.assertIn("not seeded", result["msg"])
        self.assertIsNone(result["data"])

    def test_create_role_task_is_rejected_for_non_admin(self):
        outsider = self._make_role_holder("outsider@example.com", self.mentor_role)
        result = create_admin_role_task(outsider, {"name": "Escalation", "role": "mentor"})
        self.assertEqual(result["msg"], "You do not have authority to create role tasks")
        self.assertFalse(RoleTask.objects.filter(name="Escalation").exists())

    def test_create_role_task_succeeds_when_role_currently_has_zero_holders(self):
        # This is the whole point of TK4: a role task must be creatable before
        # anyone holds the role, since new holders pick it up automatically
        # later. The old fan-out explicitly rejected this case; this one must not.
        self.assertEqual(
            RoleAssignmentHistory.objects.filter(role=self.mentor_role).count(), 0
        )
        result = create_admin_role_task(self.admin, {"name": "Future Mentors", "role": "mentor"})
        self.assertEqual(result["msg"], "Role task created successfully")
        self.assertIsNotNone(result["data"])

    # ─── recipient preview ───────────────────────────────────────────────

    def test_count_role_recipients(self):
        for i in range(3):
            self._make_role_holder(f"m{i}@example.com", self.mentor_role)
        self._make_role_holder("gone@example.com", self.mentor_role).suspend()

        result = count_role_recipients(self.admin, "mentor")
        self.assertEqual(result["data"]["count"], 3)

    def test_count_role_recipients_rejects_unknown_role_and_non_admin(self):
        self.assertIsNone(count_role_recipients(self.admin, "wizard")["data"])
        outsider = self._make_role_holder("nosy@example.com", self.mentor_role)
        self.assertIsNone(count_role_recipients(outsider, "mentor")["data"])

    def test_count_role_recipients_admin_role_reads_admin_scope(self):
        other_admin = User.objects.create_user(email="admin2@example.com", password="pw")
        AdminScope.objects.create(user=other_admin)
        result = count_role_recipients(self.admin, "admin")
        self.assertEqual(result["data"]["count"], 2)

    # ─── list / get / update / delete ───────────────────────────────────

    def test_list_admin_role_tasks(self):
        create_admin_role_task(self.admin, {"name": "A", "role": "mentor"})
        create_admin_role_task(self.admin, {"name": "B", "role": "mentor"})
        result = list_admin_role_tasks(self.admin)
        self.assertEqual(result["data"]["total"], 2)
        self.assertCountEqual(
            [item["name"] for item in result["data"]["items"]], ["A", "B"]
        )

    def test_get_admin_role_task_by_id_not_found(self):
        result = get_admin_role_task_by_id(self.admin, 9999)
        self.assertEqual(result["msg"], "Role task not found")
        self.assertIsNone(result["data"])

    def test_due_date_sort_keeps_undated_tasks_last_in_both_directions(self):
        now = timezone.now()
        ids = []
        for name, due in (("Undated", None), ("Later", now + timedelta(days=2)),
                          ("Sooner", now), ("Same date", now)):
            result = create_admin_role_task(self.admin, {
                "name": name, "role": "mentor", "due_date": due,
            })
            ids.append(result["data"]["id"])
        for direction, expected in (
            ("asc", [ids[2], ids[3], ids[1], ids[0]]),
            ("desc", [ids[1], ids[2], ids[3], ids[0]]),
        ):
            with self.subTest(direction=direction):
                # Check pagination too: equal dates retain stable ID ordering.
                actual = []
                for page in (1, 2):
                    result = list_admin_role_tasks(
                        self.admin, page=page, limit=2, sort_by="due", sort_order=direction,
                    )
                    actual.extend(item["id"] for item in result["data"]["items"])
                self.assertEqual(actual, expected)

    def test_update_admin_role_task_is_the_bulk_edit_point(self):
        # This single PATCH is what "bulk-edit in one place" means: no
        # per-user rows exist to update alongside it.
        created = create_admin_role_task(self.admin, {"name": "Original", "role": "mentor"})
        role_task_id = created["data"]["id"]

        result = update_admin_role_task(self.admin, role_task_id, {"name": "Updated"})
        self.assertEqual(result["msg"], "Role task updated successfully")
        self.assertEqual(result["data"]["name"], "Updated")

    def test_update_admin_role_task_not_found(self):
        result = update_admin_role_task(self.admin, 9999, {"name": "Ghost"})
        self.assertEqual(result["msg"], "Role task not found")
        self.assertIsNone(result["data"])

    def test_delete_admin_role_task_soft_deletes(self):
        created = create_admin_role_task(self.admin, {"name": "Delete Me", "role": "mentor"})
        role_task_id = created["data"]["id"]

        result = delete_admin_role_task(self.admin, role_task_id)
        self.assertEqual(result["msg"], "Role task deleted successfully")
        role_task = RoleTask.objects.get(id=role_task_id)
        self.assertIsNotNone(role_task.deleted_at)
        # Soft-deleted rows drop out of the admin-visible/list queryset.
        self.assertEqual(list_admin_role_tasks(self.admin)["data"]["total"], 0)

    def test_update_admin_role_task_is_rejected_for_non_admin(self):
        created = create_admin_role_task(self.admin, {"name": "Original", "role": "mentor"})
        outsider = self._make_role_holder("outsider2@example.com", self.mentor_role)

        result = update_admin_role_task(outsider, created["data"]["id"], {"name": "Hijacked"})
        self.assertEqual(result["msg"], "You do not have authority to edit role tasks")
        self.assertEqual(RoleTask.objects.get(id=created["data"]["id"]).name, "Original")

    def test_delete_admin_role_task_is_rejected_for_non_admin(self):
        created = create_admin_role_task(self.admin, {"name": "Original", "role": "mentor"})
        outsider = self._make_role_holder("outsider3@example.com", self.mentor_role)

        result = delete_admin_role_task(outsider, created["data"]["id"])
        self.assertEqual(result["msg"], "You do not have authority to delete role tasks")
        self.assertIsNone(RoleTask.objects.get(id=created["data"]["id"]).deleted_at)

    def test_update_does_not_touch_existing_completion_records(self):
        # Editing the one definition row must not disturb per-user completion
        # state — there's nothing per-user to edit alongside it.
        created = create_admin_role_task(self.admin, {"name": "Original", "role": "mentor"})
        role_task = RoleTask.objects.get(id=created["data"]["id"])
        holder = self._make_role_holder("holder@example.com", self.mentor_role)
        completion = RoleTaskCompletion.objects.create(
            role_task=role_task, user=holder, completed=True
        )

        update_admin_role_task(self.admin, role_task.id, {"name": "Updated", "description": "New text"})

        completion.refresh_from_db()
        self.assertTrue(completion.completed)
        self.assertEqual(RoleTaskCompletion.objects.filter(role_task=role_task).count(), 1)

    # ─── completion progress ─────────────────────────────────────────────

    def test_list_reports_completed_over_holder_count(self):
        holders = [
            self._make_role_holder(f"p{i}@example.com", self.mentor_role)
            for i in range(3)
        ]
        created = create_admin_role_task(self.admin, {"name": "Onboarding", "role": "mentor"})
        role_task = RoleTask.objects.get(id=created["data"]["id"])
        RoleTaskCompletion.objects.create(role_task=role_task, user=holders[0], completed=True)
        RoleTaskCompletion.objects.create(role_task=role_task, user=holders[1], completed=False)

        result = list_admin_role_tasks(self.admin)
        item = next(i for i in result["data"]["items"] if i["id"] == role_task.id)
        self.assertEqual(item["completed_count"], 1)
        self.assertEqual(item["holder_count"], 3)

    def test_progress_excludes_completions_from_users_who_no_longer_hold_the_role(self):
        holder = self._make_role_holder("gone@example.com", self.mentor_role)
        created = create_admin_role_task(self.admin, {"name": "Onboarding", "role": "mentor"})
        role_task = RoleTask.objects.get(id=created["data"]["id"])
        RoleTaskCompletion.objects.create(role_task=role_task, user=holder, completed=True)

        RoleAssignmentHistory.objects.filter(user=holder, role=self.mentor_role).update(
            valid_to=timezone.now() - timedelta(minutes=1)
        )

        result = get_admin_role_task_by_id(self.admin, role_task.id)
        # The completion row itself is untouched (see test_role_task_api.py),
        # but it no longer counts toward "how many CURRENT holders are done".
        self.assertEqual(result["data"]["completed_count"], 0)
        self.assertEqual(result["data"]["holder_count"], 0)

    def test_progress_is_zero_over_zero_when_role_has_no_current_holders(self):
        created = create_admin_role_task(self.admin, {"name": "Future Mentors", "role": "mentor"})
        result = get_admin_role_task_by_id(self.admin, created["data"]["id"])
        self.assertEqual(result["data"]["completed_count"], 0)
        self.assertEqual(result["data"]["holder_count"], 0)

    def test_progress_is_scoped_per_role_task_not_shared_across_the_same_role(self):
        holder = self._make_role_holder("solo@example.com", self.mentor_role)
        first = create_admin_role_task(self.admin, {"name": "First", "role": "mentor"})
        second = create_admin_role_task(self.admin, {"name": "Second", "role": "mentor"})
        RoleTaskCompletion.objects.create(
            role_task_id=first["data"]["id"], user=holder, completed=True
        )

        result = list_admin_role_tasks(self.admin)
        by_id = {i["id"]: i for i in result["data"]["items"]}
        self.assertEqual(by_id[first["data"]["id"]]["completed_count"], 1)
        self.assertEqual(by_id[second["data"]["id"]]["completed_count"], 0)
        self.assertEqual(by_id[first["data"]["id"]]["holder_count"], 1)
        self.assertEqual(by_id[second["data"]["id"]]["holder_count"], 1)

    def test_delete_removes_visibility_for_every_current_holder_in_one_operation(self):
        from apps.common.rbac import active_role_ids

        created = create_admin_role_task(self.admin, {"name": "Onboarding", "role": "mentor"})
        role_task_id = created["data"]["id"]
        holders = [
            self._make_role_holder(f"holder{i}@example.com", self.mentor_role)
            for i in range(3)
        ]

        def visible_to(holder):
            # Same shape of query RoleTaskMineListView runs per holder.
            return RoleTask.objects.active().filter(
                id=role_task_id, role_id__in=active_role_ids(holder)
            ).exists()

        for holder in holders:
            self.assertTrue(visible_to(holder))

        delete_admin_role_task(self.admin, role_task_id)

        for holder in holders:
            # One delete call, zero remaining visibility for every holder.
            self.assertFalse(visible_to(holder))
