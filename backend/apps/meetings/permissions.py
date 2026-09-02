from rest_framework import permissions

from apps.common.rbac import group_participant_qs, is_admin
from apps.groups.models import GroupMembership


# Membership role is per-group -- a user can mentor group A and be a student
# in group B -- so scheduling authority is checked against
# GroupMembership.membership_role, NOT the global role assignment that
# apps.common.rbac.user_has_role reads.
MENTOR_MEMBERSHIP_ROLES = (
    GroupMembership.MembershipRoleChoices.MENTOR,
    GroupMembership.MembershipRoleChoices.SUPERVISOR,
)


def is_group_mentor(user, group_id) -> bool:
    if not user or not user.is_authenticated:
        return False
    return (
        group_participant_qs(user, group_id)
        .filter(membership_role__in=MENTOR_MEMBERSHIP_ROLES)
        .exists()
    )


def is_group_participant(user, group_id) -> bool:
    if not user or not user.is_authenticated:
        return False
    return group_participant_qs(user, group_id).exists()


def can_manage_meeting(user, meeting) -> bool:
    """Organiser, any mentor/supervisor on the group, or an admin."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if is_admin(user):
        return True
    if meeting.organiser_id and meeting.organiser_id == user.id:
        return True
    return is_group_mentor(user, meeting.group_id)


def _meeting_of(obj):
    """Normalise GroupMeeting / MeetingNote / MeetingSummary to the meeting.

    The reverse accessor is absent on GroupMeeting itself, so getattr with a
    default returns the object unchanged -- one code path for all three.
    """
    return getattr(obj, "meeting", obj)


class IsGroupParticipant(permissions.BasePermission):
    """Any active member of the meeting's group. Used for the shared note."""

    message = "You are not a member of this meeting's group."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        meeting = _meeting_of(obj)
        return is_admin(request.user) or is_group_participant(
            request.user, meeting.group_id
        )


class IsGroupMentorOrReadOnly(permissions.BasePermission):
    """Read for any participant, write for the organiser / mentor / admin.

    The events app's EventManagePermission is admin-write-only, which is
    correct for programme events and wrong for these -- hence a local class
    rather than reusing it.
    """

    message = "Only a mentor or supervisor of this group can change this meeting."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        meeting = _meeting_of(obj)
        if request.method in permissions.SAFE_METHODS:
            return is_admin(request.user) or is_group_participant(
                request.user, meeting.group_id
            )
        return can_manage_meeting(request.user, meeting)
