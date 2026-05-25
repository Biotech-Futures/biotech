from django.contrib.sessions.models import Session
from django.utils import timezone

from apps.user_sessions.models import UserSession


def terminate_user_sessions(user) -> None:
    """Revoke every live session for this user — password reset, archived-track
    lockout, suspension, etc. all share the same forced-logout flow."""
    now = timezone.now()
    UserSession.objects.filter(
        user=user, ended_at__isnull=True, revoked_at__isnull=True,
    ).update(revoked_at=now, ended_at=now)
    _flush_django_sessions_for_user(user)


def _flush_django_sessions_for_user(user) -> int:
    """Delete django_session rows whose decoded data names this user.

    Django's DB session store has no user_id index, so we scan active rows.
    Cost is O(active sessions); fine at our scale.
    """
    user_id_str = str(user.pk)
    to_delete = [
        s.session_key
        for s in Session.objects.filter(expire_date__gt=timezone.now()).iterator()
        if str(_safe_decode(s).get("_auth_user_id")) == user_id_str
    ]
    if to_delete:
        Session.objects.filter(session_key__in=to_delete).delete()
    return len(to_delete)


def _safe_decode(session) -> dict:
    try:
        return session.get_decoded()
    except Exception:
        return {}
