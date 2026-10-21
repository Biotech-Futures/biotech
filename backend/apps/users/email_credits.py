"""The QuickEmailVerification credit balance, as the service reports it.

QEV gives the credits left in the ``X-QEV-Remaining-Credits`` header of each
answer. ``record_remaining`` stores that number after every real (not
sandbox) lookup instead of counting credits ourselves. The balance row is
locked while it changes, so two checks finishing at once can't both act on
the same reading. A reading that can't be used is ignored and the last known
balance kept. Nothing here raises: a check never fails because of it.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from .models import EmailVerificationCredits

logger = logging.getLogger(__name__)

CREDITS_HEADER = "X-QEV-Remaining-Credits"

# Whether an unusable header has already been logged since the last good one,
# so a run of them is logged once, not once per lookup.
_unreadable_logged = False


def _credits(value):
    """The header's whole number of credits, or None if it isn't one."""
    text = str(value if value is not None else "").strip()
    return int(text) if text.isdigit() else None


def credits_in(headers):
    """The credits left according to one QEV answer's ``headers``, or None if
    they don't say (missing, unreadable or not a whole number)."""
    try:
        return _credits(headers.get(CREDITS_HEADER))
    except Exception:  # noqa: BLE001 - headers that can't be read are just unusable
        return None


# The keys whose balance is kept: the paid one (QEV_PAID_API_KEY), which
# alerts follow, and the free one (QEV_API_KEY), kept for display only.
FREE, PAID = "free", "paid"


def record_remaining(headers, key: str = PAID) -> None:
    """Store the balance one QEV answer's ``headers`` give for ``key``. Only
    the paid key's is checked against the alert levels. Never raises."""
    global _unreadable_logged
    remaining = credits_in(headers)
    if remaining is None:
        if not _unreadable_logged:
            logger.warning("email_credits.header_unusable header=%s", CREDITS_HEADER)
            _unreadable_logged = True
        return
    _unreadable_logged = False

    try:
        if key == FREE:
            EmailVerificationCredits.get()
            EmailVerificationCredits.objects.filter(pk=EmailVerificationCredits.SINGLETON_PK).update(
                free_remaining=remaining, free_updated_at=timezone.now(),
            )
            logger.info("email_credits.recorded key=free remaining=%s", remaining)
            return
        with transaction.atomic():
            EmailVerificationCredits.get()
            credits = EmailVerificationCredits.objects.select_for_update().get(
                pk=EmailVerificationCredits.SINGLETON_PK,
            )
            credits.remaining = remaining
            credits.updated_at = timezone.now()
            # On the same locked row, so two readings can't both send an alert.
            from .email_credit_alerts import alert_if_low
            alert_if_low(credits)
            credits.save(update_fields=["remaining", "updated_at", "alerted_thresholds"])
    except Exception as exc:  # noqa: BLE001 - a balance that can't be saved mustn't stop a check
        logger.error("email_credits.record_failed error=%s", type(exc).__name__)
        return
    logger.info("email_credits.recorded remaining=%s", remaining)
