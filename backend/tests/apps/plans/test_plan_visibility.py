from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.groups.models import GroupMembership, Groups
from apps.plans.visibility import (
    active_audience_memberships,
    current_plan_groups,
    group_sees_plan,
)
from apps.submissions.models import Deadline
from apps.submissions.services import current_cohort


class PlanVisibilityTests(TestCase):
    def setUp(self):
        self.year = timezone.localdate().year
        self.group = Groups.objects.create(group_name="Current group", year=self.year)
        self.old_group = Groups.objects.create(group_name="Old group", year=self.year - 1)
        self.deleted_group = Groups.objects.create(
            group_name="Deleted group", year=self.year,
            created_at=timezone.now() - timezone.timedelta(days=1),
            deleted_at=timezone.now(),
        )

    def test_only_non_deleted_groups_in_supplied_year_are_eligible(self):
        self.assertEqual(list(current_plan_groups(self.year)), [self.group])
        self.assertTrue(group_sees_plan(self.group, self.year))
        self.assertFalse(group_sees_plan(self.old_group, self.year))
        self.assertFalse(group_sees_plan(self.deleted_group, self.year))

    def test_uses_live_database_state_for_restored_or_deleted_group(self):
        Groups.objects.filter(pk=self.group.pk).update(deleted_at=timezone.now())
        self.assertFalse(group_sees_plan(self.group, self.year))
        Groups.objects.filter(pk=self.group.pk).update(deleted_at=None)
        self.assertTrue(group_sees_plan(self.group, self.year))

    def test_active_deadline_changes_eligible_cohort(self):
        self.assertEqual(current_cohort(), self.year)
        next_group = Groups.objects.create(group_name="Next group", year=self.year + 1)
        Deadline.objects.create(
            closes_at=timezone.now().replace(year=self.year + 1, month=7, day=15)
        )
        year = current_cohort()
        self.assertEqual(year, self.year + 1)
        self.assertEqual(list(current_plan_groups(year)), [next_group])

    def test_unplaced_groups_are_not_filtered_out(self):
        self.assertIsNone(self.group.placed_at)
        self.assertTrue(group_sees_plan(self.group, self.year))

    def test_active_roster_includes_suspended_and_deactivated_accounts(self):
        User = get_user_model()
        kept = []
        for index, account_status in enumerate(("active", "suspended", "deactivated")):
            user = User.objects.create_user(email=f"roster{index}@example.test")
            User.objects.filter(pk=user.pk).update(account_status=account_status)
            kept.append(GroupMembership.objects.create(
                group=self.group,
                user=user,
                membership_role=GroupMembership.MembershipRoleChoices.values[index],
            ).pk)
        left_user = User.objects.create_user(email="left@example.test")
        blank_user = User.objects.create_user(email="blank@example.test")
        deleted_user = User.objects.create_user(email="deleted-group@example.test")
        GroupMembership.objects.create(
            group=self.group, user=left_user, membership_role="student",
            joined_at=timezone.now() - timezone.timedelta(days=2), left_at=timezone.now(),
        )
        GroupMembership.objects.create(group=self.group, user=blank_user, membership_role="")
        GroupMembership.objects.create(
            group=self.deleted_group, user=deleted_user, membership_role="student"
        )
        actual = active_audience_memberships([self.group.pk, self.deleted_group.pk])
        self.assertCountEqual(actual.values_list("pk", flat=True), kept)

    def test_only_requested_groups_are_included(self):
        user = get_user_model().objects.create_user(email="old-member@example.test")
        GroupMembership.objects.create(
            group=self.old_group, user=user, membership_role="student"
        )
        self.assertFalse(active_audience_memberships([self.group.pk]).exists())
        self.assertFalse(active_audience_memberships([]).exists())
