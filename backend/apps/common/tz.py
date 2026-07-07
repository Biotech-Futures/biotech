"""Timezone helpers for matching geography scoring."""

from datetime import datetime, timezone as _tz
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@lru_cache(maxsize=512)
def utc_offset_hours(iana_name, default=0.0):
    """Current UTC offset in hours for an IANA tz name; ``default`` on unknown/empty.

    Used as a soft signal for mentor/student timezone proximity, so a fixed
    reference instant is fine (the DST-driven variation is well below the
    penalty granularity).
    """
    if not iana_name:
        return default
    try:
        tz = ZoneInfo(iana_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return default
    offset = datetime(2025, 1, 1, tzinfo=_tz.utc).astimezone(tz).utcoffset()
    return offset.total_seconds() / 3600.0 if offset else default
