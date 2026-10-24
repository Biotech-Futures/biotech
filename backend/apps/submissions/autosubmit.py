"""Submitting complete drafts that teams left unsubmitted once their cut-off has passed.

Run on a schedule; safe to re-run, as an entry submitted once is never touched again.
It only looks from the announced deadline until this year's finalist emails go out.
"""
import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.grading.models import FinalistFlag
from apps.live.broadcast import notify_changed

from . import coedit
from .models import Submission
from .services import active_deadline, current_cohort, deadline_for_group
from .submitting import complete_submission, delete_superseded, is_complete

logger = logging.getLogger(__name__)


def in_season(now=None) -> bool:
    """Past the announced deadline (an extension always ends later), and this
    year's finalist emails haven't gone out. A flag a bounce turned back to
    unnotified keeps its ``notified_at``, so still counts as sent."""
    now = now or timezone.now()
    deadline = active_deadline()
    if deadline is None or now <= deadline.closes_at:
        return False
    return not FinalistFlag.objects.filter(
        Q(notified=True) | Q(notified_at__isnull=False), group__year=current_cohort(),
    ).exists()


def _past_cutoff(group_id: int, now) -> bool:
    """The team's own cut-off, including its grace period or extension, has passed."""
    info = deadline_for_group(group_id)
    cutoff = info.enforced_until or info.closes_at
    return cutoff is not None and now > cutoff


def entries_due(now=None, *, flush: bool = True) -> list[Submission]:
    """This round's never-submitted, complete drafts whose team is past its
    cut-off; none outside ``in_season``."""
    now = now or timezone.now()
    if not in_season(now):
        return []
    drafts = Submission.objects.filter(
        submitted_at__isnull=True,
        cohort=current_cohort(),
        group__deleted_at__isnull=True,
    ).select_related("group")
    due = []
    for entry in drafts:
        if not _past_cutoff(entry.group_id, now):
            continue
        # Co-edited text reaches the entry before it is judged complete.
        if flush and coedit.enabled():
            coedit.flush(entry.group_id)
            entry.refresh_from_db()
        if is_complete(entry):
            due.append(entry)
    return due


def auto_submit_due(now=None, *, dry_run: bool = False) -> dict:
    """Submit every entry due; returns the teams submitted, by name."""
    now = now or timezone.now()
    submitted = []
    for entry in entries_due(now, flush=not dry_run):
        if dry_run:
            submitted.append(entry.group.group_name)
            continue
        try:
            with transaction.atomic():
                # Checked again under the lock, in case a teammate acted meanwhile.
                current = Submission.objects.select_for_update().get(pk=entry.pk)
                if current.submitted_at is not None or not is_complete(current):
                    continue
                superseded = complete_submission(current, None, automated=True)
            delete_superseded(current, superseded)
            submitted.append(entry.group.group_name)
            notify_changed("submission", entry.group_id, "submitted")
        except Exception:  # noqa: BLE001
            logger.exception("submissions.auto_submit_failed group=%s", entry.group_id)
    return {"submitted": submitted, "dry_run": dry_run}
