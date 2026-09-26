"""Finalist notification email.

Uses the transactional mailbox (``DEFAULT_FROM_EMAIL`` / ``EMAIL_HOST_USER``)
already configured for the rest of the platform — no new relay to set up.

The wording is the client's own finalist email (sent from Power Automate in
2025); the Symposium date, confirm-by date, slides due date and registration
link come from :class:`FinalistEmailSettings`, set on the Notify Finalists
page, and nothing is sent until all of them are set. The email asks one team
member to reply, so replies go to the support mailbox.
"""
from __future__ import annotations

import logging
from datetime import date
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.services.email_branding import attach_inline_logo, brand_context
from apps.services.mailer import send_async
from apps.submissions.emails import recipients_for, send_individually

from ..models import FinalistEmailSettings, FinalistFlag

logger = logging.getLogger(__name__)

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


def subject_line() -> str:
    return f"Congratulations – You’re a {settings.BRAND_NAME} Finalist!"


def render_finalist_email(group_name: str, details: FinalistEmailSettings) -> tuple[str, str]:
    """The email's plain-text and HTML bodies for one team."""
    context = {
        **brand_context(),
        "GROUP_NAME": group_name,
        "SYMPOSIUM_DATE": _long_date(details.symposium_date),
        "CONFIRM_BY": _long_date(details.confirm_by),
        "SLIDES_DUE": _long_date(details.slides_due),
        "REGISTER_URL": details.registration_url or NOT_SET,
    }
    text = render_to_string("emails/finalist_notification.txt", context)
    html = render_to_string("emails/finalist_notification.html", context)
    return text, html


class _TeamEmails:
    """One team's messages as one task on the shared mail pool (so login codes
    are not delayed). If none of them could be sent, the team goes back to
    not notified, so the page shows it and a later send can retry."""

    def __init__(self, messages, flag_id: int):
        self.messages = messages
        self.flag_id = flag_id

    def send(self) -> int:
        sent, _ = send_individually(self.messages, kind="finalist_notification")
        if not sent:
            logger.error("finalist_notify.all_failed flag=%s", self.flag_id)
            FinalistFlag.objects.filter(pk=self.flag_id).update(
                notified=False, notified_at=None, notified_by=None
            )
        return sent


def notify_finalist(flag: FinalistFlag, actor=None, details: FinalistEmailSettings | None = None) -> bool:
    """Email every active member of a finalist team (students, mentors and
    supervisors), each their own copy.

    No-op when the flag has already been ``notified`` (avoids re-mailing on
    toggle churn), when the email details aren't all set, or when the team
    has nobody to mail. Returns True when the
    team's emails were queued. The team is marked notified before they go, so
    pressing Send again while they are on their way can't mail it twice.
    """
    if flag.notified:
        logger.info("finalist notify skipped: already notified (group=%s)", flag.group_id)
        return False
    details = details or FinalistEmailSettings.load()
    if not details.is_complete:
        logger.info("finalist notify skipped: email details not set (group=%s)", flag.group_id)
        return False

    recipients = recipients_for(flag.group)
    if not recipients:
        logger.info("finalist notify skipped: group %s has no active members with emails", flag.group_id)
        return False

    text, html = render_finalist_email(flag.group.group_name, details)
    messages = []
    for address in recipients:
        message = EmailMultiAlternatives(
            subject=subject_line(),
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[address],
            # "Have one team member reply to this email": replies reach support.
            reply_to=[settings.SUPPORT_EMAIL],
        )
        message.attach_alternative(html, "text/html")
        attach_inline_logo(message)
        messages.append(message)

    flag.notified = True
    flag.notified_at = timezone.now()
    flag.notified_by = actor
    flag.save(update_fields=["notified", "notified_at", "notified_by"])
    send_async(_TeamEmails(messages, flag.pk), kind="finalist_notification")
    return True
