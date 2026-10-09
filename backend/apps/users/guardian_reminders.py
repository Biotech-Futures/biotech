"""Student resends and scheduled reminders share the signed consent email flow.

Until a guardian signs, they're emailed the consent form: as soon as a student
names them on their profile, and then once a day (every
``GUARDIAN_REMINDER_INTERVAL_DAYS``; 0 switches the reminders off) by the
daily run, which also sends the first email to guardians added any other way
(registration, an admin, the student import). Each email carries a fresh link
that replaces the last. They never stop until consent is recorded.
"""
import logging
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, Throttled

from apps.services.system_email import is_email_enabled

from .guardian_consent import guardian_to_ask
from .models import StudentProfile, User

logger = logging.getLogger(__name__)

# Invited and pending accounts belong to students still waiting on consent.
_CAN_SIGN_IN = (User.AccountStatus.INVITED, User.AccountStatus.PENDING, User.AccountStatus.ACTIVE)


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


def email_new_guardian(profile) -> None:
    """Email the consent form to the guardian a student just named, unless
    they've been sent it already or no consent is needed. Never raises: the
    details are saved either way, and the daily run tries again."""
    from apps.admin.services.guardian_consent import send_guardian_consent_request

    guardian = guardian_to_ask(profile)
    if guardian is None or not guardian.email:
        return
    if profile.consent_requests.filter(guardian_email=guardian.email).exists():
        return
    try:
        send_guardian_consent_request(profile.user_id)
    except Exception:  # noqa: BLE001
        logger.exception("guardian_reminders.new_guardian_failed student=%s", profile.user_id)


def _today(now):
    """The start of today and of tomorrow, in the server's time zone."""
    start = timezone.make_aware(datetime.combine(timezone.localdate(now), time.min))
    return start, start + timedelta(days=1)


def guardians_due(now=None):
    """Students whose guardian is due the consent form today.

    This challenge year's students who can still sign in, whose consent is
    still needed (or whose change of guardian waits on the new one) and who
    have that guardian's email; not emailed today, with their next reminder
    due by the end of today. A guardian nobody has emailed yet is due at once.
    """
    from apps.submissions.services import current_cohort

    start, end = _today(now or timezone.now())
    no_email = Q(pg_email__isnull=True) | Q(pg_email="")
    no_pending_email = Q(pending_pg_email__isnull=True) | Q(pending_pg_email="")
    waiting = (Q(has_join_permission=False) & ~no_email) | (
        Q(pending_pg_requested_at__isnull=False) & ~no_pending_email
    )
    return (
        StudentProfile.objects.select_related("user")
        .filter(
            waiting,
            user__account_status__in=_CAN_SIGN_IN,
            user__date_joined__year=current_cohort(),
        )
        .filter(Q(guardian_reminder_sent_at__isnull=True) | Q(guardian_reminder_sent_at__lt=start))
        .filter(Q(guardian_reminder_due_at__isnull=True) | Q(guardian_reminder_due_at__lt=end))
        .order_by("user_id")
    )


def send_due(now=None, *, dry_run: bool = False) -> dict:
    """Email every guardian due today and count what happened.

    Off when ``GUARDIAN_REMINDER_INTERVAL_DAYS`` is 0 or the Guardian consent
    request email is switched off on System Emails. Skipped are those the
    send refuses, e.g. a guardian email that is the student's own.
    """
    from apps.admin.services.guardian_consent import (
        EMAIL_KEY,
        SEND_FAILED,
        SENT,
        send_guardian_consent_request,
    )

    if getattr(settings, "GUARDIAN_REMINDER_INTERVAL_DAYS", 0) <= 0 or not is_email_enabled(EMAIL_KEY):
        return {"sent": 0, "failed": 0, "skipped": 0, "disabled": True}

    sent = failed = skipped = 0
    for profile in guardians_due(now):
        if dry_run:
            sent += 1
            continue
        outcome = send_guardian_consent_request(profile.user_id)["status"]
        if outcome == SENT:
            sent += 1
        elif outcome == SEND_FAILED:
            failed += 1
        else:
            skipped += 1

    if failed:
        logger.error("guardian_reminders.failed sent=%s failed=%s skipped=%s", sent, failed, skipped)
    return {"sent": sent, "failed": failed, "skipped": skipped}
