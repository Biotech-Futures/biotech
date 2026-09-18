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
from django.core.mail import send_mail
from django.utils import timezone

from apps.groups.models.group_members import GroupMembership

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

    recipients = list(
        GroupMembership.objects.filter(
            group_id=flag.group_id,
            left_at__isnull=True,
        )
        .exclude(user__email="")
        .values_list("user__email", flat=True)
    )
    if not recipients:
        logger.info("finalist notify skipped: group %s has no active members with emails", flag.group_id)
        return False

    subject = f"Congratulations — {flag.group.group_name} is a BIOTech Futures finalist"
    body = (
        f"Hi,\n\n"
        f"Your group ({flag.group.group_name}) has been selected as a finalist "
        f"for the BIOTech Futures Challenge. The BIOTech Futures team will be in "
        f"touch with details about presenting at the symposium.\n\n"
        f"Kind regards,\n"
        f"BIOTech Futures Team\n"
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:  # noqa: BLE001
        logger.exception("finalist notify failed: group=%s", flag.group_id)
        return False

    flag.notified = True
    flag.notified_at = timezone.now()
    flag.notified_by = actor
    flag.save(update_fields=["notified", "notified_at", "notified_by"])
    return True
