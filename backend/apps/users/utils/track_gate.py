from apps.users.utils.admin_scope import is_operational_admin


def is_login_blocked_by_archived_track(user) -> bool:
    """Block users on archived tracks from logging in. Operational admins
    are exempt so a track admin who archives their own track can still log
    in to undo it."""
    if not user or not user.track_id:
        return False
    if is_operational_admin(user):
        return False
    return bool(getattr(user.track, "is_archived", False))
