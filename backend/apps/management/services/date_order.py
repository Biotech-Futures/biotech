"""The year's dates in order (Management > Registration Dates, Challenge
Start and Submission Deadline): registration opens before the challenge
starts, and submissions close after both the challenge start and
registration's close. Each of those saves is checked against the others of
its year, both ways, so moving an earlier date can't break the order either.
A date that isn't set is never checked against. Each check gives the
reason a save is refused, or "" when it's in order."""
from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone


def statement_time(at, user) -> str:
    """``09/10/2026 at 16:12`` in the user's Profile timezone, as the site
    writes a time in a sentence."""
    try:
        zone = ZoneInfo(getattr(user, "timezone", "") or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    return at.astimezone(zone).strftime("%d/%m/%Y at %H:%M")


def _registration(year):
    from apps.users.models import RegistrationWindow

    return RegistrationWindow.objects.filter(year=year).first()


def _challenge_start(year):
    from ..models import ChallengeStart

    return ChallengeStart.objects.filter(year=year).values_list("starts_at", flat=True).first()


def _deadline(year):
    """The submission deadline in force, when it's this year's."""
    from apps.submissions.services import active_deadline

    deadline = active_deadline()
    if deadline is None or timezone.localtime(deadline.closes_at).year != year:
        return None
    return deadline.closes_at


def challenge_start_problem(starts_at, year: int, user) -> str:
    """After registration opens, and before submissions close."""
    if starts_at is None:
        return ""
    window = _registration(year)
    if window and window.opens_at and starts_at <= window.opens_at:
        return f"Challenge Start must be later than Registration Opens ({statement_time(window.opens_at, user)})."
    deadline = _deadline(year)
    if deadline and starts_at >= deadline:
        return f"Challenge Start must be earlier than the Submission Deadline ({statement_time(deadline, user)})."
    return ""


def deadline_problem(closes_at, user) -> str:
    """After the challenge starts, and after registration closes."""
    year = timezone.localtime(closes_at).year
    starts_at = _challenge_start(year)
    if starts_at and closes_at <= starts_at:
        return f"The Submission Deadline must be later than Challenge Start ({statement_time(starts_at, user)})."
    window = _registration(year)
    if window and window.closes_at and closes_at <= window.closes_at:
        return (
            "The Submission Deadline must be later than Registration Closes "
            f"({statement_time(window.closes_at, user)})."
        )
    return ""


def registration_problems(opens_at, closes_at, year: int, user) -> dict[str, str]:
    """Opening before the challenge starts, and closing before submissions
    close: each field's reason, or none."""
    problems = {}
    starts_at = _challenge_start(year)
    if opens_at and starts_at and opens_at >= starts_at:
        problems["opens_at"] = (
            f"Registration Opens must be earlier than Challenge Start ({statement_time(starts_at, user)})."
        )
    deadline = _deadline(year)
    if closes_at and deadline and closes_at >= deadline:
        problems["closes_at"] = (
            f"Registration Closes must be earlier than the Submission Deadline ({statement_time(deadline, user)})."
        )
    return problems
