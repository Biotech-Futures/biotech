import logging
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.user_sessions.models import UserSession
from apps.users.models import User
from config.errors import InvalidOrExpiredResetToken, WeakPassword
from .models import LoginToken, PasswordResetToken

logger = logging.getLogger(__name__)

# Statuses that block a password reset (silent no-op). Onboarding stays separate.
PASSWORD_RESET_BLOCKED_STATUSES = {'invited', 'pending', 'suspended', 'deactivated'}


def send_login_code(email: str, redirect_url: str = None) -> bool:
    """Send OTP login code to user's email using our custom LoginToken"""
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return False

    # Create a new login token for this user
    login_token = LoginToken.create_for_user(user, expiry_minutes=10)
    token = login_token.token

    # edbert: Use provided redirect_url from frontend, fallback to settings or default
    if redirect_url:
        base_redirect = redirect_url
    else:
        # edbert: Fallback to settings configuration
        base_redirect = getattr(settings, 'MAGIC_LINK_REDIRECT_URL', 'http://localhost:5173/auth/callback')

    # edbert: Build magic link that points to backend magic endpoint with email and code
    backend_url = getattr(settings, 'BACKEND_URL', 'http://localhost:8000')
    query_params = {
        'email': email,
        'code': token,
        'redirect_url': base_redirect
    }
    magic_link = f"{backend_url}/services/magic/?{urlencode(query_params)}"

    # Render HTML email
    html_content = render_to_string("emails/login.html", {
        "MAGIC_LINK": magic_link,
        "OTP_CODE": token,
        "EXPIRY_MINUTES": 10,
        "First_Name": user.first_name,
    })

    # Plaintext fallback
    text_content = f"Use this link to log in: {magic_link}\nOr enter code: {token} (expires in 10 mins)."

    msg = EmailMultiAlternatives(
        subject="BIOTech Futures: Log in securely",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    return True


def verify_login_code(email: str, code: str) -> bool:
    """Verify OTP login code using our custom LoginToken"""
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return False

    # Verify the token using our LoginToken model
    login_token = LoginToken.verify_token_for_user(user, code)
    return login_token is not None


# --- password reset --------------------------------------------------------

def send_password_reset(email: str, *, ip: str = None, user_agent: str = "") -> None:
    """Issue a reset token and email it. Silent no-op for unknown / non-ACTIVE accounts."""
    user = _resolve_resettable_user(email)
    if user is None:
        return

    expiry = getattr(settings, "PASSWORD_RESET_TOKEN_EXPIRY_MINUTES", 30)
    reset = PasswordResetToken.create_for_user(
        user, expiry_minutes=expiry, ip=ip, user_agent=user_agent,
    )
    _send_reset_email(user, reset.token, expiry)


def confirm_password_reset(*, token: str, new_password: str) -> User:
    """Verify token, set new password, invalidate other tokens, terminate sessions, notify."""
    reset_row = PasswordResetToken.consume(token)
    if reset_row is None:
        raise InvalidOrExpiredResetToken()

    user = reset_row.user
    _validate_or_raise(new_password, user)

    user.set_password(new_password)
    user.save(update_fields=['password'])

    _invalidate_outstanding_tokens(user)
    _terminate_all_sessions(user)
    _send_password_changed_notification(user, ip=reset_row.requested_ip)
    return user


# --- helpers ---------------------------------------------------------------

def _resolve_resettable_user(email: str):
    """Return the User if eligible for reset, else None (and log the skip reason)."""
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        # never reveal whether the email exists
        logger.info("password_reset.skip", extra={"reason": "no_user"})
        return None

    if user.account_status in PASSWORD_RESET_BLOCKED_STATUSES:
        logger.info("password_reset.skip", extra={
            "reason": "blocked_status",
            "user_id": user.id,
            "status": user.account_status,
        })
        return None
    return user


def _send_reset_email(user, token: str, expiry_minutes: int) -> None:
    """Best-effort send. Swallows exceptions so SMTP failure does not turn a
    known-email request into a 500 — that would let an attacker enumerate users
    by comparing responses against the silent 200 returned for unknown emails.
    """
    base = getattr(
        settings,
        "PASSWORD_RESET_REDIRECT_URL",
        "http://localhost:5173/auth/reset-password",
    )
    reset_link = f"{base}?token={token}"

    ctx = {
        "RESET_PASSWORD_LINK": reset_link,
        "EXPIRY_MINUTES": expiry_minutes,
        "First_Name": user.first_name,
    }
    try:
        html_content = render_to_string("emails/password_reset.html", ctx)
        text_content = (
            f"Update your BIOTech Futures password: {reset_link}\n"
            f"This link expires in {expiry_minutes} minutes.\n"
            f"If you didn't request this, ignore this email."
        )

        msg = EmailMultiAlternatives(
            subject="BIOTech Futures: Update your password",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
    except Exception:
        logger.exception("password_reset.send_failed", extra={"user_id": user.id})


def _validate_or_raise(new_password: str, user) -> None:
    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        # token is already consumed; cheap to request another, prevents replay
        raise WeakPassword(exc.messages)


def _invalidate_outstanding_tokens(user) -> None:
    """Burn other reset tokens AND active login OTPs after a successful reset."""
    now = timezone.now()
    PasswordResetToken.objects.filter(user=user, used=False).update(used=True, used_at=now)
    LoginToken.objects.filter(user=user, used=False).update(used=True)


def _terminate_all_sessions(user) -> None:
    """Log the user out everywhere — assume reset implies the account may be compromised."""
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


def _send_password_changed_notification(user, *, ip: str = None) -> None:
    """Best-effort 'your password was changed' email. Never raises — password is already updated."""
    ctx = {
        "First_Name": user.first_name,
        "CHANGED_AT": timezone.now(),
        "REQUEST_IP": ip or "unknown",
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
    }
    try:
        html_content = render_to_string("emails/password_changed.html", ctx)
        text_content = (
            f"Hi {user.first_name or 'there'},\n\n"
            f"Your BIOTech Futures password was just changed.\n"
            f"If this wasn't you, contact {settings.SUPPORT_EMAIL} immediately."
        )
        msg = EmailMultiAlternatives(
            subject="BIOTech Futures: Your password was changed",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
    except Exception:
        logger.exception("password_reset.notification_failed", extra={"user_id": user.id})