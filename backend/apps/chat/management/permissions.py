from rest_framework.permissions import BasePermission
from datetime import timedelta
from django.utils import timezone
from apps.groups.models import GroupMembership
from apps.users.utils.roles import get_active_assignment

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
    For DELETE /chat/groups/{group_id}/messages/{message_id}/:
      - sender (self-delete): allowed only within (10 minutes)
       of the message's sent_at
      - admin: moderate everywhere
      - supervisor: moderate everywhere (within their groups)
      - mentor: only in groups they belong to
    """
    def has_object_permission(self, request, view, obj):
        u = request.user
        if not u or not u.is_authenticated:
            return False

        if obj.sender_user_id == u.id:
            if timezone.now() <= obj.sent_at + timedelta(minutes=10):
                return True

        if _has_active_role_name(u, {ROLE_ADMIN}):
            return True

        if _has_active_role_name(u, {ROLE_MENTOR, ROLE_SUPERVISOR}):
            return GroupMembership.objects.filter(
                user=u,
                group=obj.group,
                left_at__isnull=True,
            ).exists()

        return False
