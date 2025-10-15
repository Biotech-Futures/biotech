from rest_framework.permissions import BasePermission
from apps.groups.models import GroupMembers
from apps.users.utils.roles import get_active_assignment

# Role name constants (match actual capitalization in database)
ROLE_ADMIN = "Admin"
ROLE_SUPERVISOR = "Supervisor"
ROLE_MENTOR = "Mentor"


def _has_active_role_name(user, allowed_names):
    """
    Check if user has an active role matching any of the allowed names.
    Comparison is case-insensitive to handle database inconsistencies.
    """
    rah = get_active_assignment(user)
    if not rah or not rah.role:
        return False
    # Case-insensitive comparison
    user_role_lower = rah.role.role_name.lower()
    allowed_names_lower = {name.lower() for name in allowed_names}
    return user_role_lower in allowed_names_lower


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
      - Platform staff (is_staff): moderate everywhere
      - admin role: moderate everywhere
      - supervisor role: moderate everywhere
      - mentor role: only in groups they belong to
    """
    def has_object_permission(self, request, view, obj):
        u = request.user
        if not u or not u.is_authenticated:
            return False

        # Platform staff → global access
        if u.is_staff or u.is_superuser:
            return True

        # Admin / Supervisor role → global access
        if _has_active_role_name(u, {ROLE_ADMIN, ROLE_SUPERVISOR}):
            return True

        # Mentor → only if member of THIS group
        if _has_active_role_name(u, {ROLE_MENTOR}):
            return GroupMembers.objects.filter(user=u, group=obj.group).exists()

        return False
