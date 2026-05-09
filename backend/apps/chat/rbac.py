from __future__ import annotations

from django.apps import apps
from apps.common.rbac import (
    group_participant_qs,
    is_global_admin,
    track_admin_track_ids,
)


ATTACHMENT_MESSAGE_TYPE = "attachment"


def _group_from_value(group):
    if group is None:
        return None
    if hasattr(group, "id") and hasattr(group, "track_id"):
        return group

    Groups = apps.get_model("groups", "Groups")
    group_id = getattr(group, "id", group)
    return Groups.objects.only("id", "track_id").filter(pk=group_id).first()


def is_track_admin_for_group(user, group) -> bool:
    target_group = _group_from_value(group)
    if target_group is None or getattr(target_group, "track_id", None) is None:
        return False
    return int(target_group.track_id) in track_admin_track_ids(user)


def can_access_chat_group(user, group) -> bool:
    if not user or not user.is_authenticated:
        return False

    target_group = _group_from_value(group)
    if target_group is None:
        return False

    if is_global_admin(user) or is_track_admin_for_group(user, target_group):
        return True

    return group_participant_qs(user, target_group.id).exists()


def can_manage_chat_message(user, message) -> bool:
    if not user or not user.is_authenticated or message is None:
        return False

    target_group = _group_from_value(getattr(message, "group", None) or getattr(message, "group_id", None))
    if target_group is None:
        return False

    if is_global_admin(user) or is_track_admin_for_group(user, target_group):
        return True

    if not group_participant_qs(user, target_group.id).exists():
        return False

    if hasattr(message, "can_be_self_actioned_by") and message.can_be_self_actioned_by(user):
        return True

    # Developer note: attachment delete rules are narrower than general moderation.
    # Regular participants can remove only their own attachment messages here, while
    # mentor/supervisor moderation continues to flow through the existing role path.
    if (
        getattr(message, "message_type", None) == ATTACHMENT_MESSAGE_TYPE
        and getattr(message, "sender_user_id", None) == user.id
    ):
        return True

    return False
