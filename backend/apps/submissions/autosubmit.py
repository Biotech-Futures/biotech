"""Submitting complete drafts that teams left unsubmitted once their cut-off has passed.

Run on a schedule; safe to re-run, as an entry submitted once is never touched again.
"""
import logging

from django.db import transaction
from django.utils import timezone

from apps.live.broadcast import notify_changed

from .models import Submission
from .services import current_cohort, deadline_for_group
from .submitting import complete_submission, delete_superseded, is_complete

logger = logging.getLogger(__name__)


def _past_cutoff(group_id: int, now) -> bool:
    """The team's own cut-off, including its grace period or extension, has passed."""
    info = deadline_for_group(group_id)
    cutoff = info.enforced_until or info.closes_at
    return cutoff is not None and now > cutoff


def entries_due(now=None) -> list[Submission]:
    """This round's never-submitted, complete drafts whose team is past its cut-off."""
    now = now or timezone.now()
    drafts = Submission.objects.filter(
        submitted_at__isnull=True,
        cohort=current_cohort(),
        group__deleted_at__isnull=True,
    ).select_related("group")
    return [entry for entry in drafts if is_complete(entry) and _past_cutoff(entry.group_id, now)]


def auto_submit_due(now=None, *, dry_run: bool = False) -> dict:
    """Submit every entry due; returns the teams submitted, by name."""
    now = now or timezone.now()
    submitted = []
    for entry in entries_due(now):
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
