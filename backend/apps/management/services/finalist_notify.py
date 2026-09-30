"""Finalist notification email.

Uses the transactional mailbox (``DEFAULT_FROM_EMAIL`` / ``EMAIL_HOST_USER``)
already configured for the rest of the platform — no new relay to set up — and
goes through the shared system email path, so admins can switch it off or
reword it like any other system email.

The default wording is the client's own finalist email (sent from Power
Automate in 2025); the Symposium date, confirm-by date, slides due date and
registration link come from :class:`FinalistEmailSettings`, set on the Notify
Finalists page, and nothing is sent until all of them are set. The email asks
one team member to reply, so replies go to the support mailbox.
"""
from __future__ import annotations

import logging
from datetime import date
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import get_connection
from django.template.loader import render_to_string
from django.utils import timezone

from apps.grading.models import FinalistFlag
from apps.services.email_branding import brand_context
from apps.services.system_email import (
    RenderedEmail,
    build_message,
    is_email_enabled,
    render_system_email,
)
from apps.submissions.emails import recipients_for

from ..models import FinalistEmailSettings

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
    missed: list | None = None,
) -> bool:
    """Email every active member of a finalist team (students, mentors and
    supervisors), each their own copy.

    No-op when the flag has already been ``notified`` (avoids re-mailing on
    toggle churn), when an admin has switched the email off, when the email
    details aren't all set, or when the team has nobody to mail. Returns True
    only when every member was emailed; the team is only marked notified
    then, so a send someone missed can simply be retried. The addresses it
    couldn't reach go into ``missed``, when given.
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

    sent = _send_to_each(rendered, recipients, group_id=flag.group_id, connection=connection, missed=missed)
    if sent < len(recipients):
        # Someone missed it: leave the flag unnotified so the next press retries.
        logger.error(
            "finalist notify failed: %s of %s emails delivered (group=%s)",
            sent, len(recipients), flag.group_id,
        )
        return False

    flag.notified = True
    flag.notified_at = timezone.now()
    flag.notified_by = actor
    flag.save(update_fields=["notified", "notified_at", "notified_by"])
    return True


def _send_to_each(rendered, recipients, *, group_id, connection=None, missed: list | None = None) -> int:
    """Send one copy per member over a single connection: ``connection`` when
    a run passes its own, else one opened for this team. Returns how many
    sent; the addresses it couldn't reach go into ``missed``, when given.

    One message each rather than one listing the whole group: members would
    otherwise see each other's addresses, and one bad address would stop
    everyone's copy.
    """
    own = connection is None
    if own:
        connection = get_connection(fail_silently=False)
        try:
            connection.open()
        except Exception as exc:  # noqa: BLE001
            logger.error("finalist notify: connection failed group=%s error=%s", group_id, type(exc).__name__)
            if missed is not None:
                missed.extend(recipients)
            return 0

    sent = 0
    try:
        for address in recipients:
            message = build_message(
                rendered, address, from_email=settings.DEFAULT_FROM_EMAIL, connection=connection,
            )
            # "Have one team member reply to this email": replies reach support.
            message.reply_to = [settings.SUPPORT_EMAIL]
            try:
                message.send(fail_silently=False)
            except Exception as exc:  # noqa: BLE001
                # Error type only: SMTP errors carry the recipient address.
                logger.error("finalist notify: send failed group=%s error=%s", group_id, type(exc).__name__)
                if missed is not None:
                    missed.append(address)
            else:
                sent += 1
    finally:
        if own:
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass
    return sent
