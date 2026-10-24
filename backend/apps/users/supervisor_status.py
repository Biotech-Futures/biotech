"""The supervisors' weekly registration status email (the spec's "Supervisor
Weekly Digest"): to each supervisor with a student this year whose permission
form isn't signed yet, how many of their students are complete, waiting for
their guardian's signature, or waiting for their guardian's details, by the
same rules as My Students. Once a week at most, until every one of their
students is complete. The job runs daily, so a missed run is made up the next
day: a supervisor emailed in the last week is skipped, so a repeated or
overlapping run emails nobody twice. Admins can switch it off on System Emails.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.services.system_email import SENT, is_email_enabled, send_system_email

from .models import StudentProfile, SupervisorProfile, User

# The day the challenge starts, as the email names it, is Sydney's.
CHALLENGE_TZ = ZoneInfo("Australia/Sydney")

logger = logging.getLogger(__name__)

EMAIL_KEY = "supervisor_registration_status"

# Days between one supervisor's emails.
INTERVAL_DAYS = 7

# Accounts that can still sign in (or will): theirs and their students'.
_CAN_SIGN_IN = (User.AccountStatus.INVITED, User.AccountStatus.PENDING, User.AccountStatus.ACTIVE)


def _students(supervisor_id: int):
    """A supervisor's students this challenge year (registered for it, or
    back for it, as the guardian emails count them) whose accounts can still
    sign in."""
    return StudentProfile.objects.filter(
        supervisor_id=supervisor_id,
        user__account_status__in=_CAN_SIGN_IN,
        challenge_year=_cohort(),
    )


def status_counts(supervisor_id: int) -> dict:
    """Complete (permission given), pending signature (a guardian email on
    file, the form not signed) and pending contact (no guardian email)."""
    students = _students(supervisor_id)
    no_guardian = Q(pg_email__isnull=True) | Q(pg_email="")
    return {
        "complete": students.filter(has_join_permission=True).count(),
        "pending_signature": students.filter(has_join_permission=False).exclude(no_guardian).count(),
        "pending_contact": students.filter(no_guardian, has_join_permission=False).count(),
    }


def challenge_start_text() -> str:
    """"27 July": the day this year's challenge starts (Management > Challenge
    Start), in Sydney; its time isn't named. "" while it isn't set."""
    from apps.management.models import ChallengeStart
    from apps.submissions.services import current_cohort

    starts_at = ChallengeStart.for_year(current_cohort()).starts_at
    if not starts_at:
        return ""
    day = timezone.localtime(starts_at, CHALLENGE_TZ)
    return f"{day.day} {day:%B}"


def status_context(user) -> dict:
    """The merge values a supervisor's email carries."""
    counts = status_counts(user.id)
    return {
        "First_Name": user.first_name,
        "COMPLETE_COUNT": str(counts["complete"]),
        "PENDING_SIGNATURE_COUNT": str(counts["pending_signature"]),
        "PENDING_CONTACT_COUNT": str(counts["pending_contact"]),
        "CHALLENGE_START": challenge_start_text(),
        "STUDENTS_URL": f"{settings.FRONTEND_BASE_URL}/#/my-students",
    }


def supervisors_due(now=None):
    """Supervisors who can sign in, with a student still pending, not
    emailed in the last week (emailed on a Monday, due again the next Monday)."""
    today = timezone.localdate(now or timezone.now())
    pending = StudentProfile.objects.filter(
        has_join_permission=False,
        user__account_status__in=_CAN_SIGN_IN,
        challenge_year=_cohort(),
    ).values("supervisor_id")
    return (
        SupervisorProfile.objects.select_related("user")
        .filter(pk__in=pending, user__account_status=User.AccountStatus.ACTIVE)
        .exclude(user__email="")
        .exclude(status_digest_sent_on__gt=today - timedelta(days=INTERVAL_DAYS))
        .order_by("pk")
    )


def _cohort() -> int:
    from apps.submissions.services import current_cohort

    return current_cohort()


def send_due(now=None, *, dry_run: bool = False) -> dict:
    """Email every supervisor due today; counts of sent and failed. Switched
    off on System Emails, nothing is sent or noted. One that doesn't go isn't
    noted, so the next run tries again."""
    if not is_email_enabled(EMAIL_KEY):
        return {"sent": 0, "failed": 0, "disabled": True}

    today = timezone.localdate(now or timezone.now())
    sent = failed = 0
    for profile in supervisors_due(now):
        if dry_run:
            sent += 1
            continue
        outcome = send_system_email(EMAIL_KEY, [profile.user.email], status_context(profile.user))
        if outcome != SENT:
            failed += 1
            continue
        SupervisorProfile.objects.filter(pk=profile.pk).update(status_digest_sent_on=today)
        sent += 1

    if failed:
        logger.error("supervisor_registration_status.failed sent=%s failed=%s", sent, failed)
    return {"sent": sent, "failed": failed}


def digest_job(actor, options) -> dict:
    """The queued run of today's emails (``send_guard.JOBS``)."""
    return send_due()
