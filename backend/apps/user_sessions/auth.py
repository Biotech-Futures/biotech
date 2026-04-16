# apps/user_sessions/auth.py -> Issue 38
from rest_framework.authentication import BaseAuthentication
from django.utils import timezone

from .models import UserSession

class SessionIdAuthentication(BaseAuthentication):
    header = "X-Session-Id"

    def authenticate(self, request):
        sid = request.COOKIES.get("sid") or request.headers.get(self.header)
        if not sid:
            return None
        try:
            session = UserSession.objects.select_related("user").get(
                sid=sid,
                ended_at__isnull=True,
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
        except UserSession.DoesNotExist:
            return None
        session.last_activity_at = timezone.now()
        session.save(update_fields=["last_activity_at"])
        return (session.user, None)
