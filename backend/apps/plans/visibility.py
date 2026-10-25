"""Shared cohort and audience queries; viewer permissions belong to GP3."""

from apps.groups.models import GroupMembership, Groups


def current_plan_groups(year):
    """Callers read current_cohort() once and pass the resulting year."""
    return Groups.objects.filter(deleted_at__isnull=True, year=year)


def group_sees_plan(group, year):
    return current_plan_groups(year).filter(pk=group.pk).exists()


def active_audience_memberships(group_ids):
    # Login status deliberately does not affect roster-based progress totals.
    return GroupMembership.objects.filter(
        group_id__in=group_ids,
        group__deleted_at__isnull=True,
        left_at__isnull=True,
        membership_role__in=GroupMembership.MembershipRoleChoices.values,
    )
