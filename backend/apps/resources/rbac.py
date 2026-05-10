from __future__ import annotations

from django.apps import apps
from django.db.models import Q
from apps.common.rbac import (
    active_role_ids,
    group_participant_qs,
    is_global_admin,
    track_admin_track_ids,
)


RESOURCE_PUBLIC_SCOPE = "public"
RESOURCE_TRACK_SCOPE = "track"
RESOURCE_GROUP_SCOPE = "group"


def _track_id_from_value(track) -> int | None:
    if track is None:
        return None

    if hasattr(track, "track_id") and getattr(track, "track_id", None):
        return int(track.track_id)

    value = getattr(track, "id", track)
    if value in (None, ""):
        return None
    return int(value)


def _is_group_participant(user, group) -> bool:
    if not group:
        return False
    return group_participant_qs(user, group_id=getattr(group, "id", group)).exists()


def _resource_audiences(resource):
    # Stash the materialized list on the instance so callers that access
    # audiences multiple times per request (e.g. ``can_access_resource_file``
    # walks them via ``_resource_track_ids`` and then again directly) don't
    # re-query the table on each call.
    cached = getattr(resource, "_audiences_evaluated", None)
    if cached is not None:
        return cached
    prefetched = getattr(resource, "_prefetched_objects_cache", {})
    if "audiences" in prefetched:
        cached = list(prefetched["audiences"])
    else:
        ResourceAudience = apps.get_model("resources", "ResourceAudience")
        cached = list(
            ResourceAudience.objects.filter(resource=resource).select_related("role", "track")
        )
    try:
        resource._audiences_evaluated = cached
    except Exception:
        # Non-model objects in tests may forbid attribute assignment; fall back
        # to returning the freshly evaluated list without caching.
        pass
    return cached


def _resource_track_ids(resource) -> set[int]:
    if resource is None:
        return set()

    cached = getattr(resource, "_track_ids_evaluated", None)
    if cached is not None:
        return cached

    track_ids: set[int] = set()

    if getattr(resource, "track_id", None):
        track_ids.add(int(resource.track_id))

    # Use the cached related ``group`` if Django has already loaded it via
    # ``select_related`` to avoid an extra query. Only fall back to a fetch
    # when neither the cached object nor a separate group_id is missing the
    # track_id.
    group = getattr(resource, "group", None)
    if group is None and getattr(resource, "group_id", None):
        Groups = apps.get_model("groups", "Groups")
        group = Groups.objects.only("id", "track_id").filter(pk=resource.group_id).first()
    if group is not None and getattr(group, "track_id", None):
        track_ids.add(int(group.track_id))

    for audience in _resource_audiences(resource):
        if audience.track_id:
            track_ids.add(int(audience.track_id))

    try:
        resource._track_ids_evaluated = track_ids
    except Exception:
        pass
    return track_ids


def _resource_list_access_q(user):
    role_ids = active_role_ids(user)
    member_group_ids = group_participant_qs(user).values_list("group_id", flat=True)

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


def is_track_admin_for_track(user, track) -> bool:
    track_id = _track_id_from_value(track)
    if track_id is None:
        return False
    return track_id in track_admin_track_ids(user)


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

    allowed_track_ids = track_admin_track_ids(user)
    return bool(allowed_track_ids) and candidate_track_ids.issubset(allowed_track_ids)


def can_access_resource_file(user, resource) -> bool:
    if not user or not user.is_authenticated or resource is None:
        return False
    if getattr(resource, "deleted_at", None) is not None:
        return False
    if is_global_admin(user):
        return True

    admin_track_ids = track_admin_track_ids(user)
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

    user_role_ids = active_role_ids(user)
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
    admin_track_ids = track_admin_track_ids(user)
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
