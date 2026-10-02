"""What the bulk emails sent from Management wait for, and how they are sent:
the finalist notification, the non-finalist invitation and non-submission
notice, and the two results emails.

Waiting: none goes out while a team can still submit, on the deadline or an
extension, grace hours included. Until then who submitted, who is a
finalist, and the marks can all still change.

Sending: pressing Send starts a run on the server that emails everyone due,
whether or not the page stays open, over a few mail server connections at
once (``BULK_EMAIL_WORKERS``). Once every email has been tried, it waits a few
seconds (``BULK_EMAIL_RETRY_SECONDS``) and tries once more the ones that
missed someone. One run at a time per email, and each copy that goes is
recorded (see ``delivery``), so nobody is emailed twice: pressing Send again
emails only the people a run missed. The page shows the run's progress and
who it missed, and why (see ``run_state``).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from django.conf import settings
from django.core.mail import get_connection
from django.db import connection as db_connection
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.groups.models.group_members import GroupMembership
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
# Why someone was missed, when the run couldn't connect to send it.
NO_SERVER = "couldn't reach the mail server"
# Why someone was missed, when the whole team's email failed before sending.
NOT_SENT = "couldn't be sent"


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


def person_name(user) -> str:
    return user.get_full_name() or user.email


def member_labels(group, addresses) -> dict[str, str]:
    """Each address on ``group`` as the page lists someone an email missed:
    "(BTF07) Amy Chen"."""
    names = {}
    for membership in GroupMembership.objects.filter(group=group, left_at__isnull=True).select_related("user"):
        if membership.user and membership.user.email:
            names.setdefault(membership.user.email, person_name(membership.user))
    return {address: f"({group.group_name}) {names.get(address, address)}" for address in addresses}


def missed_people(people: dict[str, str], failed: dict[str, str]) -> list[dict]:
    """Who a team's email missed, as the page lists them: ``people`` labels
    each address, ``failed`` gives each one's reason."""
    return [{"who": people.get(address, address), "reason": reason} for address, reason in failed.items()]


@dataclass
class Work:
    """One team's or supervisor's email: everyone it's still due, as the page
    would list them, and sending it. ``send(connection, cache)`` gives those
    it didn't reach, as ``{"who", "reason"}``, empty when everyone got it
    (only then is it recorded as emailed); ``cache`` lasts one worker's share
    of the run, e.g. for templates read once."""

    people: list[str]
    send: Callable[[object, dict], list[dict]]


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


