import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from apps.users.models import Users, LoginCode
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

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