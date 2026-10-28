"""QuickEmailVerification usage, for Team 4's analytics dashboard
(GET /api/v1/admin/email-verification/requests/).

Counts the requests recorded in ``EmailVerificationRequest`` (one per real
request to QEV) by day, key and outcome, with the credits they cost. Days are
UTC days, as the daily lookup cap counts them. History starts from the deploy
that added the table.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate

from apps.users.models import EmailVerificationRequest

# The range asked for when none is given, and the longest one allowed.
DEFAULT_DAYS = 30
MAX_DAYS = 366


class RangeError(ValueError):
    """A ``from``/``to`` the endpoint refuses, with the message to show."""


def _day(value: str | None, name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise RangeError(f"{name} must be a date like 2026-10-28.") from None


def usage_range(start: str | None, end: str | None, *, today: date | None = None) -> tuple[date, date]:
    """The days asked for: ``to`` (default today, UTC) and ``from`` (default
    the DEFAULT_DAYS up to it), at most MAX_DAYS long."""
    today = today or datetime.now(dt_timezone.utc).date()
    last = _day(end, "to") or today
    first = _day(start, "from") or last - timedelta(days=DEFAULT_DAYS - 1)
    if first > last:
        raise RangeError("from must be on or before to.")
    if (last - first).days + 1 > MAX_DAYS:
        raise RangeError(f"Ask for at most {MAX_DAYS} days at a time.")
    return first, last


def request_usage(first: date, last: date) -> dict:
    """Each day's requests and credits, by key and outcome, from ``first`` to
    ``last`` (UTC days, both included), and their totals."""
    since = datetime.combine(first, time.min, tzinfo=dt_timezone.utc)
    until = datetime.combine(last + timedelta(days=1), time.min, tzinfo=dt_timezone.utc)
    rows = (
        EmailVerificationRequest.objects.filter(requested_at__gte=since, requested_at__lt=until)
        .annotate(day=TruncDate("requested_at", tzinfo=dt_timezone.utc))
        .values("day", "key", "outcome")
        .annotate(requests=Count("id"), credits=Sum("credits"))
        .order_by("day", "key", "outcome")
    )
    days = [
        {
            "date": row["day"].isoformat(),
            "key": row["key"],
            "outcome": row["outcome"],
            "requests": row["requests"],
            "credits": row["credits"] or 0,
        }
        for row in rows
    ]
    # As the credits endpoint answers (apps.admin.services.email_verification).
    return {
        "msg": "Email verification requests retrieved successfully",
        "data": {
            "from": first.isoformat(),
            "to": last.isoformat(),
            "timezone": "UTC",
            "days": days,
            "totals": {
                "requests": sum(day["requests"] for day in days),
                "credits": sum(day["credits"] for day in days),
            },
        },
    }
