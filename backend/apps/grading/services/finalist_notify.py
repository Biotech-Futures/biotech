"""Finalist notification email.

Off by default. Enable per environment with ``GRADING_FINALIST_EMAIL_ENABLED``.
Uses the transactional mailbox (``DEFAULT_FROM_EMAIL`` / ``EMAIL_HOST_USER``)
already configured for the rest of the platform — no new relay to set up.

The spec (page 80) says: "if flagging from the grading system and piping of
text can be implemented into the announcements, this is not required as a
dedicated system email. However, would be a 'nice to have'." — so this is
the "nice to have" fallback for when the announcement piping isn't ready.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import get_connection
from django.utils import timezone

from apps.groups.models.group_members import GroupMembership
from apps.services.system_email import build_message, is_email_enabled, render_system_email

from ..models import FinalistFlag

logger = logging.getLogger(__name__)


def notify_finalist(flag: FinalistFlag, actor=None) -> bool:
    """Send the "you're a finalist" email to every active member of the group.

    No-op when the env flag is off, or when the flag has already been
    ``notified`` (avoids re-mailing on toggle churn). Returns True when an
    email was actually dispatched, False otherwise. Non-fatal on send errors
    — the finalist flag itself stays intact.
    """
    if not getattr(settings, "GRADING_FINALIST_EMAIL_ENABLED", False):
        logger.info("finalist notify skipped: GRADING_FINALIST_EMAIL_ENABLED off (group=%s)", flag.group_id)
        return False
    if flag.notified:
        logger.info("finalist notify skipped: already notified (group=%s)", flag.group_id)
        return False
    if not is_email_enabled("finalist_notification"):
        # Not marked notified, so the group is emailed once an admin turns it back on.
        logger.info("finalist notify skipped: switched off by an admin (group=%s)", flag.group_id)
        return False

    recipients = list(dict.fromkeys(
        GroupMembership.objects.filter(
            group_id=flag.group_id,
            left_at__isnull=True,
        )
        .exclude(user__email="")
        .values_list("user__email", flat=True)
    ))
    if not recipients:
        logger.info("finalist notify skipped: group %s has no active members with emails", flag.group_id)
        return False

    group_name = flag.group.group_name
    body = (
        f"Hi,\n\n"
        f"Your group ({group_name}) has been selected as a finalist "
        f"for the BIOTech Futures Challenge. The BIOTech Futures team will be in "
        f"touch with details about presenting at the symposium.\n\n"
        f"Kind regards,\n"
        f"BIOTech Futures Team\n"
    )

    try:
        rendered = render_system_email(
            "finalist_notification", {"GROUP_NAME": group_name}, default_text=body,
        )
    except Exception:  # noqa: BLE001
        logger.exception("finalist notify failed to render: group=%s", flag.group_id)
        return False

    sent = _send_to_each(rendered, recipients, group_id=flag.group_id)
    if not sent:
        # Nobody received it: leave the flag unnotified so the next press retries.
        logger.error("finalist notify failed: no email delivered (group=%s)", flag.group_id)
        return False

    flag.notified = True
    flag.notified_at = timezone.now()
    flag.notified_by = actor
    flag.save(update_fields=["notified", "notified_at", "notified_by"])
    return True


def _send_to_each(rendered, recipients, *, group_id) -> int:
    """Send one copy per member over a single connection. Returns how many sent.

    One message each rather than one listing the whole group: members would
    otherwise see each other's addresses, and one bad address would stop
    everyone's copy.
    """
    connection = get_connection(fail_silently=False)
    try:
        connection.open()
    except Exception as exc:  # noqa: BLE001
        logger.error("finalist notify: connection failed group=%s error=%s", group_id, type(exc).__name__)
        return 0

    sent = 0
    try:
        for address in recipients:
            message = build_message(
                rendered, address, from_email=settings.DEFAULT_FROM_EMAIL, connection=connection,
            )
            try:
                message.send(fail_silently=False)
            except Exception as exc:  # noqa: BLE001
                # Error type only: SMTP errors carry the recipient address.
                logger.error("finalist notify: send failed group=%s error=%s", group_id, type(exc).__name__)
            else:
                sent += 1
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass
    return sent
