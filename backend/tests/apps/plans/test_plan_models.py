from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.groups.models import Groups
from apps.plans.models import PlanStage, PlanTask, PlanTaskCompletion


class PlanModelTests(TestCase):
    def setUp(self):
        self.stage = PlanStage.objects.create(name="Getting started")
        self.task = PlanTask.objects.create(
            stage=self.stage, name="Read the guide", audience_role="student"
        )
        self.group = Groups.objects.create(group_name="Plan group")
        self.user = get_user_model().objects.create_user(email="plan@example.test")

    def complete(self, **overrides):
        values = {"task": self.task, "group": self.group, "user": self.user}
        values.update(overrides)
        return PlanTaskCompletion.objects.create(**values)

    def test_only_one_person_record_per_task_group_user(self):
        self.complete(completed=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.complete()

    def test_only_one_shared_record_per_task_group(self):
        self.complete(user=None)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.complete(user=None)

    def test_records_are_independent_between_people_and_groups(self):
        other_user = get_user_model().objects.create_user(email="other@example.test")
        other_group = Groups.objects.create(group_name="Another plan group")
        self.complete()
        self.complete(user=other_user)
        self.complete(group=other_group)
        self.complete(user=None)
        self.assertEqual(PlanTaskCompletion.objects.count(), 4)

    def test_plan_order_uses_stage_and_task_positions_not_dates(self):
        self.task.position = 9
        self.task.save(update_fields=["position"])
        first = PlanTask.objects.create(
            stage=self.stage, name="First", audience_role="student", position=1
        )
        tied = PlanTask.objects.create(
            stage=self.stage, name="Tie", audience_role="student", position=1
        )
        later_stage = PlanStage.objects.create(name="Research", position=1)
        later = PlanTask.objects.create(
            stage=later_stage,
            name="Later stage",
            audience_role="mentor",
            due_date=timezone.localdate() - timezone.timedelta(days=5),
        )
        self.assertEqual(list(PlanTask.objects.active()), [first, tied, self.task, later])

    def test_soft_delete_hides_task_without_removing_its_ticks(self):
        completion = self.complete(completed=True)
        self.task.soft_delete()
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.deleted_at)
        self.assertFalse(PlanTask.objects.active().exists())
        self.assertTrue(PlanTaskCompletion.objects.get(pk=completion.pk).completed)

    def test_deleted_stages_hide_their_tasks(self):
        self.stage.deleted_at = timezone.now()
        self.stage.save(update_fields=["deleted_at"])
        self.assertFalse(PlanStage.objects.active().exists())
        self.assertFalse(PlanTask.objects.active().exists())
        self.assertTrue(PlanTask.objects.filter(pk=self.task.pk).exists())

    def test_hard_deleting_a_stage_cannot_destroy_tasks(self):
        with self.assertRaises(ProtectedError):
            self.stage.delete()
        self.assertTrue(PlanTask.objects.filter(pk=self.task.pk).exists())

    def test_moving_task_preserves_person_and_shared_records(self):
        self.complete(completed=True)
        self.complete(user=None, completed=True)
        new_stage = PlanStage.objects.create(name="New stage")
        self.task.stage = new_stage
        self.task.save(update_fields=["stage"])
        self.assertEqual(self.task.completions.filter(completed=True).count(), 2)

    def test_replacement_task_does_not_inherit_any_ticks(self):
        self.complete(completed=True)
        self.complete(user=None, completed=True)
        self.task.soft_delete()
        replacement = PlanTask.objects.create(
            stage=self.stage, name=self.task.name, audience_role="student"
        )
        self.assertFalse(replacement.completions.exists())
        self.assertEqual(self.task.completions.count(), 2)

    def test_deleting_membership_does_not_delete_person_progress(self):
        from apps.groups.models import GroupMembership

        membership = GroupMembership.objects.create(
            group=self.group, user=self.user, membership_role="student"
        )
        completion = self.complete(completed=True)
        membership.delete()
        self.assertTrue(PlanTaskCompletion.objects.filter(pk=completion.pk).exists())

    def test_hard_deleting_group_cascades_completions_but_keeps_template(self):
        self.complete()
        self.group.delete()
        self.assertFalse(PlanTaskCompletion.objects.exists())
        self.assertTrue(PlanTask.objects.filter(pk=self.task.pk).exists())

    def test_deleting_creator_keeps_task(self):
        self.task.created_by = self.user
        self.task.save(update_fields=["created_by"])
        self.user.delete()
        self.task.refresh_from_db()
        self.assertIsNone(self.task.created_by_id)

    def test_django_admin_cannot_bypass_mutation_services(self):
        request = RequestFactory().get("/admin/")
        for model in (PlanStage, PlanTask, PlanTaskCompletion):
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request))
            self.assertFalse(model_admin.has_delete_permission(request))
