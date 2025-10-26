"""Permission helpers shared between chat views and consumers."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser


def user_has_group_access(user, group) -> bool:
    if isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return False

    role = getattr(user, "role", "")
    if role in {"admin", "supervisor"} or getattr(user, "is_staff", False):
        return True

    if getattr(group, "mentor_id", None) == getattr(user, "id", None):
        return True

    return group.members.filter(user=user).exists()


def user_can_moderate_group_chat(user, group) -> bool:
    if isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return False

    role = getattr(user, "role", "")
    if role in {"admin", "supervisor"} or getattr(user, "is_staff", False):
        return True

    return getattr(group, "mentor_id", None) == getattr(user, "id", None)
