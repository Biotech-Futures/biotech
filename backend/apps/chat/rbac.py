from __future__ import annotations

from django.apps import apps
from django.db.models import Q
from django.utils import timezone

from apps.users.utils.admin_scope import get_admin_track_ids


GLOBAL_ADMIN_ROLE_NAMES = {"admin", "global_admin"}
MODERATOR_ROLE_NAMES = {"mentor", "supervisor"}
ATTACHMENT_MESSAGE_TYPE = "attachment"


def _active_role_assignments(user):
    RoleAssignmentHistory = apps.get_model("resources", "RoleAssignmentHistory")
    now = timezone.now()
    return RoleAssignmentHistory.objects.filter(
        user=user,
        valid_from__lte=now,
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=now)
    ).select_related("role")


def _active_role_names(user) -> set[str]:
    return {
        str(name).strip().lower()
        for name in _active_role_assignments(user).values_list("role__role_name", flat=True)
        if name
    }


def _group_from_value(group):
    if group is None:
        return None
    if hasattr(group, "id") and hasattr(group, "track_id"):
        return group

    Groups = apps.get_model("groups", "Groups")
    group_id = getattr(group, "id", group)
    return Groups.objects.only("id", "track_id").filter(pk=group_id).first()


def _group_participant_qs(user, group_id=None):
    GroupMembership = apps.get_model("groups", "GroupMembership")
    queryset = GroupMembership.objects.filter(
        user=user,
        left_at__isnull=True,
    )
    if group_id is not None:
        queryset = queryset.filter(group_id=group_id)
    return queryset


def is_global_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or getattr(user, "is_superuser", False):
        return True

    AdminScope = apps.get_model("users", "AdminScope")
    if AdminScope.objects.filter(user=user, is_global=True).exists():
        return True

    return bool(_active_role_names(user) & GLOBAL_ADMIN_ROLE_NAMES)


def _track_admin_track_ids(user) -> set[int]:
    if not user or not user.is_authenticated or is_global_admin(user):
        return set()

    track_ids = get_admin_track_ids(user)
    if track_ids in (None, []):
        return set()
    return {int(track_id) for track_id in track_ids if track_id is not None}


def is_track_admin_for_group(user, group) -> bool:
    target_group = _group_from_value(group)
    if target_group is None or getattr(target_group, "track_id", None) is None:
        return False
    return int(target_group.track_id) in _track_admin_track_ids(user)


def can_access_chat_group(user, group) -> bool:
    if not user or not user.is_authenticated:
        return False

    target_group = _group_from_value(group)
    if target_group is None:
        return False

    if is_global_admin(user) or is_track_admin_for_group(user, target_group):
        return True

    return _group_participant_qs(user, target_group.id).exists()


def can_manage_chat_message(user, message) -> bool:
    if not user or not user.is_authenticated or message is None:
        return False

    target_group = _group_from_value(getattr(message, "group", None) or getattr(message, "group_id", None))
    if target_group is None:
        return False

    if is_global_admin(user) or is_track_admin_for_group(user, target_group):
        return True

    if not _group_participant_qs(user, target_group.id).exists():
        return False

    # Developer note: attachment delete rules are narrower than general moderation.
    # Regular participants can remove only their own attachment messages here, while
    # mentor/supervisor moderation continues to flow through the existing role path.
    if (
        getattr(message, "message_type", None) == ATTACHMENT_MESSAGE_TYPE
        and getattr(message, "sender_user_id", None) == user.id
    ):
        return True

    return bool(_active_role_names(user) & MODERATOR_ROLE_NAMES)
