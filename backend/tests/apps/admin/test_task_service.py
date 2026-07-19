from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.admin.services.task import (
    list_admin_tasks, get_admin_task_by_id, create_admin_task,
    update_admin_task, delete_admin_task, toggle_admin_task,
    count_role_recipients,
)
from apps.groups.models import Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.tasks.models import CreatorRole, Task, TaskType
from apps.users.models import AdminScope


User = get_user_model()


class AdminTaskTests(TestCase):
    def setUp(self):
        self.group = Groups.objects.create(group_name="Group A")
        self.admin = User.objects.create_user(email="admin@example.com", password="pw")
        AdminScope.objects.create(user=self.admin)

    def test_lists_tasks_by_created_at_desc(self):
        older = Task.objects.create(
            name="older",
            task_type=TaskType.GROUP,
            group=self.group,
            created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        newer = Task.objects.create(
            name="newer",
            task_type=TaskType.GROUP,
            group=self.group,
            created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        now = timezone.now()
        Task.objects.filter(id=older.id).update(created_at=now - timedelta(days=1))
        Task.objects.filter(id=newer.id).update(created_at=now)

        result = list_admin_tasks(self.admin)

        ids = [item["id"] for item in result["data"]["items"]]
        self.assertEqual(ids, [newer.id, older.id])

    def test_create_group_task(self):
        result = create_admin_task(self.admin, {
            "name": "New Group Task",
            "description": "Do something",
            "task_type": TaskType.GROUP,
            "group": self.group.id,
        })
        self.assertEqual(result["msg"], "Task created successfully")
        self.assertEqual(result["data"]["name"], "New Group Task")
        self.assertEqual(result["data"]["group"], self.group.id)

    def test_create_group_task_missing_group(self):
        result = create_admin_task(self.admin, {
            "name": "Bad Task",
            "task_type": TaskType.GROUP,
        })
        self.assertEqual(result["msg"], "Group task requires a group")
        self.assertIsNone(result["data"])

    def test_create_individual_task(self):
        user = User.objects.create_user(email="user@example.com", password="pw")
        result = create_admin_task(self.admin, {
            "name": "Individual Task",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_user": user.id,
        })
        self.assertEqual(result["msg"], "Task created successfully")
        self.assertEqual(result["data"]["assigned_user"], user.id)

    def test_create_individual_task_missing_user(self):
        result = create_admin_task(self.admin, {
            "name": "Bad Task",
            "task_type": TaskType.INDIVIDUAL,
        })
        self.assertEqual(result["msg"], "Individual task requires an assigned user")
        self.assertIsNone(result["data"])

    # ─── role fan-out ────────────────────────────────────────────────────

    def _make_role_holder(self, email, role_name, *, valid_to=None):
        user = User.objects.create_user(email=email, password="pw")
        role, _ = Roles.objects.get_or_create(role_name=role_name)
        RoleAssignmentHistory.objects.create(
            user=user,
            role=role,
            valid_from=timezone.now() - timedelta(days=1),
            valid_to=valid_to,
        )
        return user

    def test_create_individual_task_by_role_fans_out(self):
        holders = [
            self._make_role_holder(f"mentor{i}@example.com", "mentor")
            for i in range(3)
        ]
        self._make_role_holder("student1@example.com", "student")

        result = create_admin_task(self.admin, {
            "name": "Mentor Training",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "mentor",
        })

        self.assertEqual(result["data"]["created_count"], 3)
        self.assertEqual(result["data"]["assigned_role"], "mentor")
        created = Task.objects.filter(name="Mentor Training")
        self.assertEqual(created.count(), 3)
        self.assertCountEqual(
            [t.assigned_user_id for t in created],
            [u.id for u in holders],
        )
        # Each recipient owns an independent, individually-completable row.
        for task in created:
            self.assertEqual(task.task_type, TaskType.INDIVIDUAL)
            self.assertIsNone(task.group_id)
            self.assertFalse(task.completed)
            self.assertEqual(task.creator_role, CreatorRole.GLOBAL_ADMIN)

    def test_role_fanout_excludes_expired_assignments(self):
        self._make_role_holder("current@example.com", "mentor")
        self._make_role_holder(
            "expired@example.com",
            "mentor",
            valid_to=timezone.now() - timedelta(hours=1),
        )

        result = create_admin_task(self.admin, {
            "name": "Only Current",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "mentor",
        })

        self.assertEqual(result["data"]["created_count"], 1)
        self.assertEqual(
            Task.objects.get(name="Only Current").assigned_user.email,
            "current@example.com",
        )

    def test_role_fanout_excludes_accounts_that_cannot_log_in(self):
        self._make_role_holder("active@example.com", "mentor")
        self._make_role_holder("suspended@example.com", "mentor").suspend()
        self._make_role_holder("gone@example.com", "mentor").deactivate()

        result = create_admin_task(self.admin, {
            "name": "Can Log In",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "mentor",
        })

        self.assertEqual(result["data"]["created_count"], 1)
        self.assertEqual(
            Task.objects.get(name="Can Log In").assigned_user.email,
            "active@example.com",
        )

    def test_role_fanout_includes_pending_and_invited_accounts(self):
        # `pending`/`invited` are is_active=False but CAN still sign in (see
        # User.INACTIVE_LOGIN_STATUSES) — a student awaiting parent permission
        # must not be silently dropped from an "everyone" fan-out.
        self._make_role_holder("pending@example.com", "student").mark_pending()
        self._make_role_holder("invited@example.com", "student").invite()

        result = create_admin_task(self.admin, {
            "name": "Reaches Everyone",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "student",
        })

        self.assertEqual(result["data"]["created_count"], 2)

    def test_count_role_recipients_matches_what_fanout_creates(self):
        for i in range(3):
            self._make_role_holder(f"c{i}@example.com", "mentor")
        self._make_role_holder("nope@example.com", "mentor").suspend()

        preview = count_role_recipients(self.admin, "mentor")
        self.assertEqual(preview["data"]["count"], 3)

        created = create_admin_task(self.admin, {
            "name": "Preview Match",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "mentor",
        })
        self.assertEqual(created["data"]["created_count"], preview["data"]["count"])

    def test_count_role_recipients_rejects_unknown_role_and_non_admin(self):
        self.assertIsNone(count_role_recipients(self.admin, "wizard")["data"])
        outsider = self._make_role_holder("nosy@example.com", "mentor")
        self.assertIsNone(count_role_recipients(outsider, "mentor")["data"])

    def test_role_fanout_does_not_duplicate_on_overlapping_assignments(self):
        # Nothing stops a user accumulating two live assignment rows for the
        # same role; that must still yield exactly one task for them.
        user = self._make_role_holder("twice@example.com", "mentor")
        RoleAssignmentHistory.objects.create(
            user=user,
            role=Roles.objects.get(role_name="mentor"),
            valid_from=timezone.now() - timedelta(hours=2),
        )

        result = create_admin_task(self.admin, {
            "name": "Exactly Once",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "mentor",
        })

        self.assertEqual(result["data"]["created_count"], 1)
        self.assertEqual(Task.objects.filter(name="Exactly Once").count(), 1)

    def test_role_fanout_admin_role_reads_admin_scope(self):
        # `admin` is an AdminScope row, not a RoleAssignmentHistory entry. A
        # second admin proves this reads the table rather than echoing the caller.
        other_admin = User.objects.create_user(email="admin2@example.com", password="pw")
        AdminScope.objects.create(user=other_admin)

        result = create_admin_task(self.admin, {
            "name": "Admin Chore",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "admin",
        })

        self.assertEqual(result["data"]["created_count"], 2)
        self.assertCountEqual(
            Task.objects.filter(name="Admin Chore").values_list(
                "assigned_user_id", flat=True
            ),
            [self.admin.id, other_admin.id],
        )

    def test_role_fanout_rejects_unknown_role(self):
        result = create_admin_task(self.admin, {
            "name": "Nope",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "wizard",
        })
        self.assertEqual(result["msg"], "Unknown role 'wizard'")
        self.assertIsNone(result["data"])
        self.assertFalse(Task.objects.filter(name="Nope").exists())

    def test_role_fanout_rejects_seeded_role_with_no_holders(self):
        Roles.objects.create(role_name="supervisor")
        result = create_admin_task(self.admin, {
            "name": "Nobody",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "supervisor",
        })
        self.assertEqual(
            result["msg"],
            "No active users currently hold the 'supervisor' role",
        )
        self.assertIsNone(result["data"])
        self.assertFalse(Task.objects.filter(name="Nobody").exists())

    def test_role_fanout_propagates_content_fields_to_every_row(self):
        for i in range(2):
            self._make_role_holder(f"m{i}@example.com", "mentor")
        parent = Task.objects.create(
            name="Parent", task_type=TaskType.GROUP, group=self.group,
            created_by=self.admin, creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        due = timezone.now() + timedelta(days=7)

        create_admin_task(self.admin, {
            "name": "  Padded Name  ",
            "description": "  some detail  ",
            "due_date": due,
            "status": "in_progress",
            "parent": parent.id,
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "mentor",
        })

        created = Task.objects.filter(name="Padded Name")
        self.assertEqual(created.count(), 2)
        for task in created:
            self.assertEqual(task.description, "some detail")
            self.assertEqual(task.due_date, due)
            self.assertEqual(task.status, "in_progress")
            self.assertEqual(task.parent_id, parent.id)

    def test_group_task_rejects_a_role_target(self):
        result = create_admin_task(self.admin, {
            "name": "Confused",
            "task_type": TaskType.GROUP,
            "group": self.group.id,
            "assigned_role": "mentor",
        })
        self.assertEqual(result["msg"], "Group tasks cannot target a role")
        self.assertIsNone(result["data"])
        self.assertFalse(Task.objects.filter(name="Confused").exists())

    def test_role_fanout_accepts_a_newly_seeded_role(self):
        # Roles are data, not code: seeding a new one must work without an edit
        # to the backend.
        alumni = Roles.objects.create(role_name="alumni")
        user = User.objects.create_user(email="alum@example.com", password="pw")
        RoleAssignmentHistory.objects.create(
            user=user, role=alumni, valid_from=timezone.now() - timedelta(days=1)
        )

        result = create_admin_task(self.admin, {
            "name": "Alumni Survey",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "alumni",
        })

        self.assertEqual(result["data"]["created_count"], 1)
        self.assertEqual(
            Task.objects.get(name="Alumni Survey").assigned_user_id, user.id
        )

    def test_role_fanout_rejects_both_user_and_role(self):
        user = self._make_role_holder("both@example.com", "mentor")
        result = create_admin_task(self.admin, {
            "name": "Ambiguous",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_user": user.id,
            "assigned_role": "mentor",
        })
        self.assertEqual(
            result["msg"], "Provide either an assigned user or a role, not both"
        )
        self.assertIsNone(result["data"])
        self.assertFalse(Task.objects.filter(name="Ambiguous").exists())

    def test_role_fanout_is_rejected_for_non_admin(self):
        outsider = self._make_role_holder("outsider@example.com", "mentor")
        result = create_admin_task(outsider, {
            "name": "Escalation",
            "task_type": TaskType.INDIVIDUAL,
            "assigned_role": "mentor",
        })
        self.assertEqual(
            result["msg"],
            "You do not have authority to create tasks for this target",
        )
        self.assertFalse(Task.objects.filter(name="Escalation").exists())

    def test_get_admin_task_by_id_found(self):
        task = Task.objects.create(
            name="Find Me", task_type=TaskType.GROUP,
            group=self.group, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        result = get_admin_task_by_id(self.admin, task.id)
        self.assertEqual(result["msg"], "Task retrieved successfully")
        self.assertEqual(result["data"]["name"], "Find Me")

    def test_get_admin_task_by_id_not_found(self):
        result = get_admin_task_by_id(self.admin, 9999)
        self.assertEqual(result["msg"], "Task not found")
        self.assertIsNone(result["data"])

    def test_update_admin_task(self):
        task = Task.objects.create(
            name="Original", task_type=TaskType.GROUP,
            group=self.group, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        result = update_admin_task(self.admin, task.id, {"name": "Updated"})
        self.assertEqual(result["msg"], "Task updated successfully")
        self.assertEqual(result["data"]["name"], "Updated")

    def test_update_admin_task_not_found(self):
        result = update_admin_task(self.admin, 9999, {"name": "Ghost"})
        self.assertEqual(result["msg"], "Task not found")
        self.assertIsNone(result["data"])

    def test_delete_admin_task(self):
        task = Task.objects.create(
            name="Delete Me", task_type=TaskType.GROUP,
            group=self.group, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        result = delete_admin_task(self.admin, task.id)
        self.assertEqual(result["msg"], "Task deleted successfully")
        task.refresh_from_db()
        self.assertIsNotNone(task.deleted_at)

    def test_delete_admin_task_not_found(self):
        result = delete_admin_task(self.admin, 9999)
        self.assertEqual(result["msg"], "Task not found")
        self.assertIsNone(result["data"])

    def test_toggle_admin_task_complete(self):
        task = Task.objects.create(
            name="Toggle Me", task_type=TaskType.GROUP,
            group=self.group, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
        )
        result = toggle_admin_task(self.admin, task.id, True)
        self.assertEqual(result["msg"], "Task updated successfully")
        self.assertTrue(result["data"]["completed"])

    def test_toggle_admin_task_incomplete(self):
        task = Task.objects.create(
            name="Toggle Me 2", task_type=TaskType.GROUP,
            group=self.group, created_by=self.admin,
            creator_role=CreatorRole.GLOBAL_ADMIN,
            completed=True,
        )
        result = toggle_admin_task(self.admin, task.id, False)
        self.assertFalse(result["data"]["completed"])

    def test_toggle_admin_task_not_found(self):
        result = toggle_admin_task(self.admin, 9999, True)
        self.assertEqual(result["msg"], "Task not found")
        self.assertIsNone(result["data"])
