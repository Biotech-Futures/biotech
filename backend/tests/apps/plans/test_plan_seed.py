from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from apps.admin.management.commands.seed_dummy_data import Command, SEED_PREFIX
from apps.groups.models import GroupMembership, Groups
from apps.plans.models import PlanStage, PlanTask, PlanTaskCompletion


class PlanSeedTests(TestCase):
    def setUp(self):
        self.command = Command(stdout=StringIO())
        self.user = get_user_model().objects.create_user(email="seed-plan@example.test")
        self.group = Groups.objects.create(group_name=f"{SEED_PREFIX} Plan group")
        GroupMembership.objects.create(
            group=self.group, user=self.user, membership_role="student"
        )
        self.groups = [(self.group, {})]
        self.buckets = {"admin": []}

    def test_seed_covers_stages_audiences_modes_and_date_states(self):
        self.command._create_plan_tasks(self.groups, self.buckets)
        self.assertEqual(PlanStage.objects.active().count(), 3)
        self.assertEqual(PlanTask.objects.active().count(), 6)
        self.assertEqual(
            set(PlanTask.objects.values_list("audience_role", "completion_mode")),
            {(role, mode) for role in ("student", "mentor", "supervisor")
             for mode in ("per_person", "per_group")},
        )
        self.assertTrue(PlanTask.objects.filter(due_date__lt=timezone.localdate()).exists())
        self.assertTrue(PlanTask.objects.filter(due_date__gt=timezone.localdate()).exists())
        self.assertTrue(PlanTask.objects.filter(due_date__isnull=True).exists())
        self.assertTrue(PlanTask.objects.exclude(resource_url="").exists())
        self.assertTrue(PlanTaskCompletion.objects.filter(user=self.user, completed=True).exists())

    def test_wipe_removes_seed_tasks_before_protected_stages_and_keeps_real_plan(self):
        self.command._create_plan_tasks(self.groups, self.buckets)
        real_stage = PlanStage.objects.create(name="Real stage")
        real_task = PlanTask.objects.create(
            stage=real_stage, name="Real task", audience_role="student"
        )
        self.command._wipe()
        self.assertEqual(list(PlanStage.objects.all()), [real_stage])
        self.assertEqual(list(PlanTask.objects.all()), [real_task])
        self.assertFalse(PlanTaskCompletion.objects.exists())

    def test_wipe_refuses_non_seed_tasks_in_seed_stage_without_deleting_anything(self):
        self.command._create_plan_tasks(self.groups, self.buckets)
        PlanTask.objects.create(
            stage=PlanStage.objects.first(), name="Real task", audience_role="student"
        )
        with self.assertRaisesMessage(CommandError, "non-seed plan task"):
            self.command._wipe()
        self.assertEqual(PlanTask.objects.count(), 7)
        self.assertEqual(PlanStage.objects.count(), 3)

    def test_old_groups_do_not_receive_seed_completions(self):
        self.group.year = timezone.localdate().year - 1
        self.group.save(update_fields=["year"])
        self.command._create_plan_tasks(self.groups, self.buckets)
        self.assertFalse(PlanTaskCompletion.objects.exists())
        self.assertIn("outside the active cohort", self.command.stdout.getvalue())
