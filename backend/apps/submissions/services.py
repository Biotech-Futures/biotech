"""Deadline rules for team submissions.

Everything that needs to know "can this team still submit?" goes through
:func:`deadline_for_group` so the rule lives in exactly one place.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from .models import Deadline, GroupExtension


@dataclass(frozen=True)
class DeadlineInfo:
    """When a particular team closes, and whether that came from an extension."""

    closes_at: datetime | None
    is_extended: bool

    @property
    def is_open(self) -> bool:
        # No configured deadline means closed rather than open-forever: a
        # missing or deactivated Deadline row is far more likely to be a
        # misconfiguration than an intention to accept entries indefinitely.
        if self.closes_at is None:
            return False
        return timezone.now() <= self.closes_at


def active_deadline() -> Deadline | None:
    """The deadline currently in force, or None if none is configured."""
    return Deadline.objects.filter(is_active=True).order_by("-created_at").first()


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
        return DeadlineInfo(closes_at=extension.extended_until, is_extended=True)

    deadline = active_deadline()
    return DeadlineInfo(
        closes_at=deadline.closes_at if deadline is not None else None,
        is_extended=False,
    )
