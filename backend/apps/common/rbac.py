from __future__ import annotations

from django.apps import apps
from django.db.models import Q
from django.utils import timezone

from apps.users.utils.admin_scope import get_admin_track_ids


GLOBAL_ADMIN_ROLE_NAMES = {"admin", "global_admin"}


def active_role_assignments(user):
    RoleAssignmentHistory = apps.get_model("resources", "RoleAssignmentHistory")
    now = timezone.now()
    return RoleAssignmentHistory.objects.filter(
        user=user,
        valid_from__lte=now,
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=now)
    ).select_related("role")


def active_role_ids(user) -> set[int]:
    return {
        role_id
        for role_id in active_role_assignments(user).values_list("role_id", flat=True)
        if role_id is not None
    }


def active_role_names(user) -> set[str]:
    return {
        str(name).strip().lower()
        for name in active_role_assignments(user).values_list("role__role_name", flat=True)
        if name
    }


def group_participant_qs(user, group_id=None):
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

    return bool(active_role_names(user) & GLOBAL_ADMIN_ROLE_NAMES)


def track_admin_track_ids(user) -> set[int]:
    if not user or not user.is_authenticated or is_global_admin(user):
        return set()

    # Developer note: centralize the shared admin-scope primitive here so
    # chat/resource RBAC cannot silently drift on global-vs-track checks.
    track_ids = get_admin_track_ids(user)
    if track_ids in (None, []):
        return set()
    return {int(track_id) for track_id in track_ids if track_id is not None}
