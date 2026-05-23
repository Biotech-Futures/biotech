import logging
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import login, logout
from rest_framework import serializers
from drf_spectacular.utils import extend_schema
from django.core.cache import cache
from urllib.parse import urlparse
from django.conf import settings
from . import auth_service
from apps.users.models import User
from apps.users.utils.admin_scope import is_operational_admin
from apps.user_sessions.models import UserSession
from config.errors import (
    AccountInactive,
    EmailAndCodeRequired,
    EmailRequired,
    InvalidOrExpiredCode,
    InvalidOrExpiredResetToken,
    LoginSendRateLimited,
    PasswordResetRateLimited,
    TooManyFailedAttempts,
    TrackArchived,
    UserNotFound,
    WeakPassword,
)

logger = logging.getLogger(__name__)

# --- Login code send rate limits -------------------------------------------
LOGIN_SEND_PER_EMAIL_LIMIT = 5
LOGIN_SEND_PER_IP_LIMIT = 20
LOGIN_SEND_WINDOW_SECONDS = 900  # 15 min

# --- OTP verify rate limits -------------------------------------------------
OTP_ATTEMPT_LIMIT = 5
OTP_ATTEMPT_WINDOW_SECONDS = 300  # 5 min
OTP_IP_ATTEMPT_MULTIPLIER = 4     # IP cap = 20

@ensure_csrf_cookie
@require_http_methods(["GET"])
def csrf_token_view(request):
    """Return the CSRF token in the response body so cross-origin SPAs that
    cannot read cookies via document.cookie can still attach X-CSRFToken
    on subsequent unsafe requests."""
    return JsonResponse({"csrfToken": get_token(request)})


class SendLoginCodeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    redirect_url = serializers.CharField(required=False, allow_blank=True)


class VerifyLoginCodeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField()


class AuthMessageSerializer(serializers.Serializer):
    message = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class VerifiedUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()


class VerifyLoginCodeResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    user = VerifiedUserSerializer()


class SendLoginCodeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=SendLoginCodeRequestSerializer,
        responses={
            200: AuthMessageSerializer,
            400: AuthMessageSerializer,
            429: AuthMessageSerializer,
        },
    )
    def post(self, request):
        # Anti-enumeration: this endpoint always returns 200 for any well-formed
        # email so an attacker cannot tell registered emails apart from unknown
        # ones. 400 = malformed input, 429 = rate-limited. Never 404.
        email = request.data.get("email")
        redirect_url = request.data.get("redirect_url")
        if not email:
            raise EmailRequired()

        ip = _client_ip(request)
        _check_login_send_throttle(email, ip)
        _bump_login_send_counters(email, ip)

        sent = auth_service.send_login_code(email, redirect_url)

        if not sent:
            logger.warning(
                "send_login_code: no user found — enumeration attempt suppressed ip=%s",
                ip,
            )

        return Response(
            {"message": "If an account exists for that email, a login code has been sent."},
            status=status.HTTP_200_OK,
        )


class VerifyLoginCodeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=VerifyLoginCodeRequestSerializer,
        responses={
            200: VerifyLoginCodeResponseSerializer,
            400: AuthMessageSerializer,
        },
    )
    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")
        if not email or not code:
            raise EmailAndCodeRequired()

        ip = _client_ip(request)
        cache_key = f"otp_attempts:{email}"
        ip_key = f"otp_attempts_ip:{ip}"

        attempts = cache.get(cache_key, 0)
        ip_attempts = cache.get(ip_key, 0)

        if attempts >= OTP_ATTEMPT_LIMIT or ip_attempts >= OTP_ATTEMPT_LIMIT * OTP_IP_ATTEMPT_MULTIPLIER:
            logger.warning(
                "verify_login_code: rate limit hit email=%s ip=%s attempts=%s ip_attempts=%s",
                email, ip, attempts, ip_attempts,
            )
            raise TooManyFailedAttempts()

        valid = auth_service.verify_login_code(email, code)
        if not valid:
            cache.set(cache_key, attempts + 1, OTP_ATTEMPT_WINDOW_SECONDS)
            cache.set(ip_key, ip_attempts + 1, OTP_ATTEMPT_WINDOW_SECONDS)
            logger.warning(
                "verify_login_code: invalid code email=%s ip=%s attempt=%s",
                email, ip, attempts + 1,
            )
            raise InvalidOrExpiredCode()

        user = User.objects.select_related("track").get(email=email)

        if user.account_status in ['suspended', 'deactivated']:
            raise AccountInactive()

        if user.track and user.track.is_archived:
            logger.warning(
                "verify_login_code: blocked archived-track login email=%s track_id=%s",
                email, user.track_id,
            )
            raise TrackArchived()

        login(request, user)
        cache.delete(cache_key)
        cache.delete(ip_key)

        return Response(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                # login() rotates the CSRF token; surface the new one so the SPA
                # doesn't keep using the pre-login value on subsequent writes.
                "csrfToken": get_token(request),
            },
            status=status.HTTP_200_OK,
        )

