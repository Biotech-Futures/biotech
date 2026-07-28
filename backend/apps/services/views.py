import logging
import time
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
from urllib.parse import urlencode, urlparse
from django.conf import settings
from . import auth_service
from apps.users.models import User
from apps.common.rbac import is_admin
from apps.common.pii import email_log_tag
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
    UserNotFound,
    WeakPassword,
)

logger = logging.getLogger(__name__)

# --- Login code send rate limits -------------------------------------------
LOGIN_SEND_PER_EMAIL_LIMIT = 5
LOGIN_SEND_PER_IP_LIMIT = 20
LOGIN_SEND_WINDOW_SECONDS = 900  # 15 min
# Minimum gap between two sends for the same address. The fixed windows above cap
# abuse; this stops an impatient user from stacking up codes they can't tell apart.
LOGIN_SEND_MIN_INTERVAL_SECONDS = 60

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
        # Stored emails are lowercase, so normalizing here keeps the throttle keys
        # from splitting on case — otherwise the cooldown is bypassed by shifting
        # one letter.
        email = (request.data.get("email") or "").strip().lower()
        redirect_url = request.data.get("redirect_url")
        if not email:
            raise EmailRequired()

        ip = _client_ip(request)
        _check_login_send_throttle(email, ip)

        # Cache-keyed on the submitted address and claimed before any user lookup,
        # so a cooled-down known email is indistinguishable from an unknown one.
        retry_after = _claim_min_interval(
            _login_send_cooldown_key(email), LOGIN_SEND_MIN_INTERVAL_SECONDS
        )
        if retry_after:
            raise LoginSendRateLimited(retry_after=retry_after)

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
        email = (request.data.get("email") or "").strip().lower()
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
                "verify_login_code: rate limit hit email_tag=%s ip=%s attempts=%s ip_attempts=%s",
                email_log_tag(email), ip, attempts, ip_attempts,
            )
            raise TooManyFailedAttempts()

        valid = auth_service.verify_login_code(email, code)
        if not valid:
            cache.set(cache_key, attempts + 1, OTP_ATTEMPT_WINDOW_SECONDS)
            cache.set(ip_key, ip_attempts + 1, OTP_ATTEMPT_WINDOW_SECONDS)
            logger.warning(
                "verify_login_code: invalid code email_tag=%s ip=%s attempt=%s",
                email_log_tag(email), ip, attempts + 1,
            )
            raise InvalidOrExpiredCode()

        # iexact no longer maps to the unique index, so .get() could raise
        # MultipleObjectsReturned on legacy mixed-case rows.
        user = User.objects.filter(email__iexact=email).order_by('pk').first()
        if user is None:
            raise InvalidOrExpiredCode()

        if user.account_status in User.INACTIVE_LOGIN_STATUSES:
            raise AccountInactive()

        login(request, user)
        cache.delete(cache_key)
        cache.delete(ip_key)

        # Only failures were logged before, so a code consumed by anything other
        # than the student left no trace at all.
        logger.info(
            "verify_login_code: session opened email_tag=%s ip=%s",
            email_log_tag(email), ip,
        )

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
                # The user app routes on the hash, so dropping the fragment would strand
                # ?error= at the site root where its router never sees it.
                fragment = f"#{parsed.fragment}" if parsed.fragment else ""
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}{fragment}"
        # Errors often precede knowing who the user is, so default to the app almost
        # everyone signs in through rather than the admin portal.
        return settings.MAGIC_LINK_REDIRECT_URL

    @extend_schema(
        responses={
            302: AuthMessageSerializer,
            400: AuthMessageSerializer,
            403: AuthMessageSerializer,
        },
    )
    def get(self, request):
        """Hand the code to the frontend. Deliberately consumes nothing.

        Mail security products (Outlook Safe Links, Defender, spam filters, link
        previewers) fetch every URL in an email. This endpoint used to verify the
        code, burn it and open a session on that GET, so the scanner logged in and
        the student got "invalid or expired code" seconds later. A GET must stay
        side-effect free: the token is only consumed by the POST behind the
        "Continue" button on the callback screen.
        """
        email = (request.GET.get("email") or "").strip().lower()
        code = (request.GET.get("code") or "").strip()
        redirect_url_param = request.GET.get("redirect_url")
        callback_base = self._safe_callback_base(redirect_url_param)

        if not email or not code:
            return redirect(f"{callback_base}?error=invalid_or_expired_code")

        # No validation, no attempt-counter bump, no login. Bumping here would let
        # a scanner hitting a stale link burn the student's 5 verify attempts.
        logger.info(
            "magic_login: handoff email_tag=%s ip=%s",
            email_log_tag(email), _client_ip(request),
        )

        params = urlencode({"email": email, "code": code})
        separator = "&" if "?" in callback_base else "?"
        return redirect(f"{callback_base}{separator}{params}")


# --- password reset --------------------------------------------------------

