"""Guardian invitations use the existing external consent form and email service."""
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, Throttled

from apps.services.system_email import SENT, send_system_email
from .models import StudentProfile


def consent_url():
    url = getattr(settings, "GUARDIAN_CONSENT_URL", "").strip()
    parsed = urlsplit(url)
    return url if parsed.scheme == "https" and parsed.netloc else ""


def reminder_info(profile):
    retry_at = profile.guardian_reminder_sent_at + timedelta(hours=24) if profile.guardian_reminder_sent_at else None
    reason = ""
    if profile.has_join_permission:
        reason = "Guardian permission has already been received."
    elif not profile.pg_email:
        reason = "Add a guardian email address before sending an invitation."
    elif not consent_url():
        reason = "Guardian invitations are not available yet. Contact support for help."
    elif retry_at and retry_at > timezone.now():
        reason = "An invitation was sent recently. Please wait 24 hours before resending."
    return {
        "last_sent_at": profile.guardian_reminder_sent_at,
        "next_due_at": profile.guardian_reminder_due_at if not profile.has_join_permission and getattr(settings, "GUARDIAN_REMINDER_INTERVAL_DAYS", 0) > 0 else None,
        "can_send": not reason,
        "unavailable_reason": reason,
    }


@transaction.atomic
def send_guardian_reminder(user_id):
    profile = StudentProfile.objects.select_for_update().select_related("user").get(user_id=user_id)
    info = reminder_info(profile)
    if not info["can_send"]:
        if profile.guardian_reminder_sent_at and not profile.has_join_permission and profile.pg_email and consent_url():
            retry = (profile.guardian_reminder_sent_at + timedelta(hours=24) - timezone.now()).total_seconds()
            if retry > 0:
                raise Throttled(wait=int(retry), detail=info["unavailable_reason"])
        raise ValidationError({"detail": info["unavailable_reason"]})
    result = send_system_email("guardian_invitation", profile.pg_email, {
        "First_Name": profile.pg_first_name,
        "STUDENT_NAME": f"{profile.user.first_name} {profile.user.last_name}".strip(),
        "STUDENT_EMAIL": profile.user.email,
        "CONSENT_URL": consent_url(),
    })
    if result != SENT:
        raise ValidationError({"detail": "The invitation could not be sent. Please try again later or contact support."})
    profile.guardian_reminder_sent_at = timezone.now()
    interval = getattr(settings, "GUARDIAN_REMINDER_INTERVAL_DAYS", 0)
    profile.guardian_reminder_due_at = timezone.now() + timedelta(days=interval) if interval > 0 else None
    profile.save(update_fields=["guardian_reminder_sent_at", "guardian_reminder_due_at"])
    return profile
