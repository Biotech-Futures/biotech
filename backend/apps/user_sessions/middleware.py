# apps/user_sessions/middleware.py
from datetime import timedelta

from django.conf import settings
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

        # Track authenticated requests
        if request.user.is_authenticated:
            now = timezone.now()
            sid = request.COOKIES.get("sid")
            session = None
            if sid:
                session = UserSession.objects.filter(
                    sid=sid,
                    user=request.user,
                    revoked_at__isnull=True,
                    ended_at__isnull=True,
                ).first()

            if session is None:
                session = UserSession.objects.create(
                    user=request.user,
                    created_at=now,
                    last_activity_at=now,
                    expires_at=now + timedelta(seconds=getattr(settings, "SESSION_COOKIE_AGE", 86400)),
                )
            else:
                session.last_activity_at = now
                session.expires_at = now + timedelta(seconds=getattr(settings, "SESSION_COOKIE_AGE", 86400))
                session.save(update_fields=["last_activity_at", "expires_at"])

            response.set_cookie(
                "sid",
                session.sid,
                max_age=getattr(settings, "SESSION_COOKIE_AGE", 86400),
                httponly=True,
                secure=getattr(settings, "SESSION_COOKIE_SECURE", False),
                samesite=getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"),
            )

        return response