# Rate-limit budgets. Keep stricter than login OTP since reset is higher-stakes.
PWRESET_REQUEST_PER_EMAIL_LIMIT = 3
PWRESET_REQUEST_PER_IP_LIMIT = 10
PWRESET_REQUEST_WINDOW_SECONDS = 900       # 15 min
PWRESET_REQUEST_MIN_INTERVAL_SECONDS = 60  # same anti-stacking gap as login send
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

        retry_after = _claim_min_interval(
            _pwreset_request_cooldown_key(email), PWRESET_REQUEST_MIN_INTERVAL_SECONDS
        )
        if retry_after:
            raise PasswordResetRateLimited(retry_after=retry_after)

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


# --- shared throttle primitives ---------------------------------------------

def _deadline_key(key: str) -> str:
    return f"{key}:until"


def _bump_window(key: str, window_seconds: int) -> None:
    """Increment a fixed-window counter without the get-then-set race.

    ``cache.add`` is SETNX on Redis, so two concurrent double-submits can't both
    reset the counter to 1 and hand the caller a free extra send.
    """
    if cache.add(key, 1, window_seconds):
        cache.set(_deadline_key(key), time.time() + window_seconds, window_seconds)
        return

    try:
        cache.incr(key)
    except ValueError:  # expired between the add and the incr
        cache.set(key, 1, window_seconds)
        cache.set(_deadline_key(key), time.time() + window_seconds, window_seconds)
        return

    # Django's Redis incr is EXISTS-then-INCRBY, not atomic: if the key lapses in
    # that gap, INCRBY recreates it with NO expiry and the counter would then
    # 429 this address forever. The deadline key is the tell — restore both.
    if cache.get(_deadline_key(key)) is None:
        cache.set(key, 1, window_seconds)
        cache.set(_deadline_key(key), time.time() + window_seconds, window_seconds)


def _window_retry_after(key: str, window_seconds: int) -> int:
    deadline = cache.get(_deadline_key(key))
    if not deadline:
        return window_seconds
    return max(1, int(deadline - time.time()))


def _claim_min_interval(key: str, seconds: int) -> int:
    """Claim the next send slot. Returns 0 when claimed, else seconds remaining.

    A rejected caller must not re-arm the window, or hammering the button would
    lock them out permanently — ``cache.add`` gives that for free.
    """
    now = time.time()
    if cache.add(key, now + seconds, seconds):
        return 0
    remaining = int((cache.get(key) or now) - now)
    return max(1, min(remaining, seconds))


def _email_request_key(email: str) -> str:
    return f"pwreset_req_email:{email}"


def _ip_request_key(ip: str) -> str:
    return f"pwreset_req_ip:{ip}"


def _confirm_attempt_key(token: str) -> str:
    return f"pwreset_confirm:{token}"


def _confirm_ip_key(ip: str) -> str:
    return f"pwreset_confirm_ip:{ip}"


def _check_request_throttle(email: str, ip: str) -> None:
    e_key, i_key = _email_request_key(email), _ip_request_key(ip)
    if cache.get(e_key, 0) >= PWRESET_REQUEST_PER_EMAIL_LIMIT:
        raise PasswordResetRateLimited(
            retry_after=_window_retry_after(e_key, PWRESET_REQUEST_WINDOW_SECONDS)
        )
    if cache.get(i_key, 0) >= PWRESET_REQUEST_PER_IP_LIMIT:
        raise PasswordResetRateLimited(
            retry_after=_window_retry_after(i_key, PWRESET_REQUEST_WINDOW_SECONDS)
        )


def _bump_request_counters(email: str, ip: str) -> None:
    _bump_window(_email_request_key(email), PWRESET_REQUEST_WINDOW_SECONDS)
    _bump_window(_ip_request_key(ip), PWRESET_REQUEST_WINDOW_SECONDS)


def _check_login_send_throttle(email: str, ip: str) -> None:
    e_key, i_key = _login_send_email_key(email), _login_send_ip_key(ip)
    if cache.get(e_key, 0) >= LOGIN_SEND_PER_EMAIL_LIMIT:
        raise LoginSendRateLimited(
            retry_after=_window_retry_after(e_key, LOGIN_SEND_WINDOW_SECONDS)
        )
    if cache.get(i_key, 0) >= LOGIN_SEND_PER_IP_LIMIT:
        raise LoginSendRateLimited(
            retry_after=_window_retry_after(i_key, LOGIN_SEND_WINDOW_SECONDS)
        )


def _bump_login_send_counters(email: str, ip: str) -> None:
    _bump_window(_login_send_email_key(email), LOGIN_SEND_WINDOW_SECONDS)
    _bump_window(_login_send_ip_key(ip), LOGIN_SEND_WINDOW_SECONDS)


def _login_send_email_key(email: str) -> str:
    return f"login_send_email:{email}"


def _login_send_ip_key(ip: str) -> str:
    return f"login_send_ip:{ip}"


def _login_send_cooldown_key(email: str) -> str:
    return f"login_send_cooldown:{email}"


def _pwreset_request_cooldown_key(email: str) -> str:
    return f"pwreset_req_cooldown:{email}"


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


