from apps.users.models import AdminScope


def is_operational_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return AdminScope.objects.filter(user=user).exists()


def get_admin_track_ids(user):
    if not is_operational_admin(user):
        return []
    if user.is_staff or user.is_superuser:
        return None
    if AdminScope.objects.filter(user=user, is_global=True).exists():
        return None
    return list(
        AdminScope.objects.filter(user=user, is_global=False).values_list("track_id", flat=True)
    )


def can_admin_track(user, track_or_id) -> bool:
    if track_or_id is None:
        return is_operational_admin(user)

    track_id = getattr(track_or_id, "id", track_or_id)
    allowed_track_ids = get_admin_track_ids(user)
    if allowed_track_ids is None:
        return True
    return track_id in allowed_track_ids


def has_chat_moderation_scope(user, track_id) -> bool:
    """
    Stricter variant used by chat moderation only.

    Unlike ``is_operational_admin`` / ``can_admin_track`` (which honor
    ``is_staff`` / ``is_superuser`` flags as global admin), chat moderation
    requires an explicit ``AdminScope`` row:

    - ``is_global=True`` row → allowed for any track
    - ``is_global=False`` row whose ``track_id`` matches → allowed for that track

    Bare ``is_staff`` / ``is_superuser`` flags and ``role='admin'``
    assignments alone are **not** sufficient. Chat deletion is a privileged
    moderation action and is intentionally gated on a purpose-built RBAC row
    rather than a broad platform flag.
    """
    from django.db.models import Q

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if track_id is None:
        return AdminScope.objects.filter(user=user, is_global=True).exists()
    return AdminScope.objects.filter(
        Q(is_global=True) | Q(track_id=track_id),
        user=user,
    ).exists()
