# apps/user_sessions/auth.py -> Issue 38
from rest_framework.authentication import BaseAuthentication
from .models import Sessions

class SessionIdAuthentication(BaseAuthentication):
    header = "X-Session-Id"

    def authenticate(self, request):
        sid = request.COOKIES.get("sid") or request.headers.get(self.header)
        if not sid:
            return None
        try:
            s = Sessions.objects.select_related("user").get(sid=sid, isloggedin=True)
        except Sessions.DoesNotExist:
            return None
        return (s.user, None)
