import logging

logger = logging.getLogger(__name__)


def is_track_archived(user) -> bool:
    """True iff the user is assigned to an archived track. Callers decide
    whether to exempt admins."""
    if not user or not user.track_id:
        return False
    return bool(getattr(user.track, "is_archived", False))


def revoke_sessions_for_archived_track(track) -> int:
    """Force-logout every non-admin user affected by ``track`` being archived.

    "Affected" is the union of two populations so we catch participants the
    login gate alone would miss:

    * directly assigned via ``User.track`` — the login gate's own scope, and
    * active members of any group on this track
      (``GroupMembership.left_at IS NULL``) — a mentor/student whose primary
      ``User.track`` differs but who is actively collaborating in a
      track-bound group should also lose their live session, otherwise an
      archived track can still be edited via the group surface.

    Operational admins are skipped — mirrors the login-gate exemption so a
    track admin who archives their own track isn't kicked out of their own
    session mid-fix. Returns the count of users actually terminated (admins
    are reported separately in the ops log).
    """
    from django.db.models import Q

    from apps.common.rbac import is_admin
    from apps.groups.models import GroupMembership
    from apps.users.models import User
    from apps.users.utils.sessions import terminate_user_sessions

    affected_users = (
        User.objects.filter(
            Q(track_id=track.id)
            | Q(
                id__in=GroupMembership.objects.filter(
                    group__track_id=track.id,
                    left_at__isnull=True,
                ).values("user_id")
            )
        )
        .distinct()
    )

    terminated_count = 0
    skipped_admin_count = 0
    for user in affected_users.iterator():
        if is_admin(user):
            skipped_admin_count += 1
            continue
        terminate_user_sessions(user)
        terminated_count += 1

    if terminated_count or skipped_admin_count:
        logger.info(
            "track.archive.sessions_terminated",
            extra={
                "track_id": track.id,
                "terminated_user_count": terminated_count,
                "skipped_admin_count": skipped_admin_count,
            },
        )

    return terminated_count
