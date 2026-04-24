# apps/user_sessions/middleware.py
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from .models import UserSession


class SessionTrackingMiddleware:
    """
    Middleware to track user sessions in the Sessions model for analytics.
    Records authenticated requests to track user activity.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Track authenticated requests using Django's native session key
        if request.user.is_authenticated:
            if not request.session.session_key:
                request.session.create()

            now = timezone.now()
            session_key = request.session.session_key
            expires_at = now + timedelta(seconds=getattr(settings, "SESSION_COOKIE_AGE", 86400))

            defaults = {
                "user": request.user,
                "created_at": now,
                "last_activity_at": now,
                "expires_at": expires_at,
            }

            # sid is unique in the database, so always reconcile against that key
            # and tolerate a concurrent insert from another request.
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

            if not created:
                update_fields = ["last_activity_at", "expires_at"]
                session.last_activity_at = now
                session.expires_at = expires_at

                if session.user_id != request.user.id:
                    session.user = request.user
                    update_fields.append("user")

                if session.ended_at is not None:
                    session.ended_at = None
                    update_fields.append("ended_at")

                if session.revoked_at is not None:
                    session.revoked_at = None
                    update_fields.append("revoked_at")

                session.save(update_fields=update_fields)

        return response
