from __future__ import annotations

from django.apps import apps
from django.db.models import Q
from django.utils import timezone


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


def get_active_role_name(user):
    """Return the most recent active role name for ``user`` (lower-cased) or None.

    This is the single source of truth for the legacy ``_get_active_role``
    helpers that used to live across ``events``, ``certificates``, etc.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None

    assignment = active_role_assignments(user).order_by("-valid_from", "-id").first()
    if not assignment or not assignment.role:
        return None

    return str(assignment.role.role_name).strip().lower()


def user_has_role(user, *role_names) -> bool:
    """Return True if ``user`` has any of the given role names active.

    Comparison is case-insensitive and tolerant of whitespace; this lets
    callers use the canonical ``ROLE_*`` constants without worrying about
    how the seeded data is cased.
    """
    if not role_names:
        return False
    normalized = {str(name).strip().lower() for name in role_names if name}
    return bool(normalized & active_role_names(user))


def group_participant_qs(user, group_id=None, *, include_deleted_groups=False):
    GroupMembership = apps.get_model("groups", "GroupMembership")
    queryset = GroupMembership.objects.filter(
        user=user,
        left_at__isnull=True,
    )
    # Active membership never flows through a deleted group unless explicitly requested.
    if not include_deleted_groups:
        queryset = queryset.filter(group__deleted_at__isnull=True)
    if group_id is not None:
        queryset = queryset.filter(group_id=group_id)
    return queryset


def is_global_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    AdminScope = apps.get_model("users", "AdminScope")
    return AdminScope.objects.filter(user=user, is_global=True).exists()


def track_admin_track_ids(user) -> set[int]:
    if not user or not user.is_authenticated or is_global_admin(user):
        return set()
    AdminScope = apps.get_model("users", "AdminScope")
    return {
        int(track_id)
        for track_id in AdminScope.objects.filter(
            user=user, is_global=False, track__isnull=False
        ).values_list("track_id", flat=True)
    }
