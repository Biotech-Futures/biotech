"""The daily email asking students for their parent/guardian's details.

A student with no guardian email on file can't have the consent form sent, so
they're emailed once a day until they add one on their profile. Only this
challenge year's students (by when their account was made) whose account can
still sign in are emailed, and none whose consent is already recorded. Admins
can switch it off on System Emails.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import log_audit_event

from apps.services.system_email import SENT, is_email_enabled, send_system_email

from .models import StudentProfile, User

logger = logging.getLogger(__name__)

EMAIL_KEY = "guardian_details_request"

# Invited and pending accounts can still sign in to add the details.
_CAN_SIGN_IN = (User.AccountStatus.INVITED, User.AccountStatus.PENDING, User.AccountStatus.ACTIVE)


def details_link() -> str:
    """The student's profile, with the guardian form open."""
    return f"{settings.FRONTEND_BASE_URL}/#/profile?guardian=edit"


# A supervisor's Copy Details Link: a public form for the guardian's name and
# email, for whoever the supervisor sends it to. The signed token is the only
# credential, and the form closes once the student has a guardian email.
FORM_LINK_LIFETIME = timedelta(days=14)
_FORM_SALT = "guardian-details-form"


class DetailsFormError(Exception):
    """A details form link that can't be used, with a code the page can act on."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def details_form_link(profile: StudentProfile) -> str:
    """A link to the details form. Copying one resets the time for every
    copy out: each works until FORM_LINK_LIFETIME after the latest."""
    now = timezone.now()
    StudentProfile.objects.filter(pk=profile.pk).update(guardian_details_link_at=now)
    profile.guardian_details_link_at = now
    token = signing.dumps({"student": profile.user_id}, salt=_FORM_SALT)
    return f"{settings.FRONTEND_BASE_URL}/#/guardian-details/{token}"


def open_details_form(token: str, *, for_update: bool = False) -> StudentProfile:
    """The student behind a details form link, while it can still be used:
    until the guardian's details are given (or consent recorded), and for
    FORM_LINK_LIFETIME after the latest copy of the link."""
    expired = DetailsFormError("expired", "This link has expired. Ask the student's supervisor for a new one.")
    try:
        data = signing.loads(token or "", salt=_FORM_SALT)
    except signing.BadSignature:
        raise DetailsFormError("invalid", "This link isn't valid. Check you opened the whole link.")
    queryset = StudentProfile.objects.select_related("user")
    if for_update:
        queryset = queryset.select_for_update()
    profile = queryset.filter(user_id=data.get("student")).first()
    if profile is None:
        raise DetailsFormError("invalid", "This link isn't valid. Check you opened the whole link.")
    if (profile.pg_email or "").strip() or profile.has_join_permission:
        raise DetailsFormError("done", "The guardian's details have already been given. Thank you.")
    latest = profile.guardian_details_link_at
    if latest is None:
        # A link copied before copies reset the time counts from when it was made.
        try:
            signing.loads(token, salt=_FORM_SALT, max_age=FORM_LINK_LIFETIME)
        except signing.SignatureExpired:
            raise expired
    elif timezone.now() - latest > FORM_LINK_LIFETIME:
        raise expired
    return profile


def student_name(profile: StudentProfile) -> str:
    user = profile.user
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email


def save_details_form(token: str, *, first_name: str, last_name: str, email: str) -> StudentProfile:
    """Record the guardian named on a details form, then email them the
    consent form, as when a student names them on their profile. Raises
    DetailsFormError for a link that can't be used and ValueError for the
    student's own email, a placeholder or a student's account."""
    from .guardian_reminders import email_new_guardian
    from .serializers import new_guardian_email_problem

    email = email.strip().lower()
    with transaction.atomic():
        profile = open_details_form(token, for_update=True)
        if email == (profile.user.email or "").strip().lower():
            raise ValueError("Enter the guardian's email, not the student's.")
        if email != (profile.pg_email or "").strip().lower() and (problem := new_guardian_email_problem(email)):
            raise ValueError(problem)
        profile.pg_first_name = first_name.strip()
        profile.pg_last_name = last_name.strip()
        profile.pg_email = email
        profile.parent_guardian_flag = True
        profile.clear_pending_guardian()
        profile.save()
        log_audit_event(
            actor=None,
            entity_type="user",
            entity_id=profile.user_id,
            action="guardian_update",
            after_state={"guardianEmail": email, "via": "details_form"},
        )
    email_new_guardian(profile)
    return profile


def students_due(now=None):
    """Students with no guardian email, not yet emailed today."""
    from apps.submissions.services import current_cohort

    today = timezone.localdate(now or timezone.now())
    return (
        StudentProfile.objects.select_related("user")
        .filter(
            Q(pg_email__isnull=True) | Q(pg_email=""),
            has_join_permission=False,
            user__account_status__in=_CAN_SIGN_IN,
            challenge_year=current_cohort(),
        )
        .exclude(user__email="")
        .exclude(guardian_details_reminded_on=today)
        .order_by("user_id")
    )


def send_to_student(profile: StudentProfile, initiated_by=None) -> dict:
    """Email one student the guardian-details request. Used by supervisors."""
    if not is_email_enabled(EMAIL_KEY):
        return {
            "status": "disabled",
            "msg": "Guardian details emails are switched off on System Emails.",
        }
    if profile.has_join_permission:
        return {"status": "invalid", "msg": "Consent is already recorded for this student."}
    if (profile.pg_email or "").strip():
        return {
            "status": "invalid",
            "msg": "This student already has a guardian email on file.",
        }
    email = (profile.user.email or "").strip()
    if not email:
        return {"status": "invalid", "msg": "This student has no email address."}

    outcome = send_system_email(
        EMAIL_KEY,
        [email],
        {"STUDENT_FIRST_NAME": profile.user.first_name or "", "DETAILS_URL": details_link()},
        sent_by=initiated_by,
    )
    if outcome != SENT:
        return {
            "status": "failed",
            "msg": "The mail server didn't accept the email. Try again shortly.",
        }
    StudentProfile.objects.filter(pk=profile.pk).update(
        guardian_details_reminded_on=timezone.localdate(),
    )
    return {"status": "sent", "msg": f"Details request sent to {email}."}


def send_due(now=None, *, dry_run: bool = False) -> dict:
    """Email every student due today and return counts of sent and failed.

    When an admin has switched the email off, nothing is sent or recorded. A
    student whose email doesn't go isn't recorded, so the next run tries again.
    """
    if not is_email_enabled(EMAIL_KEY):
        return {"sent": 0, "failed": 0, "disabled": True}

    today = timezone.localdate(now or timezone.now())
    sent = failed = 0
    for profile in students_due(now):
        if dry_run:
            sent += 1
            continue
        outcome = send_system_email(
            EMAIL_KEY,
            [profile.user.email],
            {"STUDENT_FIRST_NAME": profile.user.first_name or "", "DETAILS_URL": details_link()},
        )
        if outcome != SENT:
            failed += 1
            continue
        StudentProfile.objects.filter(pk=profile.pk).update(guardian_details_reminded_on=today)
        sent += 1

    if failed:
        logger.error("guardian_details_request.failed sent=%s failed=%s", sent, failed)
    return {"sent": sent, "failed": failed}


def reminder_job(actor, options) -> dict:
    """The queued run of today's details emails (``send_guard.JOBS``). Each
    that fails is tried once more at once, as every single email is."""
    return send_due()
