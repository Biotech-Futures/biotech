"""Deadline rules for team submissions.

Everything that needs to know "can this team still submit?" goes through
:func:`deadline_for_group` so the rule lives in exactly one place.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone

from .models import Deadline, GroupExtension


@dataclass(frozen=True)
class DeadlineInfo:
    """When a particular team closes, and whether that came from an extension.

    ``closes_at`` is the date the team is shown. ``enforced_until`` is when
    writes actually stop being accepted, which may be later: the programme
    announces a single deadline but quietly accepts submissions for a further
    grace period so nobody in a far-behind timezone loses part of their
    deadline day. An extension replaces both.
    """

    closes_at: datetime | None
    is_extended: bool
    enforced_until: datetime | None = None

    @property
    def is_open(self) -> bool:
        # No deadline means closed, not open forever: a missing row is far
        # likelier to be a misconfiguration than an intention.
        cutoff = self.enforced_until or self.closes_at
        if cutoff is None:
            return False
        return timezone.now() <= cutoff

    @property
    def is_in_grace(self) -> bool:
        """Past the announced date, but still being accepted."""
        if self.closes_at is None or self.enforced_until is None:
            return False
        return self.closes_at < timezone.now() <= self.enforced_until


def active_deadline() -> Deadline | None:
    """The deadline currently in force, or None if none is configured."""
    return Deadline.objects.filter(is_active=True).order_by("-created_at").first()


def current_cohort() -> int:
    """The competition year an entry belongs to.

    Read from the active deadline rather than the clock, and deliberately *not*
    from a team's own extended date. Both matter:

    * A submission made inside a grace window that crosses New Year still
      belongs to the year the competition closed in, so the clock is wrong.
    * A team granted an extension into the following January is still competing
      in the same cohort as everyone else, so the per-team date is wrong too.

    Falls back to the current year only when no deadline is configured at all,
    which is a misconfiguration rather than a normal state.
    """
    deadline = active_deadline()
    if deadline is not None:
        return timezone.localtime(deadline.closes_at).year
    return timezone.localtime().year


def deadline_for_group(group_id: int) -> DeadlineInfo:
    """Resolve the closing time that applies to one team.

    An extension wins outright rather than being compared against the standard
    deadline. Applying the granted date exactly as entered keeps the admin
    screen predictable — the date shown is the date enforced — at the cost of
    letting a mistyped earlier date shorten a team's window.

    An extension also applies when no standard deadline exists at all, since it
    is an explicit per-team decision rather than a fallback.
    """
    extension = GroupExtension.objects.filter(group_id=group_id).first()
    if extension is not None:
        # An extension is a granted date, not an announced one, so no further
        # grace is added on top — what the admin entered is what applies.
        return DeadlineInfo(
            closes_at=extension.extended_until,
            is_extended=True,
            enforced_until=extension.extended_until,
        )

    deadline = active_deadline()
    if deadline is None:
        return DeadlineInfo(closes_at=None, is_extended=False, enforced_until=None)

    return DeadlineInfo(
        closes_at=deadline.closes_at,
        is_extended=False,
        enforced_until=deadline.closes_at + timedelta(hours=deadline.grace_hours),
    )