class MagicLoginView(APIView):
    """Handle magic link authentication. Both success and error return a 302
    redirect to the frontend callback so users always see a proper UI."""
    permission_classes = [AllowAny]
    authentication_classes = []

    _ALLOWED_REDIRECT_DOMAINS = [
        'localhost',
        '127.0.0.1',
        'biotechfutures.org',
        'mentoring.biotechfutures.org',
        'mentoringadmin.biotechfutures.org',
    ]

    def _safe_callback_base(self, redirect_url_param):
        """Return the frontend callback base URL, stripped of any query string."""
        if redirect_url_param:
            parsed = urlparse(redirect_url_param)
            if parsed.hostname in self._ALLOWED_REDIRECT_DOMAINS:
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return settings.ADMIN_MAGIC_LINK_REDIRECT_URL

    @extend_schema(
        responses={
            302: AuthMessageSerializer,
            400: AuthMessageSerializer,
            403: AuthMessageSerializer,
        },
    )
    def get(self, request):
        email = request.GET.get("email")
        code = request.GET.get("code")
        redirect_url_param = request.GET.get("redirect_url")
        callback_base = self._safe_callback_base(redirect_url_param)

        if not email or not code:
            return redirect(f"{callback_base}?error=invalid_or_expired_code")

        ip = _client_ip(request)
        cache_key = f"otp_attempts:{email}"
        ip_key = f"otp_attempts_ip:{ip}"

        attempts = cache.get(cache_key, 0)
        ip_attempts = cache.get(ip_key, 0)

        if attempts >= OTP_ATTEMPT_LIMIT or ip_attempts >= OTP_ATTEMPT_LIMIT * OTP_IP_ATTEMPT_MULTIPLIER:
            logger.warning(
                "magic_login: rate limit hit email=%s ip=%s attempts=%s ip_attempts=%s",
                email, ip, attempts, ip_attempts,
            )
            return redirect(f"{callback_base}?error=too_many_attempts")

        if not auth_service.verify_login_code(email, code):
            cache.set(cache_key, attempts + 1, OTP_ATTEMPT_WINDOW_SECONDS)
            cache.set(ip_key, ip_attempts + 1, OTP_ATTEMPT_WINDOW_SECONDS)
            logger.warning(
                "magic_login: invalid code email=%s ip=%s attempt=%s",
                email, ip, attempts + 1,
            )
            return redirect(f"{callback_base}?error=invalid_or_expired_code")

        try:
            user = User.objects.select_related("track").get(email=email)
        except User.DoesNotExist:
            return redirect(f"{callback_base}?error=invalid_or_expired_code")

        if user.account_status in ['suspended', 'deactivated']:
            return redirect(f"{callback_base}?error=account_inactive")

        if user.track and user.track.is_archived:
            logger.warning(
                "magic_login: blocked archived-track login email=%s track_id=%s",
                email, user.track_id,
            )
            return redirect(f"{callback_base}?error=track_archived")

        login(request, user)
        cache.delete(cache_key)
        cache.delete(ip_key)

        # Admins land on the admin portal; everyone else on the user app.
        if is_operational_admin(user):
            frontend_callback = settings.ADMIN_MAGIC_LINK_REDIRECT_URL
        else:
            frontend_callback = settings.MAGIC_LINK_REDIRECT_URL

        if redirect_url_param:
            parsed_url = urlparse(redirect_url_param)
            if parsed_url.hostname in self._ALLOWED_REDIRECT_DOMAINS:
                frontend_callback = redirect_url_param

        return redirect(f"{frontend_callback}?success=true&email={user.email}")


# --- password reset --------------------------------------------------------

# Rate-limit budgets. Keep stricter than login OTP since reset is higher-stakes.
PWRESET_REQUEST_PER_EMAIL_LIMIT = 3
PWRESET_REQUEST_PER_IP_LIMIT = 10
PWRESET_REQUEST_WINDOW_SECONDS = 900       # 15 min
PWRESET_CONFIRM_ATTEMPT_LIMIT = 5          # per token — catches accidental retries
PWRESET_CONFIRM_PER_IP_LIMIT = 20          # per IP — caps brute force across many guessed tokens
PWRESET_CONFIRM_WINDOW_SECONDS = 900       # 15 min


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=64)
    new_password = serializers.CharField(write_only=True, max_length=256)


