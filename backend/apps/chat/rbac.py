from __future__ import annotations

from django.apps import apps
from django.contrib.auth import get_user_model
from apps.common.rbac import (
    group_participant_qs,
    is_admin,
)


def _group_from_value(group):
    if group is None:
        return None
    if hasattr(group, "id"):
        # Deleted groups must not authorize chat access from cached model instances.
        if getattr(group, "deleted_at", None) is not None:
            return None
        return group

    Groups = apps.get_model("groups", "Groups")
    group_id = getattr(group, "id", group)
    return Groups.objects.only("id").filter(
        pk=group_id,
        deleted_at__isnull=True,
    ).first()


def can_access_chat_group(user, group) -> bool:
    if not user or not user.is_authenticated:
        return False

    target_group = _group_from_value(group)
    if target_group is None:
        return False

    if is_admin(user):
        return True

    return group_participant_qs(user, target_group.id).exists()


def chat_recipients_qs(group_id, *, exclude_user_id=None):
    """Members of ``group_id`` a message is actually addressed to.

    Role/status predicate matches the unread digest (``services/digest.py``,
    which additionally scopes to non-deleted groups): supervisors observe
    rather than participate, and login-blocked accounts can never open the
    board. Counting either makes "read by everyone" unreachable.
    ``invited``/``pending`` users DO count — they are ``is_active=False``
    but can still sign in.
    """
    GroupMembership = apps.get_model("groups", "GroupMembership")
    User = get_user_model()
    queryset = (
        GroupMembership.objects
        .filter(group_id=group_id, left_at__isnull=True)
        .exclude(membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR)
        .exclude(user__account_status__in=User.INACTIVE_LOGIN_STATUSES)
        .select_related("user")
    )
    if exclude_user_id is not None:
        queryset = queryset.exclude(user_id=exclude_user_id)
    return queryset


def can_manage_chat_message(user, message) -> bool:
    """Authorize edit or delete of an existing chat message.

    Allowed iff the caller is an admin, or is the original sender within
    the self-action window — delegated to
    ``Messages.can_be_self_actioned_by`` so the window definition lives
    in one place. Mentor/supervisor roles do not by themselves grant
    moderation rights.
    """
    if not user or not user.is_authenticated or message is None:
        return False

    target_group = _group_from_value(getattr(message, "group", None) or getattr(message, "group_id", None))
    if target_group is None:
        return False

    if is_admin(user):
        return True

    self_action = getattr(message, "can_be_self_actioned_by", None)
    if callable(self_action):
        return bool(self_action(user))
    return False
