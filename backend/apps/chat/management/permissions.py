from rest_framework.permissions import BasePermission
from apps.groups.models import GroupMembership
from apps.users.utils.roles import get_active_assignment
from django.utils import timezone
from datetime import timedelta

ROLE_ADMIN = "admin"
ROLE_SUPERVISOR = "supervisor"
ROLE_MENTOR = "mentor"


def _has_active_role_name(user, allowed_names):
    rah = get_active_assignment(user)
    return bool(rah and rah.role and rah.role.role_name in allowed_names)


class IsGroupMemberOrAdmin(BasePermission):
    """
    For GET/POST: allow if user is admin, or a member of the group.
    (Mentors are covered by membership since they belong to specific groups.)
    """
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if u.is_staff or _has_active_role_name(u, {ROLE_ADMIN}):
            return True
        gid = view.kwargs.get("group_pk")
        return GroupMembership.objects.filter(
            user=u,
            group_id=gid,
            left_at__isnull=True,
        ).exists()


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

        # Admin → global access
        if _has_active_role_name(u, {ROLE_ADMIN}):
            return True

        # Mentor / Supervisor → only if member of THIS group
        if _has_active_role_name(u, {ROLE_MENTOR, ROLE_SUPERVISOR}):
            return GroupMembership.objects.filter(
                user=u,
                group=obj.group,
                left_at__isnull=True,
            ).exists()

        return False


class CanEditMessage(BasePermission):
    """
    For PATCH (edit):
      - admin: edit everywhere, anytime
      - sender: edit only their own messages within 10 minutes of sending
    """
    def has_object_permission(self, request, view, obj):
        u = request.user
        if not u or not u.is_authenticated:
            return False

        # Admin → global access, anytime
        if _has_active_role_name(u, {ROLE_ADMIN}):
            return True

        # Must be the sender
        if obj.sender_user != u:
            return False

        # Check if within 10 minutes
        now = timezone.now()
        time_limit = timedelta(minutes=10)
        if now - obj.sent_at > time_limit:
            return False

        return True
