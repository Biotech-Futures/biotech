from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from apps.users.models import User
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import mailtrap as mt
from .models import LoginToken


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
        from django.conf import settings
        base_redirect = getattr(settings, 'MAGIC_LINK_REDIRECT_URL', 'http://localhost:5173/auth/callback')

    # edbert: Build magic link that points to backend magic endpoint with email and code
    magic_link = f"http://localhost:8000/services/magic/?email={email}&code={token}"

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
        from_email="noreply@biotechfutures.org",
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