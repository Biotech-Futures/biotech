"""Low-credit alerts for QuickEmailVerification.

When the balance drops below a level in QEV_LOW_CREDIT_THRESHOLDS (500 and
100), one email goes to QEV_ALERT_EMAIL. Each level alerts once; a reading
that crosses several at once sends a single email, for the lowest. Once the
balance is back at or above a level (a top-up), that level can alert again.
The email type is locked, so it can't be switched off on System Emails.
"""
from __future__ import annotations

import logging

from django.conf import settings

from apps.services.system_email import SENT, send_system_email, sender_connection, sender_for

logger = logging.getLogger(__name__)

ALERT_EMAIL_TYPE = "email_credits_low"

# Seconds the alert waits on each mail server operation, instead of the
# site-wide EMAIL_TIMEOUT: it's sent while the credits row is locked, and a
# hung mail server mustn't hold that lock for long.
ALERT_SMTP_TIMEOUT_SECONDS = 5


def _thresholds() -> list[int]:
    return sorted({int(level) for level in getattr(settings, "QEV_LOW_CREDIT_THRESHOLDS", (500, 100))}, reverse=True)


def _send(remaining: int, threshold: int) -> bool:
    """Send the alert now; True once the mail server has taken it. Not in the
    background: this already runs on the verification worker, and waiting is
    what lets a mail server failure leave the level unmarked for a retry."""
    try:
        # The mailbox System Emails sends it from, signed in with a short timeout.
        sender = sender_for(ALERT_EMAIL_TYPE)
        status = send_system_email(
            ALERT_EMAIL_TYPE,
            getattr(settings, "QEV_ALERT_EMAIL", "info@biotechfutures.org"),
            {"REMAINING": remaining, "THRESHOLD": threshold},
            background=False,
            from_email=sender.from_email,
            connection=sender_connection(sender, timeout=ALERT_SMTP_TIMEOUT_SECONDS),
        )
    except Exception as exc:  # noqa: BLE001 - an alert that can't go is tried again next reading
        logger.error("email_credits.alert_failed threshold=%s error=%s", threshold, type(exc).__name__)
        return False
    if status != SENT:
        logger.error("email_credits.alert_not_sent threshold=%s status=%s", threshold, status)
        return False
    logger.info("email_credits.alert_sent threshold=%s remaining=%s", threshold, remaining)
    return True


def alert_if_low(credits) -> None:
    """Called with the balance row locked and its new ``remaining`` set:
    forget levels the balance is back up to, and alert once for the lowest
    level newly dropped below, marking every level crossed. A level whose
    alert can't be sent stays unmarked, so the next reading tries again.
    Updates ``credits.alerted_thresholds``; the caller saves. Never raises."""
    try:
        remaining = credits.remaining
        alerted = {level for level in credits.alerted_thresholds if remaining < level}
        crossed = [level for level in _thresholds() if remaining < level and level not in alerted]
        # Sent before the caller saves the row: if that save fails, the next
        # reading sends the alert again. A duplicate alert is acceptable; a
        # lost one is not.
        if crossed and _send(remaining, min(crossed)):
            alerted.update(crossed)
        credits.alerted_thresholds = sorted(alerted, reverse=True)
    except Exception as exc:  # noqa: BLE001 - an alert problem mustn't stop the balance being kept
        logger.error("email_credits.alert_check_failed error=%s", type(exc).__name__)
