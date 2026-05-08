from datetime import timedelta

from rest_framework.permissions import BasePermission

from apps.groups.models import GroupMembership, Groups
from apps.users.utils.admin_scope import can_admin_track

SELF_ACTION_WINDOW = timedelta(minutes=10)


class IsGroupMemberOrAdmin(BasePermission):
    """Read / post: caller is an active member of the target group, or
    has admin scope for the group's track (global ``AdminScope`` or a
    track-scoped row), as defined by ``can_admin_track``.
    """

    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        gid = view.kwargs.get("group_pk")
        if gid is None:
            return False
        if GroupMembership.objects.filter(
            user=u, group_id=gid, left_at__isnull=True
        ).exists():
            return True
        track_id = (
            Groups.objects.filter(pk=gid).values_list("track_id", flat=True).first()
        )
        return can_admin_track(u, track_id)


class CanModerateMessage(BasePermission):
    """Delete a chat message.

    Allowed iff the caller is the sender within ``SELF_ACTION_WINDOW``,
    or has admin scope for the message's group's track via
    ``can_admin_track`` (global or track-scoped ``AdminScope``).
    """

    def has_object_permission(self, request, view, obj):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if obj.can_be_self_actioned_by(u):
            return True
        return can_admin_track(u, obj.group.track_id)


class CanEditMessage(BasePermission):
    """Edit a chat message. Same rule as ``CanModerateMessage`` —
    sender within the self-action window, or admin scope for the
    message's track.
    """

    def has_object_permission(self, request, view, obj):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if obj.can_be_self_actioned_by(u):
            return True
        return can_admin_track(u, obj.group.track_id)
