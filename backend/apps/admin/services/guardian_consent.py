"""Guardian consent from the admin user sheet: emailing the consent form,
viewing signed consents and recording a guardian's withdrawal.

The email goes to the guardian whose consent is still needed: a requested
guardian change if there is one, otherwise the guardian on file. The link opens
the platform's consent page (apps.users.guardian_consent). Once it has gone,
the student is told too, so they can remind their guardian.
"""
import base64
from datetime import timedelta
from typing import Any, Dict

from django.db import transaction
from django.conf import settings
from django.utils import timezone

from apps.admin.services.user import fetch_user_by_id
from apps.audit.services import log_audit_event
from apps.services.system_email import FAILED, SKIPPED, send_system_email
from apps.users import guardian_consent as consent
from apps.users.models import GuardianConsent, GuardianConsentRequest, StudentProfile

EMAIL_KEY = "guardian_consent_request"
STUDENT_NOTICE_KEY = "guardian_consent_student_notice"

# Spaces out sends to one guardian, so a double click or an impatient resend
# doesn't fill their inbox.
RESEND_COOLDOWN = timedelta(minutes=10)

# Outcomes, mapped to HTTP codes by the view.
SENT = "sent"
OK = "ok"
NOT_FOUND = "not_found"
INVALID = "invalid"
THROTTLED = "throttled"
DISABLED = "disabled"
SEND_FAILED = "failed"


def _result(outcome: str, msg: str, data=None) -> Dict[str, Any]:
    return {"status": outcome, "msg": msg, "data": data}


def send_guardian_consent_request(user_id: int, initiated_by=None) -> Dict[str, Any]:
    """Email the consent form to the guardian of student ``user_id``."""
    with transaction.atomic():
        profile = (
            StudentProfile.objects.select_for_update()
            .select_related("user")
            .filter(user_id=user_id)
            .first()
        )
        if profile is None:
            return _result(NOT_FOUND, "Student not found.")

        guardian = consent.guardian_to_ask(profile)
        if guardian is None:
            return _result(INVALID, "Consent is already recorded for this student.")
        if not guardian.email:
            return _result(INVALID, "This student has no guardian email to send to.")
        if guardian.email == (profile.user.email or "").strip().lower():
            return _result(
                INVALID,
                "The guardian email is the student's own address. Update it to the guardian's before sending.",
            )

        last_sent = (
            GuardianConsentRequest.objects.filter(student=profile)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        now = timezone.now()
        if last_sent and now - last_sent < RESEND_COOLDOWN:
            wait = int((RESEND_COOLDOWN - (now - last_sent)).total_seconds() // 60) + 1
            return _result(
                THROTTLED,
                f"A consent request was just sent. Try again in {wait} minute{'s' if wait != 1 else ''}.",
            )

        # The student hears once that their guardian was emailed, not with every reminder.
        first_to_guardian = not GuardianConsentRequest.objects.filter(
            student=profile, guardian_email=guardian.email,
        ).exists()
        request, token = consent.issue_request(profile, guardian, sent_by=initiated_by)
        student = profile.user
        outcome = send_system_email(
            EMAIL_KEY,
            [guardian.email],
            {
                "GUARDIAN_FIRST_NAME": (
                    "" if consent.is_placeholder_name(guardian.first_name, guardian.last_name, profile)
                    else guardian.first_name
                ),
                "STUDENT_FIRST_NAME": student.first_name or "your student",
                "STUDENT_NAME": consent.student_name(profile),
                "CONSENT_URL": consent.consent_link(token),
                "EXPIRY_DAYS": consent.LINK_LIFETIME.days,
            },
        )
        if outcome in (SKIPPED, FAILED):
            # Nobody got the link, so it must not count as sent or replace the
            # previous one: undo the whole request.
            transaction.set_rollback(True)
            if outcome == SKIPPED:
                return _result(DISABLED, "Guardian consent request emails are switched off on System Emails.")
            return _result(SEND_FAILED, "The mail server didn't accept the email. Try again shortly.")

        profile.guardian_reminder_sent_at = now
        interval = getattr(settings, "GUARDIAN_REMINDER_INTERVAL_DAYS", 0)
        profile.guardian_reminder_due_at = now + timedelta(days=interval) if interval > 0 else None
        profile.save(update_fields=["guardian_reminder_sent_at", "guardian_reminder_due_at"])

        log_audit_event(
            actor=initiated_by,
            entity_type="user",
            entity_id=user_id,
            action="guardian_consent_request",
            after_state={"guardianEmail": guardian.email, "requestId": request.pk},
        )

    # The student's copy is an FYI: if it's switched off or doesn't go, the
    # guardian's request still stands.
    if student.email and first_to_guardian:
        send_system_email(
            STUDENT_NOTICE_KEY,
            [student.email],
            {"STUDENT_FIRST_NAME": student.first_name or "", "GUARDIAN_EMAIL": guardian.email},
        )

    return _result(SENT, f"Consent request sent to {guardian.email}.", fetch_user_by_id(user_id))


def list_guardian_consents(user_id: int) -> Dict[str, Any]:
    """Every consent signed on the platform for student ``user_id``, newest
    first, with the signature as an image the admin page can show."""
    profile = StudentProfile.objects.filter(user_id=user_id).first()
    if profile is None:
        return {"msg": "Student not found.", "data": None}
    items = [
        {
            "id": c.pk,
            "reference": c.reference,
            # What its PDF record downloads as, e.g. "2026_318_BTF_1.pdf".
            "fileName": consent.record_pdf_filename(c),
            "guardianFullName": c.guardian_full_name,
            "guardianEmail": c.guardian_email,
            "mediaConsent": c.media_consent,
            "consentVersion": c.consent_version,
            "signedAt": c.signed_at.isoformat(),
            "withdrawnAt": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
            "mediaWithdrawnAt": c.media_withdrawn_at.isoformat() if c.media_withdrawn_at else None,
            "signature": "data:image/png;base64," + base64.b64encode(bytes(c.signature_png)).decode(),
        }
        for c in profile.consents.order_by("-signed_at")
    ]
    return {"msg": "Consents retrieved successfully", "data": items}


def guardian_consent_record(user_id: int, consent_id: int):
    """The signed record PDF for one of student ``user_id``'s consents, as
    (filename, bytes), or None if there's no such consent."""
    record = (
        GuardianConsent.objects.select_related("student__user")
        .filter(pk=consent_id, student__user_id=user_id)
        .first()
    )
    if record is None:
        return None
    return consent.record_pdf_filename(record), consent.record_pdf_bytes(record)


def withdraw_guardian_consent(user_id: int, *, media_only: bool, initiated_by=None) -> Dict[str, Any]:
    """Record that the guardian withdrew consent, or only media consent."""
    profile = StudentProfile.objects.filter(user_id=user_id).first()
    if profile is None:
        return _result(NOT_FOUND, "Student not found.")
    if not profile.has_join_permission:
        return _result(INVALID, "There's no consent on record to withdraw.")
    if media_only and profile.media_consent is False:
        return _result(INVALID, "Media consent is already recorded as not given.")
    consent.withdraw(profile, media_only=media_only, initiated_by=initiated_by)
    msg = "Media consent withdrawn." if media_only else "Consent withdrawn."
    return _result(OK, msg, fetch_user_by_id(user_id))
