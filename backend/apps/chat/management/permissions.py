from rest_framework.permissions import BasePermission
from apps.groups.models import GroupMembers
from apps.users.utils.roles import get_active_assignment

ROLE_ADMIN = "admin"
ROLE_SUPERVISOR = "supervisor"
ROLE_MENTOR = "mentor"


def _has_active_role_name(user, allowed_names):
    rah = get_active_assignment(user)
    return bool(rah and rah.role and rah.role.role_name in allowed_names)


class IsGroupMemberOrStaff(BasePermission):
    """
    For GET/POST: allow if user is staff, admin, supervisor, or a member of the group.
    (Mentors are covered by membership since they belong to specific groups.)
    """
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if u.is_staff or _has_active_role_name(u, {ROLE_ADMIN, ROLE_SUPERVISOR}):
            return True
        gid = view.kwargs.get("group_pk")
        return GroupMembers.objects.filter(user=u, group_id=gid).exists()


class CanModerateMessage(BasePermission):
    """
    For DELETE:
      - admin: moderate everywhere
      - supervisor: moderate everywhere
      - mentor: only in groups they belong to
    """
    def has_object_permission(self, request, view, obj):
        u = request.user
        if not u or not u.is_authenticated:
            return False

        # Admin / Supervisor → global access
        if _has_active_role_name(u, {ROLE_ADMIN, ROLE_SUPERVISOR}):
            return True

        # Mentor → only if member of THIS group
        if _has_active_role_name(u, {ROLE_MENTOR}):
            return GroupMembers.objects.filter(user=u, group=obj.group).exists()

        return False
