"""The QuickEmailVerification credit balance, for admins
(GET /api/v1/admin/email-verification/credits/).

One block per key: the free key (QEV_API_KEY, tried first) and the paid key
(QEV_PAID_API_KEY, used when the free one is out of credit, and the one the
low-credit alerts follow). Whether a key is set is shown; the key never is.

Read-only: the balance row is written only by the verification service
(apps.users.email_credits and email_verification), so reading it never
creates it.
"""
from django.conf import settings
from django.utils import timezone

from apps.users.email_verification import retry_at
from apps.users.models import EmailVerificationCredits


def _iso(value):
    return value.isoformat() if value else None


def _key_block(setting: str, remaining, updated_at, exhausted_at, now) -> dict:
    """One key's state: whether it's set, its balance as last reported, and
    whether it's out of credit (until ``retryAt``)."""
    retry = retry_at(exhausted_at) if exhausted_at else None
    return {
        "configured": bool(getattr(settings, setting, "")),
        "remaining": remaining,
        "updatedAt": _iso(updated_at),
        "exhausted": retry is not None and now < retry,
        "exhaustedAt": _iso(exhausted_at),
        "retryAt": _iso(retry),
    }


def get_credit_balance() -> dict:
    """Each key's balance as QEV last reported it (``remaining`` is None until
    it has) and whether it's out of credit; the alert levels and which have
    been sent for the paid key; and today's lookups against the daily cap."""
    credits = EmailVerificationCredits.objects.filter(pk=EmailVerificationCredits.SINGLETON_PK).first()
    now = timezone.now()
    # A count kept for an earlier day is no longer today's.
    counted_today = credits is not None and credits.lookups_on == now.date()
    return {
        "msg": "Email verification credits retrieved successfully",
        "data": {
            "free": _key_block(
                "QEV_API_KEY",
                credits.free_remaining if credits else None,
                credits.free_updated_at if credits else None,
                credits.free_exhausted_at if credits else None,
                now,
            ),
            "paid": {
                **_key_block(
                    "QEV_PAID_API_KEY",
                    credits.remaining if credits else None,
                    credits.updated_at if credits else None,
                    credits.paid_exhausted_at if credits else None,
                    now,
                ),
                "alertedThresholds": list(credits.alerted_thresholds) if credits else [],
            },
            "thresholds": sorted(
                {int(level) for level in getattr(settings, "QEV_LOW_CREDIT_THRESHOLDS", (500, 100))},
                reverse=True,
            ),
            "lookupsToday": credits.lookups_today if counted_today else 0,
            "lookupsOn": _iso(credits.lookups_on) if credits else None,
            # 0: no daily limit.
            "dailyCap": int(getattr(settings, "QEV_DAILY_LOOKUP_CAP", 0)),
            "sandbox": bool(getattr(settings, "QEV_USE_SANDBOX", False)),
        },
    }
