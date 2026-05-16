from rest_framework.permissions import BasePermission

from apps.chat.rbac import can_access_chat_group, can_manage_chat_message
from apps.groups.models import Groups


class IsGroupMemberOrAdmin(BasePermission):
    """Read / post: caller is an active member of the target group, or
    has admin scope for the group's track (global or track-scoped).

    Delegates to the shared RBAC helper so REST, download, and websocket
    access stay aligned.
    """

    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        gid = view.kwargs.get("group_pk")
        # A deleted group no longer grants chat access through membership or admin scope.
        group = Groups.objects.only("id", "track_id").filter(
            pk=gid,
            deleted_at__isnull=True,
        ).first()
        return can_access_chat_group(u, group)


class CanModerateMessage(BasePermission):
    """Delete a chat message.

    Allowed iff the caller is the sender within the self-action window,
    or has admin scope for the message's group's track.
    """

    def has_object_permission(self, request, view, obj):
        return can_manage_chat_message(getattr(request, "user", None), obj)


class CanEditMessage(BasePermission):
    """Edit a chat message. Same rule as CanModerateMessage — sender
    within the self-action window, or admin scope for the message's
    track. Kept as a separate class so views wire intent explicitly.
    """

    def has_object_permission(self, request, view, obj):
        return can_manage_chat_message(getattr(request, "user", None), obj)
