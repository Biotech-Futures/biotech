def is_track_archived(user) -> bool:
    """True iff the user is assigned to an archived track. Callers decide
    whether to exempt admins."""
    if not user or not user.track_id:
        return False
    return bool(getattr(user.track, "is_archived", False))


def revoke_sessions_for_archived_track(track) -> int:
    """Force-logout every non-admin member of an archived track. Mirrors the
    login gate's admin exemption so a track admin who archives their own
    track isn't kicked out of their own session mid-fix."""
    from apps.users.models import User
    from apps.users.utils.admin_scope import is_operational_admin
    from apps.users.utils.sessions import terminate_user_sessions

    count = 0
    for user in User.objects.filter(track=track).iterator():
        if is_operational_admin(user):
            continue
        terminate_user_sessions(user)
        count += 1
    return count
