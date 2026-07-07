from __future__ import annotations

from django.apps import apps
from django.db.models import Q
from apps.common.rbac import (
    active_role_ids,
    group_participant_qs,
    is_admin,
)


RESOURCE_PUBLIC_SCOPE = "public"
RESOURCE_GROUP_SCOPE = "group"


def _is_group_participant(user, group) -> bool:
    if not group:
        return False
    return group_participant_qs(user, group_id=getattr(group, "id", group)).exists()


def _resource_audiences(resource):
    # Per-instance memoization; can_access_resource_file walks audiences twice.
    cached = getattr(resource, "_audiences_evaluated", None)
    if cached is not None:
        return cached
    prefetched = getattr(resource, "_prefetched_objects_cache", {})
    if "audiences" in prefetched:
        cached = list(prefetched["audiences"])
    else:
        ResourceAudience = apps.get_model("resources", "ResourceAudience")
        cached = list(
            ResourceAudience.objects.filter(resource=resource).select_related("role")
        )
    try:
        resource._audiences_evaluated = cached
    except Exception:
        pass
    return cached


def _resource_list_access_q(user):
    role_ids = active_role_ids(user)
    member_group_ids = group_participant_qs(user).values_list("group_id", flat=True)

    access_q = Q(visibility_scope=RESOURCE_PUBLIC_SCOPE)

    if role_ids:
        access_q |= Q(audiences__role_id__in=role_ids)

    access_q |= Q(visibility_scope=RESOURCE_GROUP_SCOPE, group_id__in=member_group_ids)

    return access_q


def can_manage_resource_file(user, resource=None, track=None) -> bool:
    return is_admin(user)


def can_access_resource_file(user, resource) -> bool:
    if not user or not user.is_authenticated or resource is None:
        return False
    if getattr(resource, "deleted_at", None) is not None:
        return False
    if is_admin(user):
        return True

    if resource.visibility_scope == RESOURCE_PUBLIC_SCOPE:
        return True

    if (
        resource.visibility_scope == RESOURCE_GROUP_SCOPE
        and getattr(resource, "group_id", None)
        and _is_group_participant(user, resource.group or resource.group_id)
    ):
        return True

    user_role_ids = active_role_ids(user)
    for audience in _resource_audiences(resource):
        if audience.role_id is not None and audience.role_id in user_role_ids:
            return True

    return False


def filter_resources_for_user(queryset, user, *, for_management: bool = False):
    if not user or not user.is_authenticated:
        return queryset.none()
    if is_admin(user):
        return queryset

    if for_management:
        return queryset.none()

    return queryset.filter(_resource_list_access_q(user)).distinct()
