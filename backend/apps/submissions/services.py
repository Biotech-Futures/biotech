"""Deadline rules for team submissions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone

from .models import Deadline, GroupExtension


@dataclass(frozen=True)
class DeadlineInfo:
    """``closes_at`` is the date shown; ``enforced_until`` adds the unannounced grace period."""

    closes_at: datetime | None
    is_extended: bool
    enforced_until: datetime | None = None

    @property
    def is_open(self) -> bool:
        # No deadline configured counts as closed.
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
    return Deadline.objects.filter(is_active=True).order_by("-created_at").first()


def current_cohort() -> int:
    """The competition year, from the active deadline so grace windows and extensions stay in it."""
    deadline = active_deadline()
    if deadline is not None:
        return timezone.localtime(deadline.closes_at).year
    return timezone.localtime().year


def deadline_for_group(group_id: int) -> DeadlineInfo:
    """The closing time for one team; an extension replaces the standard deadline outright."""
    extension = GroupExtension.objects.filter(group_id=group_id).first()
    if extension is not None:
        # An extension carries its own quiet grace hours rather than
        # inheriting the global deadline's — the admin granting it decides
        # both the shown date and the buffer.
        return DeadlineInfo(
            closes_at=extension.extended_until,
            is_extended=True,
            enforced_until=extension.extended_until
            + timedelta(hours=extension.grace_hours),
        )

    deadline = active_deadline()
    if deadline is None:
        return DeadlineInfo(closes_at=None, is_extended=False, enforced_until=None)

    return DeadlineInfo(
        closes_at=deadline.closes_at,
        is_extended=False,
        enforced_until=deadline.closes_at + timedelta(hours=deadline.grace_hours),
    )
