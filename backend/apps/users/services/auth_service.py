import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from apps.users.models import Users, LoginCode
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

TEMPORARY_VALID_EMAILS = { #until migrations are made
    "alice@example.com": {
        "id": 1,
        "first_name": "Alice",
        "last_name": "Example",
        "email": "alice@example.com",
    },
    "bob@example.com": {
        "id": 2,
        "first_name": "Bob",
        "last_name": "Example",
        "email": "bob@example.com",
    },
}

# apps/users/services/auth_service.py

# Temporary in-memory fake users (email → user dict)
FAKE_USERS = {
    "alice@example.com": {
        "id": 1,
        "first_name": "Alice",
        "last_name": "Example",
        "email": "alice@example.com",
    },
    "bob@example.com": {
        "id": 2,
        "first_name": "Bob",
        "last_name": "Example",
        "email": "bob@example.com",
    },
}

def send_login_code(email: str) -> bool:
    # --- TEMP: fake user lookup ---
    user = FAKE_USERS.get(email)
    if not user:
        return False

    code = f"{random.randint(100000, 999999)}"
    expiry_minutes = 10

    # Store OTP in memory (skip DB)
    FAKE_USERS[email]["otp"] = code

    # Build magic link
    magic_link = f"https://biotechfutures.org/auth/magic?email={email}&code={code}"

    # Render template
    html_content = render_to_string("emails/login.html", {
        "MAGIC_LINK": magic_link,
        "OTP_CODE": code,
        "EXPIRY_MINUTES": expiry_minutes,
        "First_Name": user["first_name"],
    })

    text_content = f"Use this link to log in: {magic_link}\nOr enter code: {code} (expires in {expiry_minutes} mins)."

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
    user = FAKE_USERS.get(email)
    if not user:
        return False

    stored = user.get("otp")
    return stored == code

"""
def send_login_code(email: str) -> bool:
    try:
        user = Users.objects.get(email=email)
    except Users.DoesNotExist:
        return False

    code = f"{random.randint(100000, 999999)}"
    expiry_minutes = 10
    expiry = timezone.now() + timedelta(minutes=expiry_minutes)

    LoginCode.objects.create(user=user, code=code, expires_at=expiry)

    # Build magic link
    magic_link = f"https://biotechfutures.org/auth/magic?email={email}&code={code}"

    # Render HTML email (store your HTML template as templates/emails/login.html)
    html_content = render_to_string("emails/login.html", {
        "MAGIC_LINK": magic_link,
        "OTP_CODE": code,
        "EXPIRY_MINUTES": expiry_minutes,
        "First_Name": user.first_name,
    })

    # Plaintext fallback
    text_content = f"Use this link to log in: {magic_link}\nOr enter code: {code} (expires in {expiry_minutes} mins)."

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
    try:
        user = Users.objects.get(email=email)
        login_code = LoginCode.objects.filter(user=user, code=code).latest("created_at")
    except (Users.DoesNotExist, LoginCode.DoesNotExist):
        return False

    if login_code.is_valid():
        login_code.used = True
        login_code.save(update_fields=["used"])
        return True
    return False
"""