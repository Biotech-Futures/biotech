from apps.users.models import AdminScope


def is_operational_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return AdminScope.objects.filter(user=user).exists()


def get_admin_track_ids(user):
    if not is_operational_admin(user):
        return []
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