class PasswordResetRequestView(APIView):
    """POST /services/password-reset/request/ — always 200, never reveals if email exists."""
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: AuthMessageSerializer, 429: AuthMessageSerializer},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        ip = _client_ip(request)

        _check_request_throttle(email, ip)
        _bump_request_counters(email, ip)

        auth_service.send_password_reset(
            email,
            ip=ip,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return Response(
            {"message": "If an account exists for that email, a reset link has been sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """POST /services/password-reset/confirm/ — exchange token + new_password for a reset."""
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={
            200: AuthMessageSerializer,
            400: AuthMessageSerializer,
            429: AuthMessageSerializer,
        },
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        ip = _client_ip(request)
        attempt_key = _confirm_attempt_key(token)
        ip_key = _confirm_ip_key(ip)
        if cache.get(attempt_key, 0) >= PWRESET_CONFIRM_ATTEMPT_LIMIT:
            raise PasswordResetRateLimited()
        if cache.get(ip_key, 0) >= PWRESET_CONFIRM_PER_IP_LIMIT:
            raise PasswordResetRateLimited()

        try:
            auth_service.confirm_password_reset(token=token, new_password=new_password)
        except (InvalidOrExpiredResetToken, WeakPassword):
            cache.set(attempt_key, cache.get(attempt_key, 0) + 1, PWRESET_CONFIRM_WINDOW_SECONDS)
            cache.set(ip_key, cache.get(ip_key, 0) + 1, PWRESET_CONFIRM_WINDOW_SECONDS)
            raise

        cache.delete(attempt_key)
        return Response(
            {"message": "Password reset successful. Please log in with your new password."},
            status=status.HTTP_200_OK,
        )


def _client_ip(request) -> str:
    # X-Forwarded-For is attacker-controlled when the app is reachable directly.
    # Only honor it when the deployment terminates at a trusted proxy/CDN
    # (Azure Front Door / App Service ingress / ALB). Production opts in via
    # TRUST_FORWARDED_FOR=true; everywhere else we anchor rate-limit keys to
    # the real socket peer so an attacker can't fan out across spoofed IPs.
    if getattr(settings, "TRUST_FORWARDED_FOR", False):
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            return _strip_port(xff.split(",")[0])
    return _strip_port(request.META.get("REMOTE_ADDR", "") or "")


def _strip_port(addr: str) -> str:
    # Azure App Service forwards `IP:PORT` in X-Forwarded-For / REMOTE_ADDR;
    # GenericIPAddressField rejects the port suffix.
    addr = addr.strip()
    if not addr:
        return ""
    if addr.startswith("["):
        end = addr.find("]")
        return addr[1:end] if end != -1 else addr
    if addr.count(":") == 1:
        return addr.split(":", 1)[0]
    return addr


def _email_request_key(email: str) -> str:
    return f"pwreset_req_email:{email}"


def _ip_request_key(ip: str) -> str:
    return f"pwreset_req_ip:{ip}"


def _confirm_attempt_key(token: str) -> str:
    return f"pwreset_confirm:{token}"


def _confirm_ip_key(ip: str) -> str:
    return f"pwreset_confirm_ip:{ip}"


def _check_request_throttle(email: str, ip: str) -> None:
    if cache.get(_email_request_key(email), 0) >= PWRESET_REQUEST_PER_EMAIL_LIMIT:
        raise PasswordResetRateLimited()
    if cache.get(_ip_request_key(ip), 0) >= PWRESET_REQUEST_PER_IP_LIMIT:
        raise PasswordResetRateLimited()


def _bump_request_counters(email: str, ip: str) -> None:
    e_key, i_key = _email_request_key(email), _ip_request_key(ip)
    cache.set(e_key, cache.get(e_key, 0) + 1, PWRESET_REQUEST_WINDOW_SECONDS)
    cache.set(i_key, cache.get(i_key, 0) + 1, PWRESET_REQUEST_WINDOW_SECONDS)


def _check_login_send_throttle(email: str, ip: str) -> None:
    if cache.get(_login_send_email_key(email), 0) >= LOGIN_SEND_PER_EMAIL_LIMIT:
        raise LoginSendRateLimited()
    if cache.get(_login_send_ip_key(ip), 0) >= LOGIN_SEND_PER_IP_LIMIT:
        raise LoginSendRateLimited()


def _bump_login_send_counters(email: str, ip: str) -> None:
    e_key = _login_send_email_key(email)
    i_key = _login_send_ip_key(ip)
    cache.set(e_key, cache.get(e_key, 0) + 1, LOGIN_SEND_WINDOW_SECONDS)
    cache.set(i_key, cache.get(i_key, 0) + 1, LOGIN_SEND_WINDOW_SECONDS)


def _login_send_email_key(email: str) -> str:
    return f"login_send_email:{email}"


def _login_send_ip_key(ip: str) -> str:
    return f"login_send_ip:{ip}"


class LogoutView(APIView):
    """Logout endpoint - destroys Django session"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: AuthMessageSerializer},
    )
    def post(self, request):
        # Explicitly revoke parallel tracking sessions if they exist
        session_key = request.session.session_key
        if session_key:
            UserSession.objects.filter(sid=session_key).update(revoked_at=timezone.now())
            
        logout(request)  # Destroys native session
        
        response = Response({"message": "Successfully logged out"}, status=status.HTTP_200_OK)
        return response


