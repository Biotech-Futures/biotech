"""Emailing a student's guardian the consent form, from the admin user sheet.

The email goes to the guardian whose consent is still needed: a requested
guardian change if there is one, otherwise the guardian on file. Consent itself
still arrives through the join-permission webhook; this only asks for it.
"""
from datetime import timedelta
from typing import Any, Dict

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.admin.services.user import fetch_user_by_id
from apps.audit.services import log_audit_event
from apps.services.system_email import FAILED, SKIPPED, send_system_email
from apps.users.models import StudentProfile

EMAIL_KEY = "guardian_consent_request"

# Spaces out sends to one guardian, so a double click or an impatient resend
# doesn't fill their inbox.
RESEND_COOLDOWN = timedelta(minutes=10)

# Outcomes, mapped to HTTP codes by the view.
SENT = "sent"
NOT_FOUND = "not_found"
INVALID = "invalid"
THROTTLED = "throttled"
NOT_CONFIGURED = "not_configured"
DISABLED = "disabled"
SEND_FAILED = "failed"


def _result(outcome: str, msg: str, data=None) -> Dict[str, Any]:
    return {"status": outcome, "msg": msg, "data": data}


def _is_placeholder_name(first: str, last: str, user) -> bool:
    """A student created without a guardian has their own name copied into the
    guardian fields; that isn't a name to greet the guardian by."""
    guardian = f"{first or ''} {last or ''}".strip().lower()
    student = f"{user.first_name or ''} {user.last_name or ''}".strip().lower()
    return not guardian or guardian == student


def send_guardian_consent_request(user_id: int, initiated_by=None) -> Dict[str, Any]:
    """Email the consent form to the guardian of student ``user_id``."""
    consent_url = (getattr(settings, "GUARDIAN_CONSENT_FORM_URL", "") or "").strip()
    if not consent_url:
        return _result(
            NOT_CONFIGURED,
            "The consent form link isn't set up (GUARDIAN_CONSENT_FORM_URL), so no request was sent.",
        )

    with transaction.atomic():
        profile = (
            StudentProfile.objects.select_for_update()
            .select_related("user")
            .filter(user_id=user_id)
            .first()
        )
        if profile is None:
            return _result(NOT_FOUND, "Student not found.")

        if profile.has_pending_guardian:
            first, last, email = (
                profile.pending_pg_first_name,
                profile.pending_pg_last_name,
                profile.pending_pg_email,
            )
        elif profile.has_join_permission:
            return _result(INVALID, "Consent is already recorded for this student.")
        else:
            first, last, email = profile.pg_first_name, profile.pg_last_name, profile.pg_email

        email = (email or "").strip()
        if not email:
            return _result(INVALID, "This student has no guardian email to send to.")

        sent_at = profile.guardian_request_sent_at
        now = timezone.now()
        if sent_at and now - sent_at < RESEND_COOLDOWN:
            wait = int((RESEND_COOLDOWN - (now - sent_at)).total_seconds() // 60) + 1
            return _result(
                THROTTLED,
                f"A consent request was just sent. Try again in {wait} minute{'s' if wait != 1 else ''}.",
            )

        student = profile.user
        outcome = send_system_email(
            EMAIL_KEY,
            [email],
            {
                "GUARDIAN_FIRST_NAME": "" if _is_placeholder_name(first, last, student) else first,
                "STUDENT_FIRST_NAME": student.first_name or "your student",
                "STUDENT_NAME": f"{student.first_name or ''} {student.last_name or ''}".strip() or student.email,
                "STUDENT_EMAIL": student.email,
                "CONSENT_URL": consent_url,
            },
        )
        if outcome == SKIPPED:
            return _result(DISABLED, "Guardian consent request emails are switched off on System Emails.")
        if outcome == FAILED:
            return _result(SEND_FAILED, "The mail server didn't accept the email. Try again shortly.")

        profile.guardian_request_sent_at = now
        profile.save(update_fields=["guardian_request_sent_at"])
        log_audit_event(
            actor=initiated_by,
            entity_type="user",
            entity_id=user_id,
            action="guardian_consent_request",
            after_state={"guardianEmail": email, "sentAt": now.isoformat()},
        )

    return _result(SENT, f"Consent request sent to {email}.", fetch_user_by_id(user_id))