def start_run(key: str, actor, work: list[Work]) -> None:
    """Start a run emailing every item of ``work``, on the server, so the page
    can be closed: the items are shared across ``BULK_EMAIL_WORKERS`` threads,
    each with its own mail server connection, then those that missed someone
    are tried once more (see ``_retry``). Raises ``AlreadySending`` while
    another run is going."""
    if not _take(
        key, started_at=timezone.now(), started_by=actor, finished_at=None,
        due=sum(len(item.people) for item in work), emailed=0, failed=0, error="", missed=[],
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
        # Each item that missed someone, with who: added to by every worker.
        failures: list[tuple[Work, list[dict]]] = []
        if threaded:
            threads = [
                threading.Thread(target=_work, args=(key, share, failures, True), daemon=True) for share in shares
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        else:
            for share in shares:
                _work(key, share, failures, False)
        if failures:
            _retry(key, failures)
    except Exception:  # noqa: BLE001
        logger.exception("email run %s failed", key)
    finally:
        EmailSendRun.objects.filter(key=key).update(held_until=None, finished_at=timezone.now())
        if threaded:
            db_connection.close()


def _send(key: str, item: Work, connection, cache: dict) -> list[dict]:
    """``item``'s email: who it missed, and why."""
    try:
        return item.send(connection, cache)
    except Exception:  # noqa: BLE001
        logger.exception("email run %s: an email failed", key)
        return [{"who": p, "reason": NOT_SENT} for p in item.people]


def _close(connection) -> None:
    try:
        connection.close()
    except Exception:  # noqa: BLE001
        pass


def _work(key: str, items: list[Work], failures: list, threaded: bool) -> None:
    """One worker's share of a run, over one mail server connection. Who each
    item reaches counts at once; those that missed someone go on
    ``failures`` for ``_retry``."""
    connection = get_connection(fail_silently=False)
    try:
        try:
            connection.open()
        except Exception as exc:  # noqa: BLE001
            logger.error("email run %s: mail server unreachable error=%s", key, type(exc).__name__)
            failures.extend((item, [{"who": p, "reason": NO_SERVER} for p in item.people]) for item in items)
            return
        cache: dict = {}
        for item in items:
            missed = _send(key, item, connection, cache)
            _note(key, emailed=len(item.people) - len(missed))
            if missed:
                failures.append((item, missed))
    finally:
        _close(connection)
        if threaded:
            db_connection.close()


def _retry(key: str, failures: list[tuple[Work, list[dict]]]) -> None:
    """After every email has been tried, a few seconds' wait, then each that
    missed someone once more, over a fresh connection. Only those it missed
    are emailed again (see ``delivery``); whoever it still misses is the
    run's missed list."""
    time.sleep(settings.BULK_EMAIL_RETRY_SECONDS)
    logger.warning("email run %s: trying %s emails once more", key, len(failures))
    connection = get_connection(fail_silently=False)
    try:
        connection.open()
    except Exception as exc:  # noqa: BLE001
        logger.error("email run %s: mail server unreachable error=%s", key, type(exc).__name__)
        for _, missed in failures:
            _note(key, failed=1, missed=missed, error=UNREACHABLE)
        return
    try:
        cache: dict = {}
        for item, missed in failures:
            # Only someone missed the first time can still be missed.
            first = {m["who"] for m in missed}
            still = [m for m in _send(key, item, connection, cache) if m["who"] in first]
            _note(key, emailed=len(missed) - len(still), failed=1 if still else 0, missed=still)
    finally:
        _close(connection)


def _note(key: str, *, emailed: int = 0, failed: int = 0, missed: list[dict] = (), error: str = "") -> None:
    """Add an item's outcome to the run, and renew its hold."""
    held_until = timezone.now() + SEND_LEASE
    if not missed:
        EmailSendRun.objects.filter(key=key).update(emailed=F("emailed") + emailed, held_until=held_until)
        return
    # The list grows from several workers at once: locked, so none is lost.
    with transaction.atomic():
        run = EmailSendRun.objects.select_for_update().get(key=key)
        run.emailed += emailed
        run.failed += failed
        run.missed = [*run.missed, *missed]
        run.error = error or run.error
        run.held_until = held_until
        run.save(update_fields=["emailed", "failed", "missed", "error", "held_until"])


def _missed_entry(entry) -> dict:
    """``{"who", "reason"}``; a run from before reasons were kept has the name only."""
    return entry if isinstance(entry, dict) else {"who": str(entry), "reason": ""}


def last_missed(key: str) -> list[str]:
    """Who ``key``'s last run missed, as the page lists them."""
    run = EmailSendRun.objects.filter(key=key).first()
    return [_missed_entry(entry)["who"] for entry in run.missed] if run else []


def run_state(key: str) -> dict:
    """Whether ``key``'s email is sending now, and its run's progress (the
    one going, or the last): people due and emailed, teams or supervisors
    not emailed in full, and why it stopped short, if it did."""
    run = EmailSendRun.objects.filter(key=key).first()
    sending = bool(run and run.held_until and run.held_until >= timezone.now())
    return {
        "sending": sending,
        # Where mail that can't be delivered comes back to: the address it's sent from.
        "sent_from": settings.EMAIL_FROM_ADDRESS,
        "run": {
            "due": run.due,
            "emailed": run.emailed,
            "failed": run.failed,
            "error": run.error,
            # Who it couldn't reach, and why.
            "missed": [_missed_entry(entry) for entry in run.missed],
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        } if run and run.started_at else None,
    }
