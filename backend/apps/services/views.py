from django.shortcuts import redirect
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
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
from apps.user_sessions.models import UserSession
from config.errors import (
    AccountInactive,
    EmailAndCodeRequired,
    EmailRequired,
    InvalidOrExpiredCode,
    InvalidOrExpiredResetToken,
    PasswordResetRateLimited,
    TooManyFailedAttempts,
    UserNotFound,
    WeakPassword,
    error_json_response,
)


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
            404: AuthMessageSerializer,
        },
    )
    def post(self, request):
        email = request.data.get("email")
        # edbert: Added redirect_url parameter to support frontend callback
        redirect_url = request.data.get("redirect_url")
        if not email:
            raise EmailRequired()

        # edbert: Pass redirect_url to auth service
        sent = auth_service.send_login_code(email, redirect_url)
        if sent:
            return Response({"message": "Login code sent"}, status=status.HTTP_200_OK)
        raise UserNotFound()


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

        cache_key = f"otp_attempts:{email}"
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            raise TooManyFailedAttempts()

        valid = auth_service.verify_login_code(email, code)
        if not valid:
            cache.set(cache_key, attempts + 1, 300)
            raise InvalidOrExpiredCode()

        # At this point user is authenticated
        user = User.objects.get(email=email)

        if user.account_status in ['suspended', 'deactivated']:
            raise AccountInactive()
            
        login(request, user)  # Creates session cookie
        cache.delete(cache_key)

        return Response(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            },
            status=status.HTTP_200_OK,
        )

def magic_login(request):
    """Handle magic link authentication with Django sessions"""
    email = request.GET.get("email")
    code = request.GET.get("code")

    if not email or not code:
        return error_json_response(EmailAndCodeRequired)

    if not auth_service.verify_login_code(email, code):
        return error_json_response(InvalidOrExpiredCode)

    # User is authenticated
    user = User.objects.get(email=email)

    if user.account_status in ['suspended', 'deactivated']:
        return error_json_response(AccountInactive)
        
    login(request, user)  # Creates session cookie

    # Redirect to frontend - securely validate domain
    redirect_url_param = request.GET.get("redirect_url")
    frontend_callback = getattr(settings, 'MAGIC_LINK_REDIRECT_URL', 'http://localhost:5173/#/auth/callback')
    
    if redirect_url_param:
        parsed_url = urlparse(redirect_url_param)
        allowed_domains = ['localhost', '127.0.0.1', 'biotechfutures.org']
        if parsed_url.hostname in allowed_domains:
            frontend_callback = redirect_url_param

    redirect_url = f"{frontend_callback}?success=true&email={user.email}"

    return redirect(redirect_url)


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
    # X-Forwarded-For only safe when terminated by a trusted proxy (Azure Front Door / App Service)
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def _check_request_throttle(email: str, ip: str) -> None:
    if cache.get(_email_request_key(email), 0) >= PWRESET_REQUEST_PER_EMAIL_LIMIT:
        raise PasswordResetRateLimited()
    if cache.get(_ip_request_key(ip), 0) >= PWRESET_REQUEST_PER_IP_LIMIT:
        raise PasswordResetRateLimited()


def _bump_request_counters(email: str, ip: str) -> None:
    e_key, i_key = _email_request_key(email), _ip_request_key(ip)
    cache.set(e_key, cache.get(e_key, 0) + 1, PWRESET_REQUEST_WINDOW_SECONDS)
    cache.set(i_key, cache.get(i_key, 0) + 1, PWRESET_REQUEST_WINDOW_SECONDS)


def _email_request_key(email: str) -> str:
    return f"pwreset_req_email:{email}"


def _ip_request_key(ip: str) -> str:
    return f"pwreset_req_ip:{ip}"


def _confirm_attempt_key(token: str) -> str:
    return f"pwreset_confirm:{token}"


def _confirm_ip_key(ip: str) -> str:
    return f"pwreset_confirm_ip:{ip}"


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


@require_http_methods(["GET"])
def test_email_template(request):
    """
    Test view to preview the login email template in browser
    Access at: /services/test-email/
    """
    # Sample data for template testing
    context = {
        "MAGIC_LINK": "https://biotechfutures.org/auth/magic?email=test@example.com&code=123456",
        "OTP_CODE": "123456",
        "EXPIRY_MINUTES": 10,
        "First_Name": "John"
    }

    # Render the email template
    try:
        html_content = render_to_string("emails/login.html", context)
        return HttpResponse(html_content, content_type="text/html")
    except Exception as e:
        return HttpResponse(
            f"<h1>Template Error</h1><p>Error rendering template: {str(e)}</p>",
            content_type="text/html"
        )

#to be deleted.
@require_http_methods(["GET"])
def test_email_preview(request):
    """
    Preview email template with customizable parameters
    Access at: /services/test-email-preview/
    """
    # Get parameters from URL or use defaults
    first_name = request.GET.get('first_name', 'John')
    email = request.GET.get('email', 'test@example.com')
    otp_code = request.GET.get('otp_code', '123456')
    expiry_minutes = request.GET.get('expiry_minutes', '10')

    context = {
        "MAGIC_LINK": f"https://biotechfutures.org/auth/magic?email={email}&code={otp_code}",
        "OTP_CODE": otp_code,
        "EXPIRY_MINUTES": expiry_minutes,
        "First_Name": first_name
    }

    try:
        html_content = render_to_string("emails/login.html", context)

        # Wrap in a preview container
        preview_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Email Template Preview</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .preview-header {{ background: #f0f0f0; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
                .preview-controls {{ margin-bottom: 20px; }}
                .preview-controls input {{ margin: 5px; padding: 8px; }}
                .preview-controls button {{ background: #007cba; color: white; padding: 8px 15px; border: none; border-radius: 3px; cursor: pointer; }}
                .email-preview {{ border: 1px solid #ddd; padding: 0; }}
            </style>
        </head>
        <body>
            <div class="preview-header">
                <h1>🧪 Email Template Preview</h1>
                <p>Preview of login.html template with current variables</p>
            </div>

            <div class="preview-controls">
                <form method="get">
                    <input type="text" name="first_name" placeholder="First Name" value="{first_name}">
                    <input type="email" name="email" placeholder="Email" value="{email}">
                    <input type="text" name="otp_code" placeholder="OTP Code" value="{otp_code}" maxlength="6">
                    <input type="number" name="expiry_minutes" placeholder="Expiry Minutes" value="{expiry_minutes}">
                    <button type="submit">Update Preview</button>
                </form>
            </div>

            <div class="email-preview">
                {html_content}
            </div>
        </body>
        </html>
        """

        return HttpResponse(preview_html, content_type="text/html")

    except Exception as e:
        return HttpResponse(
            f"<h1>Template Error</h1><p>Error rendering template: {str(e)}</p>",
            content_type="text/html"
        )
