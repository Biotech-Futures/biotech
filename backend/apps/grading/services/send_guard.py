"""What the bulk emails sent from Management wait for, and how they are sent:
the finalist notification, the non-finalist invitation and non-submission
notice, and the two results emails.

Waiting: none goes out while a team can still submit, on the deadline or an
extension, grace hours included. Until then who submitted, who is a
finalist, and the marks can all still change.

Sending: pressing Send starts a run on the server that emails everyone due,
whether or not the page stays open, over several mail server connections at
once (``BULK_EMAIL_WORKERS``). One run at a time per email, so nobody is
emailed twice; the page shows the run's progress (see ``run_state``).
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from django.conf import settings
from django.core.mail import get_connection
from django.db import connection as db_connection
from django.db.models import F, Q
from django.utils import timezone

from apps.submissions.models import GroupExtension
from apps.submissions.services import active_deadline, current_cohort

from ..models import EmailSendRun
from .finalist_notify import SYMPOSIUM_TZ, _long_date

logger = logging.getLogger(__name__)

# The runs that aren't a system email's own key.
FINALIST_SEND = "finalist_notification"

# How long a run holds its email between sends: far past one team's send, so
# it only ever lapses for a run that died partway.
SEND_LEASE = timedelta(minutes=5)

UNREACHABLE = "Couldn't reach the mail server. Press Send again to email the rest."


def _long_time(moment: datetime) -> str:
    """"Friday, 17 October 2026, 11:59 PM", in Sydney time."""
    local = timezone.localtime(moment, SYMPOSIUM_TZ)
    return f"{_long_date(local.date())}, {int(f'{local:%I}')}:{local:%M} {local:%p}"


def submissions_open_reason() -> str:
    """Why sending waits for submissions to close, or "" once they have: the
    deadline, then the last of this year's extensions, grace hours included."""
    now = timezone.now()
    deadline = active_deadline()
    if deadline is not None:
        until = deadline.closes_at + timedelta(hours=deadline.grace_hours)
        if now <= until:
            return f"Submissions are open until {_long_time(until)} (Sydney time). Send this once they close."
    ends = [
        end
        for extension in GroupExtension.objects.filter(
            revoked_at__isnull=True, group__year=current_cohort(), group__deleted_at__isnull=True,
        )
        if (end := extension.extended_until + timedelta(hours=extension.grace_hours)) >= now
    ]
    if ends:
        return (
            f"A team's extension is open until {_long_time(max(ends))} (Sydney time). "
            "Send this once every extension has ended."
        )
    return ""


class AlreadySending(Exception):
    """A run is already sending this email."""


@dataclass
class Work:
    """One team's or supervisor's email: how many people it goes to, and
    sending it. ``send(connection, cache)`` gives how many got it and whether
    everyone did (only then is it recorded as emailed); ``cache`` lasts one
    worker's share of the run, e.g. for templates read once."""

    people: int
    send: Callable[[object, dict], tuple[int, bool]]


def _take(key: str, **fields) -> bool:
    """Hold ``key``'s email: a single conditional update, so of two requests
    racing for it only one gets it."""
    now = timezone.now()
    EmailSendRun.objects.get_or_create(key=key)
    return bool(
        EmailSendRun.objects.filter(key=key)
        .filter(Q(held_until__isnull=True) | Q(held_until__lt=now))
        .update(held_until=now + SEND_LEASE, **fields)
    )


@contextmanager
def holding_send(key: str):
    """Hold ``key``'s email for one send made in the request itself (flagging
    a finalist with notify). Raises ``AlreadySending`` while a run holds it."""
    if not _take(key):
        raise AlreadySending
    try:
        yield
    finally:
        EmailSendRun.objects.filter(key=key).update(held_until=None)


def start_run(key: str, actor, work: list[Work]) -> None:
    """Start a run emailing every item of ``work``, on the server, so the page
    can be closed: the items are shared across ``BULK_EMAIL_WORKERS`` threads,
    each with its own mail server connection. Raises ``AlreadySending`` while
    another run is going."""
    if not _take(
        key, started_at=timezone.now(), started_by=actor, finished_at=None,
        due=sum(item.people for item in work), emailed=0, failed=0, error="",
    ):
        raise AlreadySending
    if settings.BULK_EMAIL_DISPATCH_SYNC:
        _run(key, work, workers=1, threaded=False)
    else:
        threading.Thread(
            target=_run, args=(key, work),
            kwargs={"workers": max(1, settings.BULK_EMAIL_WORKERS), "threaded": True},
            daemon=True, name=f"email-run-{key}",
        ).start()


def _run(key: str, work: list[Work], *, workers: int, threaded: bool) -> None:
    try:
        shares = [share for share in (work[i::workers] for i in range(workers)) if share]
        if threaded:
            threads = [threading.Thread(target=_work, args=(key, share, True), daemon=True) for share in shares]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        else:
            for share in shares:
                _work(key, share, False)
    except Exception:  # noqa: BLE001
        logger.exception("email run %s failed", key)
    finally:
        EmailSendRun.objects.filter(key=key).update(held_until=None, finished_at=timezone.now())
        if threaded:
            db_connection.close()


def _work(key: str, items: list[Work], threaded: bool) -> None:
    """One worker's share of a run, over one mail server connection."""
    connection = get_connection(fail_silently=False)
    try:
        try:
            connection.open()
        except Exception as exc:  # noqa: BLE001
            logger.error("email run %s: mail server unreachable error=%s", key, type(exc).__name__)
            EmailSendRun.objects.filter(key=key).update(failed=F("failed") + len(items), error=UNREACHABLE)
            return
        cache: dict = {}
        for item in items:
            try:
                sent, whole = item.send(connection, cache)
            except Exception:  # noqa: BLE001
                logger.exception("email run %s: an email failed", key)
                sent, whole = 0, False
            EmailSendRun.objects.filter(key=key).update(
                emailed=F("emailed") + (sent if whole else 0),
                failed=F("failed") + (0 if whole else 1),
                held_until=timezone.now() + SEND_LEASE,
            )
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass
        if threaded:
            db_connection.close()


def run_state(key: str) -> dict:
    """Whether ``key``'s email is sending now, and its run's progress (the
    one going, or the last): people due and emailed, teams or supervisors
    not emailed in full, and why it stopped short, if it did."""
    run = EmailSendRun.objects.filter(key=key).first()
    sending = bool(run and run.held_until and run.held_until >= timezone.now())
    return {
        "sending": sending,
        "run": {
            "due": run.due,
            "emailed": run.emailed,
            "failed": run.failed,
            "error": run.error,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        } if run and run.started_at else None,
    }
