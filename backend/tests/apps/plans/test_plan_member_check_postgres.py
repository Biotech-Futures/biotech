"""GP3 completion under real row locks (PostgreSQL only; skipped on SQLite).

A tick waits for the task row lock while another connection ends the
viewer's access and commits; the tick must then be refused. Also covers the
plan's first-tick race: simultaneous ticks of one shared task. Run with
``--settings=config.settings_local`` against the local PostgreSQL.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.groups.models import GroupMembership, Groups
from apps.plans.models import PlanStage, PlanTask, PlanTaskCompletion


@skipUnlessDBFeature("has_select_for_update")
class GroupPlanCheckPostgresTests(TransactionTestCase):
    def setUp(self):
        User = get_user_model()
        self.group = Groups.objects.create(group_name="BTF1", year=timezone.localdate().year)
        self.student = User.objects.create_user(email="student@test.com", password="pw")
        self.other_student = User.objects.create_user(email="student2@test.com", password="pw")
        for user in (self.student, self.other_student):
            GroupMembership.objects.create(user=user, group=self.group, membership_role="student")
        stage = PlanStage.objects.create(name="Getting started")
        self.shared = PlanTask.objects.create(
            stage=stage, name="Agree a time", audience_role="student", completion_mode="per_group",
        )

    def tick(self, user, body=None):
        """POST a tick from its own thread and database connection, closed after."""
        close_old_connections()
        try:
            client = APIClient()
            client.force_authenticate(user)
            url = reverse(
                "plans:group-plan-task-check", kwargs={"group_id": self.group.id, "task_id": self.shared.id},
            )
            return client.post(url, {"completed": True} if body is None else body, format="json")
        finally:
            connection.close()

    def in_own_connection(self, change):
        """Run and commit ``change`` on another connection."""
        close_old_connections()
        try:
            with transaction.atomic():
                change()
        finally:
            connection.close()

    def wait_until_blocked(self):
        """Wait until another connection is queued for a row lock."""
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_locks WHERE NOT granted")
                if cursor.fetchone()[0]:
                    return
            time.sleep(0.02)
        self.fail("The tick never waited for the task row lock.")

    def tick_while_locked(self, user, change):
        """Hold the task row lock; tick; commit ``change`` elsewhere; release."""
        with ThreadPoolExecutor(max_workers=2) as pool:
            with transaction.atomic():
                PlanTask.objects.select_for_update().get(pk=self.shared.pk)
                pending = pool.submit(self.tick, user)
                self.wait_until_blocked()
                self.assertFalse(pending.done())
                pool.submit(self.in_own_connection, change).result(timeout=10)
            return pending.result(timeout=10)

    def assert_refused(self, response):
        self.assertEqual(response.status_code, 404, response.data)
        self.assertFalse(PlanTaskCompletion.objects.exists())
        self.assertFalse(AuditLog.objects.filter(entity_type="plan_task").exists())

    def test_a_tick_waits_for_the_lock_then_saves(self):
        response = self.tick_while_locked(self.student, lambda: None)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(PlanTaskCompletion.objects.get(task=self.shared, group=self.group, user=None).completed)

    def test_a_membership_ended_while_waiting_is_refused(self):
        def end_membership():
            GroupMembership.objects.filter(user=self.student, group=self.group).update(left_at=timezone.now())

        self.assert_refused(self.tick_while_locked(self.student, end_membership))

    def test_a_group_deleted_while_waiting_is_refused(self):
        def delete_group():
            Groups.objects.filter(pk=self.group.pk).update(deleted_at=timezone.now())

        self.assert_refused(self.tick_while_locked(self.student, delete_group))

    def test_simultaneous_first_ticks_save_one_shared_record(self):
        barrier = Barrier(2)

        def tick_together(user):
            barrier.wait(timeout=10)
            return self.tick(user)

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(tick_together, [self.student, self.other_student]))

        self.assertEqual([r.status_code for r in responses], [200, 200])
        self.assertEqual(PlanTaskCompletion.objects.filter(task=self.shared, group=self.group).count(), 1)
        # Only the first changed anything; the second found it already ticked.
        self.assertEqual(AuditLog.objects.filter(entity_type="plan_task").count(), 1)

    def test_simultaneous_flips_are_applied_one_after_the_other(self):
        barrier = Barrier(2)

        def flip_together(user):
            barrier.wait(timeout=10)
            return self.tick(user, body={})

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(flip_together, [self.student, self.other_student]))

        # One ticked, the other then unticked: neither read a stale value.
        self.assertEqual(sorted(r.data["completed"] for r in responses), [False, True])
        self.assertFalse(PlanTaskCompletion.objects.get(task=self.shared, group=self.group, user=None).completed)
        self.assertEqual(AuditLog.objects.filter(entity_type="plan_task").count(), 2)
