from __future__ import annotations

from django.apps import apps
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
