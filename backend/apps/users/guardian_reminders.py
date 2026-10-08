"""Student resends and scheduled reminders share the signed consent email flow."""
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError, Throttled

from .guardian_consent import guardian_to_ask
from .models import StudentProfile


def reminder_info(profile):
    from apps.admin.services.guardian_consent import RESEND_COOLDOWN
    guardian = guardian_to_ask(profile)
    last_request = profile.consent_requests.order_by("-created_at").first()
    last_sent = last_request.created_at if last_request else profile.guardian_reminder_sent_at
    reason = ""
    if guardian is None:
        reason = "Guardian permission has already been received."
    elif not guardian.email:
        reason = "Add a guardian email address before sending an invitation."
    elif guardian.email == (profile.user.email or "").strip().lower():
        reason = "Use your guardian's email address, not your own."
    elif last_sent and last_sent + RESEND_COOLDOWN > timezone.now():
        reason = "An invitation was sent recently. Please wait 10 minutes before resending."
    return {
        "last_sent_at": last_sent,
        "next_due_at": profile.guardian_reminder_due_at if guardian and getattr(settings, "GUARDIAN_REMINDER_INTERVAL_DAYS", 0) > 0 else None,
        "can_send": not reason,
        "unavailable_reason": reason,
    }


def send_guardian_reminder(user_id):
    from apps.admin.services.guardian_consent import send_guardian_consent_request
    result = send_guardian_consent_request(user_id)
    if result["status"] == "throttled":
        raise Throttled(detail=result["msg"])
    if result["status"] != "sent":
        raise ValidationError({"detail": result["msg"]})
    return StudentProfile.objects.get(user_id=user_id)
