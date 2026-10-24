from datetime import timedelta
import logging

from django.utils import timezone

from apps.system_logs.models import SystemLogEntry


def make_entry(*, age=timedelta(0), at=None, level=logging.WARNING, logger_name="apps.example", message="Something happened", **fields):
    """A stored log row, ``age`` old (or logged ``at``)."""
    return SystemLogEntry.objects.create(
        created_at=at or timezone.now() - age,
        level=level,
        level_name=logging.getLevelName(level),
        logger_name=logger_name,
        message=message,
        **fields,
    )
