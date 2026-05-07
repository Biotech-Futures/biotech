from rest_framework.permissions import BasePermission

from apps.groups.models import Groups

from apps.chat.rbac import can_access_chat_group, can_manage_chat_message


class IsGroupMemberOrAdmin(BasePermission):
    """
    For GET/POST: allow if user is admin, or a member of the group.
    (Mentors are covered by membership since they belong to specific groups.)
    """
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        gid = view.kwargs.get("group_pk")
        group = Groups.objects.only("id", "track_id").filter(pk=gid).first()
        # Developer note: chat views delegate group scope checks to the shared RBAC
        # helper so REST, download, and websocket access stay aligned.
        return can_access_chat_group(u, group)


class CanModerateMessage(BasePermission):
    """
    For DELETE:
      - admin: moderate everywhere
      - supervisor: moderate everywhere
      - mentor: only in groups they belong to
    """
    def has_object_permission(self, request, view, obj):
        return can_manage_chat_message(getattr(request, "user", None), obj)
