"""Finalist notification email.

Uses the transactional mailbox (``DEFAULT_FROM_EMAIL`` / ``EMAIL_HOST_USER``)
already configured for the rest of the platform — no new relay to set up — and
goes through the shared system email path, so admins can switch it off or
reword it like any other system email.

The default wording is the client's own finalist email (sent from Power
Automate in 2025); the Symposium date, confirm-by date, slides due date and
registration link come from :class:`FinalistEmailSettings`, set on the Notify
Finalists page, and nothing is sent until all of them are set. The email asks
one team member to reply, and replies go back to the sender.
"""
from __future__ import annotations

import logging
from datetime import date
from zoneinfo import ZoneInfo

from django.template.loader import render_to_string
from django.utils import timezone

from apps.grading.models import FinalistFlag
from apps.services.email_branding import brand_context
from apps.services.system_email import (
    RenderedEmail,
    is_email_enabled,
    render_system_email,
)
from apps.submissions.emails import recipients_for

from ..models import FinalistEmailSettings
from .delivery import send_group

logger = logging.getLogger(__name__)

EMAIL_KEY = "finalist_notification"

# Shown in a preview where a detail hasn't been filled in yet.
NOT_SET = "[not set]"

# The Symposium runs in Sydney, so "today" for its dates is Sydney's.
SYMPOSIUM_TZ = ZoneInfo("Australia/Sydney")


def symposium_today() -> date:
    return timezone.localdate(timezone=SYMPOSIUM_TZ)


def _long_date(day: date | None) -> str:
    """"Friday, 24 October 2025"; built from parts because "%-d" fails on Windows."""
    if day is None:
        return NOT_SET
    return f"{day:%A}, {day.day} {day:%B %Y}"


def finalist_email_context(group_name: str, details: FinalistEmailSettings) -> dict:
    """The values the email's merge tags and template read."""
    return {
        "GROUP_NAME": group_name,
        "SYMPOSIUM_DATE": _long_date(details.symposium_date),
        "CONFIRM_BY": _long_date(details.confirm_by),
        "SLIDES_DUE": _long_date(details.slides_due),
        "REGISTER_URL": details.registration_url or NOT_SET,
    }


def render_finalist_email(group_name: str, details: FinalistEmailSettings) -> RenderedEmail:
    """The email for one team: an admin's saved wording if there is some,
    otherwise the client's template, with its plain-text twin."""
    context = finalist_email_context(group_name, details)
    default_text = render_to_string(
        "emails/finalist_notification.txt", {**brand_context(), **context}
    )
    return render_system_email(EMAIL_KEY, context, default_text=default_text)


def notify_finalist(
    flag: FinalistFlag, actor=None, details: FinalistEmailSettings | None = None, connection=None,
    missed: dict | None = None,
) -> bool:
    """Email every active member of a finalist team in one email: its
    students in To, its mentors and supervisors in CC.

    No-op when the flag has already been ``notified`` (avoids re-mailing on
    toggle churn), when an admin has switched the email off, when the email
    details aren't all set, or when the team has nobody to mail. Returns True
    only when every member has the email; the team is only marked notified
    then, so a send someone missed can simply be retried, and the retry emails
    only them. The addresses it couldn't reach go into ``missed``, when given,
    each with why.
    """
    if flag.notified:
        logger.info("finalist notify skipped: already notified (group=%s)", flag.group_id)
        return False
    if not is_email_enabled(EMAIL_KEY):
        # Not marked notified, so the group is emailed once an admin turns it back on.
        logger.info("finalist notify skipped: switched off by an admin (group=%s)", flag.group_id)
        return False
    details = details or FinalistEmailSettings.load()
    if not details.is_complete:
        logger.info("finalist notify skipped: email details not set (group=%s)", flag.group_id)
        return False

    recipients = recipients_for(flag.group)
    if not recipients:
        logger.info("finalist notify skipped: group %s has no active members with emails", flag.group_id)
        return False

    try:
        rendered = render_finalist_email(flag.group.group_name, details)
    except Exception:  # noqa: BLE001
        logger.exception("finalist notify failed to render: group=%s", flag.group_id)
        return False

    failed = send_group(
        rendered, recipients, connection, email=EMAIL_KEY, group=flag.group, log_as=f"group={flag.group_id}",
    )
    if failed:
        # Someone missed it: leave the flag unnotified so the next press retries.
        logger.error(
            "finalist notify failed: %s of %s members missed (group=%s)", len(failed), len(recipients), flag.group_id,
        )
        if missed is not None:
            missed.update(failed)
        return False

    flag.notified = True
    flag.notified_at = timezone.now()
    flag.notified_by = actor
    flag.save(update_fields=["notified", "notified_at", "notified_by"])
    return True
