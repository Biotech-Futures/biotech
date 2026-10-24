"""The timed jobs, run by the backend itself rather than by GitHub's schedules
(which ran hours late): the bounce check, waiting emails, the unread
messages digest, auto-submit, RSVP reminders and the daily reminder emails.

Off unless ``SCHEDULER_ENABLED`` is set. Each web server process then starts
one timer, on its first request (never in tests or management commands). The
timer wakes every minute and runs each job that's due, calling the same code
its endpoint calls, so the GitHub workflows can still start any of them by
hand.

A job is due once per slot: the start of its 10 minutes, quarter hour, hour
or day (UTC). A process runs a slot only if it claims it first, with one
conditional update on its ``ScheduledJobRun`` row, so each slot runs once
however many processes and instances there are, and a slot missed while the
backend was asleep or restarting runs at the next tick. A job's first slot is
the one after the scheduler first sees it, so switching it on sends nothing
straight away.
"""
from __future__ import annotations

import importlib
import logging
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db import IntegrityError, close_old_connections, connection
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

TICK_SECONDS = 60
DAY = 24 * 60


@dataclass(frozen=True)
class Job:
    name: str
    label: str
    # How often, in minutes (DAY for daily), and when in each period it's due:
    # minutes past the period's start, e.g. 3 for :03, or 6 * 60 + 41 daily.
    every: int
    at: int
    # What it runs: "module:function", the same as its endpoint runs.
    run: str


# The frequent ones as the GitHub workflows ran them, at their odd minutes;
# the daily ones on the hour, one after another (UTC).
JOBS: tuple[Job, ...] = (
    Job("bounce_check", "Bounced email check", 10, 3,
        "apps.management.services.bounce_check:start_check"),
    Job("waiting_emails", "Waiting emails", 10, 7, "apps.services.waiting_email:queue_waiting"),
    Job("unread_digest", "Unread messages digest", 15, 7, "apps.chat.services.digest:dispatch_unread_digest"),
    Job("auto_submit", "Submission auto-submit", 60, 7, "apps.submissions.autosubmit:auto_submit_due"),
    Job("rsvp_reminders", "RSVP reminders", 60, 23, "apps.management.scheduler:queue_rsvp_reminders"),
    Job("submission_reminders", "Submission reminders", DAY, 21 * 60,
        "apps.submissions.reminders:queue_reminder_runs"),
    Job("guardian_details_reminders", "Guardian details reminders", DAY, 19 * 60,
        "apps.management.scheduler:queue_guardian_details_reminders"),
    Job("guardian_consent_reminders", "Guardian consent reminders", DAY, 18 * 60,
        "apps.management.scheduler:queue_guardian_consent_reminders"),
    Job("supervisor_registration_status", "Supervisor registration status", DAY, 20 * 60,
        "apps.management.scheduler:queue_supervisor_registration_status"),
)


# --- the jobs that only queue their emails, as their endpoints do -----------

def _queue(key: str) -> str:
    from apps.management.services.send_guard import queue_job

    queue_job(key)
    return "queued"


def queue_rsvp_reminders():
    return _queue("rsvp_reminder")


def queue_guardian_details_reminders():
    return _queue("guardian_details_request")


def queue_guardian_consent_reminders():
    return _queue("guardian_consent_request")


def queue_supervisor_registration_status():
    return _queue("supervisor_registration_status")


# --- slots and claims --------------------------------------------------------

def slot_for(job: Job, now: datetime) -> datetime:
    """The start of ``job``'s slot that ``now`` falls in (UTC)."""
    minutes = int(now.timestamp() // 60)
    start = (minutes - job.at) // job.every * job.every + job.at
    return datetime.fromtimestamp(start * 60, tz=dt_timezone.utc)


def claim(job: Job, slot: datetime, now: datetime) -> bool:
    """Whether this process gets to run ``job``'s ``slot``: one conditional
    update, so exactly one process does. A job seen for the first time is
    marked as having run this slot, so it starts at the next one."""
    from .models import ScheduledJobRun

    if not ScheduledJobRun.objects.filter(name=job.name).exists():
        try:
            ScheduledJobRun.objects.create(name=job.name, last_slot=slot)
        except IntegrityError:
            pass
        return False
    return bool(
        ScheduledJobRun.objects.filter(name=job.name)
        .filter(Q(last_slot__isnull=True) | Q(last_slot__lt=slot))
        .update(last_slot=slot, last_started_at=now)
    )


def _function(path: str):
    module, name = path.split(":")
    return getattr(importlib.import_module(module), name)


def tick(now: datetime | None = None) -> list[str]:
    """Run every job whose slot is due and unclaimed. One failing is logged
    and noted, and never stops the rest. Returns the names of those run."""
    from .models import ScheduledJobRun

    now = now or timezone.now()
    ran = []
    for job in JOBS:
        if not claim(job, slot_for(job, now), now):
            continue
        ok, error = True, ""
        try:
            _function(job.run)()
        except Exception as exc:  # noqa: BLE001
            ok, error = False, f"{type(exc).__name__}: {exc}"[:300]
            logger.exception("scheduled_job.failed name=%s", job.name)
        ScheduledJobRun.objects.filter(name=job.name).update(
            last_finished_at=timezone.now(), last_ok=ok, last_error=error,
        )
        ran.append(job.name)
    return ran


# --- the timer ----------------------------------------------------------------

_started = False
_start_lock = threading.Lock()


def enabled() -> bool:
    """Switched on, and not a test run."""
    executable = sys.argv[0].rsplit("/", 1)[-1]
    return (
        bool(getattr(settings, "SCHEDULER_ENABLED", False))
        and executable not in {"pytest", "py.test"}
        and "test" not in sys.argv[1:2]
    )


def _loop() -> None:
    while True:
        # Just after the minute turns, so a slot starting then is due.
        time.sleep(TICK_SECONDS - time.time() % TICK_SECONDS + 1)
        close_old_connections()
        try:
            tick()
        except Exception:  # noqa: BLE001
            logger.exception("scheduled_job.tick_failed")
        finally:
            connection.close()


def ensure_started() -> None:
    """Start this process's timer, once, when switched on."""
    global _started
    if _started or not enabled():
        return
    with _start_lock:
        if _started:
            return
        _started = True
        threading.Thread(target=_loop, name="scheduled-jobs", daemon=True).start()
        logger.info("scheduled_jobs.started")


class SchedulerStartMiddleware:
    """Starts the timer on a web server process's first request: never in a
    management command, and after any forking of the server's processes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not _started:
            ensure_started()
        return self.get_response(request)


def job_states() -> dict:
    """Whether the timer is on, and each job's schedule and last run, for
    Management > Email Checks."""
    from .models import ScheduledJobRun

    runs = {run.name: run for run in ScheduledJobRun.objects.all()}

    def iso(value):
        return value.isoformat() if value else None

    jobs = []
    for job in JOBS:
        run = runs.get(job.name)
        jobs.append({
            "name": job.name,
            "label": job.label,
            "every": job.every,
            "at": job.at,
            "lastStartedAt": iso(run.last_started_at) if run else None,
            "lastFinishedAt": iso(run.last_finished_at) if run else None,
            "ok": run.last_ok if run else None,
            "error": run.last_error if run else "",
        })
    return {"enabled": bool(getattr(settings, "SCHEDULER_ENABLED", False)), "jobs": jobs}
