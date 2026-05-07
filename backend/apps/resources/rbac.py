from __future__ import annotations

from django.apps import apps
from django.db.models import Q
from django.utils import timezone

from apps.users.utils.admin_scope import get_admin_track_ids


GLOBAL_ADMIN_ROLE_NAMES = {"admin", "global_admin"}
RESOURCE_PUBLIC_SCOPE = "public"
RESOURCE_TRACK_SCOPE = "track"
RESOURCE_GROUP_SCOPE = "group"


def _active_role_assignments(user):
    RoleAssignmentHistory = apps.get_model("resources", "RoleAssignmentHistory")
    now = timezone.now()
    return RoleAssignmentHistory.objects.filter(
        user=user,
        valid_from__lte=now,
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=now)
    ).select_related("role")


def _active_role_ids(user) -> set[int]:
    return {
        role_id
        for role_id in _active_role_assignments(user).values_list("role_id", flat=True)
        if role_id is not None
    }


def _active_role_names(user) -> set[str]:
    return {
        str(name).strip().lower()
        for name in _active_role_assignments(user).values_list("role__role_name", flat=True)
        if name
    }


def _track_id_from_value(track) -> int | None:
    if track is None:
        return None

    if hasattr(track, "track_id") and getattr(track, "track_id", None):
        return int(track.track_id)

    value = getattr(track, "id", track)
    if value in (None, ""):
        return None
    return int(value)


def _group_participant_qs(user, group_id=None):
    GroupMembership = apps.get_model("groups", "GroupMembership")
    queryset = GroupMembership.objects.filter(
        user=user,
        left_at__isnull=True,
    )
    if group_id is not None:
        queryset = queryset.filter(group_id=group_id)
    return queryset


def _is_group_participant(user, group) -> bool:
    if not group:
        return False
    return _group_participant_qs(user, group_id=getattr(group, "id", group)).exists()


def _resource_audiences(resource):
    ResourceAudience = apps.get_model("resources", "ResourceAudience")
    prefetched = getattr(resource, "_prefetched_objects_cache", {})
    if "audiences" in prefetched:
        return prefetched["audiences"]
    return ResourceAudience.objects.filter(resource=resource).select_related("role", "track")


def _resource_track_ids(resource) -> set[int]:
    track_ids: set[int] = set()
    if resource is None:
        return track_ids

    if getattr(resource, "track_id", None):
        track_ids.add(int(resource.track_id))

    group = getattr(resource, "group", None)
    if group is None and getattr(resource, "group_id", None):
        Groups = apps.get_model("groups", "Groups")
        group = Groups.objects.only("id", "track_id").filter(pk=resource.group_id).first()

    if group is not None and getattr(group, "track_id", None):
        track_ids.add(int(group.track_id))

    for audience in _resource_audiences(resource):
        if audience.track_id:
            track_ids.add(int(audience.track_id))

    return track_ids


def _track_admin_track_ids(user) -> set[int]:
    if not user or not user.is_authenticated or is_global_admin(user):
        return set()

    track_ids = get_admin_track_ids(user)
    if track_ids in (None, []):
        return set()
    return {int(track_id) for track_id in track_ids if track_id is not None}


def _resource_list_access_q(user):
    role_ids = _active_role_ids(user)
    member_group_ids = _group_participant_qs(user).values_list("group_id", flat=True)

    access_q = Q(visibility_scope=RESOURCE_PUBLIC_SCOPE)

    if user.track_id:
        access_q |= (
            Q(visibility_scope=RESOURCE_TRACK_SCOPE)
            & (Q(track_id=user.track_id) | Q(group__track_id=user.track_id))
        )
        access_q |= Q(audiences__role__isnull=True, audiences__track_id=user.track_id)
        if role_ids:
            access_q |= Q(audiences__role_id__in=role_ids, audiences__track_id=user.track_id)

    if role_ids:
        access_q |= Q(audiences__role_id__in=role_ids, audiences__track__isnull=True)

    access_q |= Q(visibility_scope=RESOURCE_GROUP_SCOPE, group_id__in=member_group_ids)

    return access_q


def is_global_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or getattr(user, "is_superuser", False):
        return True

    AdminScope = apps.get_model("users", "AdminScope")
    if AdminScope.objects.filter(user=user, is_global=True).exists():
        return True

    return bool(_active_role_names(user) & GLOBAL_ADMIN_ROLE_NAMES)


def is_track_admin_for_track(user, track) -> bool:
    track_id = _track_id_from_value(track)
    if track_id is None:
        return False
    return track_id in _track_admin_track_ids(user)


def can_manage_resource_file(user, resource=None, track=None) -> bool:
    if not user or not user.is_authenticated:
        return False
    if is_global_admin(user):
        return True

    candidate_track_ids = set()
    track_id = _track_id_from_value(track)
    if track_id is not None:
        candidate_track_ids.add(track_id)
    candidate_track_ids.update(_resource_track_ids(resource))

    if not candidate_track_ids:
        return False

    allowed_track_ids = _track_admin_track_ids(user)
    return bool(allowed_track_ids) and candidate_track_ids.issubset(allowed_track_ids)


def can_access_resource_file(user, resource) -> bool:
    if not user or not user.is_authenticated or resource is None:
        return False
    if getattr(resource, "deleted_at", None) is not None:
        return False
    if is_global_admin(user):
        return True

    admin_track_ids = _track_admin_track_ids(user)
    if admin_track_ids:
        return bool(_resource_track_ids(resource) & admin_track_ids)

    if resource.visibility_scope == RESOURCE_PUBLIC_SCOPE:
        return True

    resource_track_ids = _resource_track_ids(resource)
    if (
        resource.visibility_scope == RESOURCE_TRACK_SCOPE
        and user.track_id
        and int(user.track_id) in resource_track_ids
    ):
        return True

    if (
        resource.visibility_scope == RESOURCE_GROUP_SCOPE
        and getattr(resource, "group_id", None)
        and _is_group_participant(user, resource.group or resource.group_id)
    ):
        return True

    user_role_ids = _active_role_ids(user)
    user_track_id = int(user.track_id) if user.track_id else None
    for audience in _resource_audiences(resource):
        role_ok = audience.role_id is None or audience.role_id in user_role_ids
        track_ok = audience.track_id is None or audience.track_id == user_track_id
        if role_ok and track_ok:
            return True

    return False


def filter_resources_for_user(queryset, user, *, for_management: bool = False):
    if not user or not user.is_authenticated:
        return queryset.none()
    if is_global_admin(user):
        return queryset

    # Developer note: resource RBAC stays intentionally small and file-focused here
    # instead of introducing a generic policy engine for unrelated modules.
    admin_track_ids = _track_admin_track_ids(user)
    if admin_track_ids:
        admin_q = (
            Q(track_id__in=admin_track_ids)
            | Q(group__track_id__in=admin_track_ids)
            | Q(audiences__track_id__in=admin_track_ids)
        )
        return queryset.filter(admin_q).distinct()

    if for_management:
        return queryset.none()

    return queryset.filter(_resource_list_access_q(user)).distinct()
