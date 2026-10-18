"""The QuickEmailVerification credit balance, for admins
(GET /api/v1/admin/email-verification/credits/).

Read-only: the balance row is written only by the verification service
(apps.users.email_credits), so reading it never creates it.
"""
from django.conf import settings
from django.utils import timezone

from apps.users.models import EmailVerificationCredits


def get_credit_balance() -> dict:
    """The balance as QEV last reported it (``remaining`` is None until it
    has), the alert levels and which have been sent, and today's lookups
    against the daily cap."""
    credits = EmailVerificationCredits.objects.filter(pk=EmailVerificationCredits.SINGLETON_PK).first()
    today = timezone.now().date()
    # A count kept for an earlier day is no longer today's.
    counted_today = credits is not None and credits.lookups_on == today
    return {
        "msg": "Email verification credits retrieved successfully",
        "data": {
            "remaining": credits.remaining if credits else None,
            "updatedAt": credits.updated_at.isoformat() if credits and credits.updated_at else None,
            "alertedThresholds": list(credits.alerted_thresholds) if credits else [],
            "thresholds": sorted(
                {int(level) for level in getattr(settings, "QEV_LOW_CREDIT_THRESHOLDS", (500, 100))},
                reverse=True,
            ),
            "lookupsToday": credits.lookups_today if counted_today else 0,
            "lookupsOn": credits.lookups_on.isoformat() if credits and credits.lookups_on else None,
            "dailyCap": int(getattr(settings, "QEV_DAILY_LOOKUP_CAP", 600)),
            "sandbox": bool(getattr(settings, "QEV_USE_SANDBOX", False)),
        },
    }
