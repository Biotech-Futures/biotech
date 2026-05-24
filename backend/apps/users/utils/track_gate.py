def is_track_archived(user) -> bool:
    """True iff the user is assigned to an archived track. Callers decide
    whether to exempt admins."""
    if not user or not user.track_id:
        return False
    return bool(getattr(user.track, "is_archived", False))
