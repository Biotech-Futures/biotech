"""Keeping the System Logs table to a bounded size."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import SystemLogEntry

# Rows deleted per statement, so a large prune never holds a long lock.
PRUNE_BATCH_SIZE = 5000


def prune(days: int | None = None, *, batch_size: int = PRUNE_BATCH_SIZE) -> int:
    """Delete log rows older than ``days`` (default ``SYSTEM_LOG_RETENTION_DAYS``)
    in batches, and return how many were deleted."""
    if days is None:
        days = settings.SYSTEM_LOG_RETENTION_DAYS
    if days < 1:
        # 0 would delete everything, which is never what a schedule means.
        raise ValueError("Retention must be at least 1 day.")
    cutoff = timezone.now() - timedelta(days=days)
    deleted = 0
    while True:
        ids = list(
            SystemLogEntry.objects.filter(created_at__lt=cutoff)
            .order_by()
            .values_list("id", flat=True)[:batch_size]
        )
        if not ids:
            return deleted
        SystemLogEntry.objects.filter(id__in=ids).delete()
        deleted += len(ids)
