"""The daily email asking students for their parent/guardian's details.

A student with no guardian email on file can't have the consent form sent, so
they're emailed once a day until they add one on their profile. Only this
challenge year's students (by when their account was made) whose account can
still sign in are emailed, and none whose consent is already recorded. Admins
can switch it off on System Emails.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.services.system_email import SENT, is_email_enabled, send_system_email

from .models import StudentProfile, User

logger = logging.getLogger(__name__)

EMAIL_KEY = "guardian_details_request"

# Invited and pending accounts can still sign in to add the details.
_CAN_SIGN_IN = (User.AccountStatus.INVITED, User.AccountStatus.PENDING, User.AccountStatus.ACTIVE)


def details_link() -> str:
    """The student's profile, with the guardian form open."""
    return f"{settings.FRONTEND_BASE_URL}/#/profile?guardian=edit"


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
            user__date_joined__year=current_cohort(),
        )
        .exclude(user__email="")
        .exclude(guardian_details_reminded_on=today)
        .order_by("user_id")
    )


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
