# apps/user_sessions/middleware.py
import logging

from django.db import IntegrityError
from django.utils import timezone

from .models import UserSession

logger = logging.getLogger(__name__)


# RFC 7231 idempotent / safe methods. Skipping these avoids 2 DB writes
# (get_or_create + save) on every read request — typically ~70% of traffic.
# State-changing methods (POST/PATCH/PUT/DELETE) still update last_activity_at,
# so any real user action keeps the analytics row fresh. Purely passive
# read-only users will show stale last_activity_at, which is acceptable since
# the field isn't consumed by any security/operational logic.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class SessionTrackingMiddleware:
    """
    Middleware to track user sessions in the Sessions model for analytics.
    Records authenticated *state-changing* requests to track user activity.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.method in _SAFE_METHODS:
            return response

        if not request.user.is_authenticated:
            return response

        # Tracking must never break an already-committed write. The view has
        # already returned by this point; any exception here would surface as
        # a 500 to the client even though the requested action succeeded,
        # prompting retries that double-execute non-idempotent operations.
        try:
            self._track(request)
        except Exception:
            logger.exception("session_tracking.failed")

        return response

    def _track(self, request):
        session_key = request.session.session_key

        # Token/JWT-authenticated requests don't own a Django session.
        # Creating one here would never set a cookie on the response —
        # SessionMiddleware.process_response runs *after* us in the response
        # chain, but only persists sessions that existed before the view ran.
        # The result would be an orphan django_session row plus a fresh
        # user_session row on every API call, bloating both tables and giving
        # _flush_django_sessions_for_user more haystack to search through.
        if not session_key:
            return

        now = timezone.now()
        # Mirror Django's authoritative session expiry rather than computing
        # our own. Keeps SESSION_SAVE_EVERY_REQUEST / sliding-vs-fixed expiry
        # policy consistent between django_session.expire_date and
        # user_session.expires_at — otherwise the two drift and "session is
        # open" answers depend on which table you ask.
        expires_at = request.session.get_expiry_date()

        defaults = {
            "user": request.user,
            "created_at": now,
            "last_activity_at": now,
            "expires_at": expires_at,
        }

        try:
            session, created = UserSession.objects.get_or_create(
                sid=session_key,
                defaults=defaults,
            )
        except IntegrityError:
            session = UserSession.objects.filter(sid=session_key).first()
            if session is None:
                raise
            created = False

        if created:
            return

        # SECURITY: never resurrect a row that was intentionally terminated.
        # auth_service._terminate_all_sessions sets revoked_at/ended_at on
        # password reset and other "the account may be compromised" flows.
        # Receiving a further authenticated write on the same sid means
        # either a race against the django_session flush or a leaked cookie
        # that survived the flush (e.g. _safe_decode silently dropped it).
        # Clearing the flags would launder the security signal that the rest
        # of the system worked to establish, so instead: log it, and flush
        # the Django session so the next request from this client lands as
        # AnonymousUser.
        if session.revoked_at is not None or session.ended_at is not None:
            logger.warning(
                "session_tracking.use_of_terminated_session",
                extra={
                    "user_id": request.user.id,
                    "sid": session_key,
                    "revoked_at": (
                        session.revoked_at.isoformat() if session.revoked_at else None
                    ),
                    "ended_at": (
                        session.ended_at.isoformat() if session.ended_at else None
                    ),
                },
            )
            request.session.flush()
            return

        update_fields = ["last_activity_at", "expires_at"]
        session.last_activity_at = now
        session.expires_at = expires_at

        if session.user_id != request.user.id:
            session.user = request.user
            update_fields.append("user")

        session.save(update_fields=update_fields)
