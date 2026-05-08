from rest_framework.permissions import BasePermission

from apps.groups.models import GroupMembership
from apps.users.utils.admin_scope import (
    has_chat_moderation_scope,
    is_operational_admin,
)
from apps.users.utils.roles import get_active_assignment

ROLE_ADMIN = "admin"


def _has_active_role_name(user, allowed_names):
    rah = get_active_assignment(user)
    return bool(rah and rah.role and rah.role.role_name in allowed_names)


class IsGroupMemberOrAdmin(BasePermission):
    """
    For GET / POST on /chat/groups/{gid}/messages/.

    Allowed if the user is:
      - an operational admin (``is_staff`` / ``is_superuser`` / any
        ``AdminScope`` row), so admins can read & post in any group
        without explicit membership;
      - or has the legacy ``role='admin'`` assignment (kept for
        backward compatibility while older role-only admins are migrated
        to ``AdminScope``);
      - or is an active member of the group.

    NOTE: This is intentionally looser than ``CanModerateMessage``. Reading
    a group is a less privileged action than deleting a message in it; the
    moderation gate has its own, stricter contract.
    """

    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if is_operational_admin(u) or _has_active_role_name(u, {ROLE_ADMIN}):
            return True
        gid = view.kwargs.get("group_pk")
        return GroupMembership.objects.filter(
            user=u,
            group_id=gid,
            left_at__isnull=True,
        ).exists()


class CanModerateMessage(BasePermission):
    """
    For DELETE /chat/messages/{message_id}/.

    Allowed if any of:
      - sender within the per-message self-action window
        (``Messages.can_be_self_deleted_by``); or
      - the user passes ``has_chat_moderation_scope`` for the message's
        track (i.e. has an explicit ``AdminScope`` row, global or
        track-pinned).

    See ``has_chat_moderation_scope`` for why ``is_staff`` / ``is_superuser``
    flags alone are not honored here.
    """

    def has_object_permission(self, request, view, obj):
        u = request.user
        if obj.can_be_self_deleted_by(u):
            return True
        return has_chat_moderation_scope(u, obj.group.track_id)


class CanEditMessage(BasePermission):
    """
    For PATCH /chat/messages/{message_id}/.

    Editing is sender-only and time-boxed: only the original sender may
    edit, and only within ``Messages.SELF_ACTION_WINDOW``. Admins do **not**
    get an edit override — admin moderation goes through DELETE so the
    audit trail (``deleted_at``) is preserved instead of silently
    rewriting message content.
    """

    def has_object_permission(self, request, view, obj):
        return obj.can_be_self_edited_by(request.user)
