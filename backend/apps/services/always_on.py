"""Whether Azure's Always On is keeping the backend awake.

While Always On is on, Azure itself calls the backend every few minutes, the
calls naming themselves ``AlwaysOn``. ``AlwaysOnPingMiddleware`` notes the
latest one's time on the System Emails settings row; ``always_on_state``
reads it for the System Emails page, which warns when the calls have stopped:
with Always On off the backend falls asleep when no one is using it, so its
timed emails go late or not at all.
"""
from __future__ import annotations

import logging
import os
from datetime import timedelta

from django.db import DatabaseError
from django.utils import timezone

logger = logging.getLogger(__name__)

# What Azure's calls name themselves (their User-Agent), in any casing.
PING_AGENT = "alwayson"
# The row is written at most this often, however often Azure calls.
WRITE_EVERY = timedelta(minutes=1)
# Azure calls every few minutes; none for this long means it's off.
QUIET_FOR = timedelta(minutes=20)

ON, OFF, CHECKING, NOT_AZURE = "on", "off", "checking", "not_azure"

# When this process last wrote a call, so most calls cost nothing.
_last_written = None


def on_azure() -> bool:
    """Whether the backend is running as an Azure App Service."""
    return bool(os.environ.get("WEBSITE_SITE_NAME"))


def note_ping(now=None) -> None:
    """Note that Azure's Always On just called. Never raises."""
    global _last_written
    from .models import SystemEmailSettings

    now = now or timezone.now()
    if _last_written is not None and now - _last_written < WRITE_EVERY:
        return
    _last_written = now
    try:
        SystemEmailSettings.get()
        SystemEmailSettings.objects.filter(pk=SystemEmailSettings.SINGLETON_PK).update(always_on_seen_at=now)
    except DatabaseError:
        logger.warning("always_on.note_failed")


def always_on_state(now=None) -> dict:
    """``{"state", "lastSeenAt"}``: ``on`` (Azure called within QUIET_FOR),
    ``off`` (it hasn't for longer), ``checking`` (watching for less than
    QUIET_FOR, with no call yet) or ``not_azure`` (running elsewhere, as on a
    developer's machine, where there's nothing to tell)."""
    from .models import SystemEmailSettings

    if not on_azure():
        return {"state": NOT_AZURE, "lastSeenAt": None}
    now = now or timezone.now()
    row = SystemEmailSettings.get()
    seen = row.always_on_seen_at
    last_seen = seen.isoformat() if seen else None
    if seen is not None and now - seen <= QUIET_FOR:
        return {"state": ON, "lastSeenAt": last_seen}
    started = row.always_on_watch_started_at
    if started is None:
        # The first look: no call could have come yet.
        SystemEmailSettings.objects.filter(pk=SystemEmailSettings.SINGLETON_PK).update(
            always_on_watch_started_at=now,
        )
        started = now
    if seen is None and now - started < QUIET_FOR:
        return {"state": CHECKING, "lastSeenAt": None}
    return {"state": OFF, "lastSeenAt": last_seen}


class AlwaysOnPingMiddleware:
    """First of all middleware: notes each call from Azure's Always On,
    whatever its address, before anything can redirect or refuse it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if PING_AGENT in request.META.get("HTTP_USER_AGENT", "").lower():
            note_ping()
        return self.get_response(request)
