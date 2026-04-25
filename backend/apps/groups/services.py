from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.users.models import MentorProfile

from .models import GroupMembership

MEMBER_MEMBERSHIP_ROLE = GroupMembership.MembershipRole.MEMBER
MENTOR_MEMBERSHIP_ROLE = GroupMembership.MembershipRole.MENTOR


def active_mentor_membership_qs(*, mentor_user=None, group=None):
    queryset = GroupMembership.objects.filter(
        membership_role=GroupMembership.MembershipRole.MENTOR,
        left_at__isnull=True,
    )
    if mentor_user is not None:
        queryset = queryset.filter(user=mentor_user)
    if group is not None:
        queryset = queryset.filter(group=group)
    return queryset


@transaction.atomic
def assign_mentor_to_group(*, group, mentor_user, replace_existing=False):
    mentor_profile = MentorProfile.objects.filter(user=mentor_user).first()
    if mentor_profile is None:
        raise ValidationError("Selected user does not have a mentor profile.")

    current_group_mentors = list(
        active_mentor_membership_qs(group=group).select_related("user")
    )
    current_same_membership = next(
        (membership for membership in current_group_mentors if membership.user_id == mentor_user.id),
        None,
    )

    if current_same_membership is not None and not replace_existing:
        return {
            "membership": current_same_membership,
            "created": False,
            "replaced_memberships": [],
        }

    if current_group_mentors and not replace_existing and current_same_membership is None:
        raise ValidationError("Group already has an active mentor. Use the replacement workflow.")

    active_other_group_count = (
        active_mentor_membership_qs(mentor_user=mentor_user)
        .exclude(group=group)
        .count()
    )
    if current_same_membership is None and active_other_group_count >= mentor_profile.max_group_count:
        raise ValidationError("Selected mentor has already reached max_group_count.")

    replaced_memberships = []
    if replace_existing:
        now = timezone.now()
        for membership in current_group_mentors:
            if membership.user_id == mentor_user.id:
                continue
            membership.left_at = now
            membership.save(update_fields=["left_at"])
            replaced_memberships.append(membership)

    if current_same_membership is not None:
        return {
            "membership": current_same_membership,
            "created": False,
            "replaced_memberships": replaced_memberships,
        }

    membership = GroupMembership.objects.create(
        group=group,
        user=mentor_user,
        membership_role=GroupMembership.MembershipRole.MENTOR,
    )
    return {
        "membership": membership,
        "created": True,
        "replaced_memberships": replaced_memberships,
    }
