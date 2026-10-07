"""What the bulk emails sent from Management wait for, and how they are sent:
the finalist notification, the non-finalist invitation and non-submission
notice, and the two results emails.

Waiting: none goes out while a team can still submit, on the deadline or an
extension, grace hours included. Until then who submitted, who is a
finalist, and the marks can all still change.

Sending: pressing Send queues a run on the server that emails everyone due,
whether or not the page stays open. One run sends at a time across every
email: one pressed while another is going waits its turn, and starts a few
seconds after the one before it finishes (``BULK_EMAIL_QUEUE_GAP_SECONDS``).
Who it emails is worked out when it starts. A run sends over a few mail
server connections at once (``BULK_EMAIL_WORKERS``); once every email has
been tried, it waits a few seconds (``BULK_EMAIL_RETRY_SECONDS``) and tries
once more the ones that missed someone. Each copy that goes is recorded (see
``delivery``), so nobody is emailed twice: pressing Send again emails only the
people a run missed. The page shows the run's progress, what's queued, and
who it missed, and why (see ``run_state``).
"""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from django.conf import settings
from django.db import connection as db_connection
from django.db import transaction
from django.db.models import F, Max, Q
from django.utils import timezone

from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.services.email_registry import get_email_type
from apps.services.system_email import sender_connection, sender_for
from apps.submissions.models import GroupExtension
from apps.submissions.services import active_deadline, current_cohort

from ..models import EmailSendRun, QueuedEmailSend
from .delivery import already_sent
from .finalist_notify import SYMPOSIUM_TZ, _long_date

logger = logging.getLogger(__name__)

# The runs that aren't a system email's own key.
FINALIST_SEND = "finalist_notification"
# The row held while the queue is sending (see ``_kick``).
QUEUE_KEY = "bulk_email_queue"

# How long a run holds its email between sends: far past one team's send, so
# it only ever lapses for a run that died partway.
SEND_LEASE = timedelta(minutes=5)

UNREACHABLE = "Couldn't reach the mail server. Press Send again to email the rest."
# Why someone was missed, when the run couldn't connect to send it.
NO_SERVER = "couldn't reach the mail server"
# Why someone was missed, when the whole team's email failed before sending.
NOT_SENT = "couldn't be sent"
NOT_READY = "Couldn't get this send ready. Press it again."


def _long_time(moment: datetime) -> str:
    """"Friday, 17 October 2026, 11:59 PM", in Sydney time."""
    local = timezone.localtime(moment, SYMPOSIUM_TZ)
    return f"{_long_date(local.date())}, {int(f'{local:%I}')}:{local:%M} {local:%p}"


def submissions_open_reason(action: str = "Send this") -> str:
    """Why sending waits for submissions to close, or "" once they have: the
    deadline, then the last of this year's extensions, grace hours included.
    ``action`` is what waits, e.g. "Post this" for an email's announcement."""
    now = timezone.now()
    deadline = active_deadline()
    if deadline is not None:
        until = deadline.closes_at + timedelta(hours=deadline.grace_hours)
        if now <= until:
            return f"Submissions are open until {_long_time(until)} (Sydney time). {action} once they close."
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
            f"{action} once every extension has ended."
        )
    return ""


def person_name(user) -> str:
    return user.get_full_name() or user.email


def person_label(groups: str, name: str | None, address: str) -> str:
    """Someone as the page lists who an email missed: "amy@example.com
    (BTF07, Amy Chen)", or "amy@example.com (BTF07)" without a name."""
    if name and name != address:
        return f"{address} ({groups}, {name})"
    return f"{address} ({groups})"


def _is_on(who: str, group_name: str) -> bool:
    """Whether a missed entry is someone on ``group_name``: "amy@x (BTF07,
    Amy Chen)", "amy@x (BTF07)", or an older run's "(BTF07) Amy Chen"."""
    return (
        f" ({group_name}, " in who
        or who.endswith(f" ({group_name})")
        or who.startswith(f"({group_name}) ")
    )


def member_labels(group, addresses) -> dict[str, str]:
    """Each address on ``group`` as the page lists someone an email missed
    (see ``person_label``)."""
    names = {}
    for membership in GroupMembership.objects.filter(group=group, left_at__isnull=True).select_related("user"):
        if membership.user and membership.user.email:
            names.setdefault(membership.user.email, person_name(membership.user))
    return {address: person_label(group.group_name, names.get(address), address) for address in addresses}


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


# What each email's send emails: ``BUILDERS[key](actor, options)`` gives its
# work, called when its turn in the queue comes so it reaches whoever is due
# then. Each email's module adds its own.
BUILDERS: dict[str, Callable[[object, dict], list[Work]]] = {}


def queue_send(key: str, actor, options: dict | None = None) -> None:
    """Queue a send of ``key``'s email (``options`` as its builder takes
    them), then start the queue if nothing is sending (see ``_kick``)."""
    QueuedEmailSend.objects.create(key=key, options=options or {}, queued_by=actor)
    _kick()


def _take(key: str, **fields) -> bool:
    """Hold ``key``'s row: a single conditional update, so of two requests
    racing for it only one gets it."""
    now = timezone.now()
    EmailSendRun.objects.get_or_create(key=key)
    return bool(
        EmailSendRun.objects.filter(key=key)
        .filter(Q(held_until__isnull=True) | Q(held_until__lt=now))
        .update(held_until=now + SEND_LEASE, **fields)
    )


def _sending_elsewhere() -> bool:
    """A run is going that this queue didn't start, e.g. one from before an
    update: the queue waits for it."""
    return EmailSendRun.objects.exclude(key=QUEUE_KEY).filter(held_until__gte=timezone.now()).exists()


def _gap_left() -> float:
    """How much longer to wait after the last run finished, so runs start a
    few seconds apart."""
    last = EmailSendRun.objects.exclude(key=QUEUE_KEY).aggregate(last=Max("finished_at"))["last"]
    if last is None:
        return 0
    return settings.BULK_EMAIL_QUEUE_GAP_SECONDS - (timezone.now() - last).total_seconds()


def _kick() -> None:
    """Start sending the queue unless it's sending already: take its hold,
    start the first run at once when nothing finished just now (so the page
    sees it sending), and send the rest in turn. Called on every press, and
    on the pages' checks, which picks the queue up again after a restart."""
    if not QueuedEmailSend.objects.exists() or not _take(QUEUE_KEY):
        return
    try:
        if _sending_elsewhere():
            _let_go()
            return
        first = _next() if _gap_left() <= 0 else None
    except Exception:
        _let_go()
        raise
    if settings.BULK_EMAIL_DISPATCH_SYNC:
        _send_queue(first, threaded=False)
    else:
        threading.Thread(
            target=_send_queue, args=(first,), kwargs={"threaded": True}, daemon=True, name="email-queue",
        ).start()


def _let_go() -> None:
    EmailSendRun.objects.filter(key=QUEUE_KEY).update(held_until=None)


def _next() -> tuple[str, list[Work]] | None:
    """Start the oldest queued send: work out who it emails now, start its
    run's progress and take it off the queue. None once the queue is empty."""
    while True:
        item = QueuedEmailSend.objects.select_related("queued_by").order_by("id").first()
        if item is None:
            return None
        try:
            work = BUILDERS[item.key](item.queued_by, item.options)
        except Exception:  # noqa: BLE001
            logger.exception("email queue: couldn't get %s ready", item.key)
            _begin(item.key, item.queued_by, [])
            EmailSendRun.objects.filter(key=item.key).update(
                held_until=None, finished_at=timezone.now(), error=NOT_READY,
            )
            item.delete()
            continue
        _begin(item.key, item.queued_by, work)
        # Only now, so the page always sees it either queued or sending.
        item.delete()
        return item.key, work


def _begin(key: str, actor, work: list[Work]) -> None:
    """Start ``key``'s run afresh: held, with everyone ``work`` is due."""
    now = timezone.now()
    EmailSendRun.objects.update_or_create(key=key, defaults={
        "held_until": now + SEND_LEASE, "started_at": now, "started_by": actor, "finished_at": None,
        "due": sum(len(item.people) for item in work), "emailed": 0, "failed": 0, "error": "", "missed": [],
    })


def _send_queue(first, *, threaded: bool) -> None:
    """Send the queue in turn, a few seconds apart, then let it go. A send
    queued as it lets go starts the queue again."""
    try:
        while True:
            if first is None:
                if not QueuedEmailSend.objects.exists():
                    break
                wait = _gap_left()
                if wait > 0:
                    time.sleep(wait)
                first = _next()
                if first is None:
                    break
            key, work = first
            first = None
            workers = max(1, settings.BULK_EMAIL_WORKERS) if threaded else 1
            _run(key, work, workers=workers, threaded=threaded)
    except Exception:  # noqa: BLE001
        logger.exception("email queue failed")
    finally:
        _let_go()
        try:
            _kick()
        except Exception:  # noqa: BLE001
            logger.exception("email queue failed to start again")
        if threaded:
            db_connection.close()


def _run(key: str, work: list[Work], *, workers: int, threaded: bool) -> None:
    """Email every item of ``work``: the items are shared across ``workers``
    threads, each with its own mail server connection, then those that
    missed someone are tried once more (see ``_retry``)."""
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
    ``failures`` for ``_retry``. Signed in as ``key``'s sender."""
    connection = sender_connection(sender_for(key), fail_silently=False)
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
    connection = sender_connection(sender_for(key), fail_silently=False)
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
    """Add an item's outcome to the run, and renew its hold and the queue's."""
    held_until = timezone.now() + SEND_LEASE
    EmailSendRun.objects.filter(key=QUEUE_KEY).update(held_until=held_until)
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


def tried_teams(key: str, teams) -> set[int]:
    """Which of these teams a send of ``key``'s email has already tried:
    someone on it has the email, or the last run missed someone on it.
    Resend Email To Missed Individuals emails the people on these still due it."""
    teams = list(teams)
    tried = set(already_sent(key, [team.id for team in teams]))
    missed = last_missed(key)
    for team in teams:
        if any(_is_on(who, team.group_name) for who in missed):
            tried.add(team.id)
    return tried


# An older run's entry: "(BTF07) Amy Chen", without the address.
_OLD_LABEL = re.compile(r"^\((?P<group>[^)]*)\) (?P<name>.+)$")


def _with_addresses(entries: list[dict]) -> list[dict]:
    """Missed entries as the page lists them. An older run's, which named
    the person only, gets their address from their team, when it can be
    found."""
    members: dict[str, dict[str, str]] = {}
    shown = []
    for entry in entries:
        old = _OLD_LABEL.match(entry["who"])
        if old and "@" not in entry["who"]:
            group, name = old["group"], old["name"]
            if group not in members:
                team = Groups.objects.filter(group_name=group, deleted_at__isnull=True).order_by("-year").first()
                memberships = (
                    GroupMembership.objects.filter(group=team).select_related("user") if team else []
                )
                members[group] = {
                    person_name(m.user): m.user.email for m in memberships if m.user and m.user.email
                }
            address = members[group].get(name)
            if address:
                entry = {**entry, "who": person_label(group, name, address)}
        shown.append(entry)
    return shown


def _email_name(key: str) -> str:
    """"Finalist notification", as System Emails names it."""
    try:
        return get_email_type(key).name
    except Exception:  # noqa: BLE001
        return key


def _ahead(item: QueuedEmailSend) -> list[str]:
    """The emails sending, and queued before ``item``, by name, each once."""
    keys = list(
        EmailSendRun.objects.exclude(key=QUEUE_KEY).filter(held_until__gte=timezone.now()).values_list("key", flat=True)
    )
    keys += QueuedEmailSend.objects.filter(id__lt=item.id).values_list("key", flat=True)
    return list(dict.fromkeys(_email_name(key) for key in keys))


def run_state(key: str) -> dict:
    """Whether ``key``'s email is sending now, how many of its sends are
    queued, and its run's progress (the one going, or the last): people due
    and emailed, teams or supervisors not emailed in full, and why it stopped
    short, if it did. Starts the queue again if it stopped (see ``_kick``)."""
    _kick()
    run = EmailSendRun.objects.filter(key=key).first()
    sending = bool(run and run.held_until and run.held_until >= timezone.now())
    queued = list(QueuedEmailSend.objects.filter(key=key).order_by("id"))
    return {
        "sending": sending,
        # Its sends waiting their turn, and the emails ahead of the first.
        "queued": len(queued),
        "ahead": _ahead(queued[0]) if queued else [],
        # Where mail that can't be delivered comes back to: the address it's
        # sent from, as picked on System Emails.
        "sent_from": sender_for(key).address,
        "run": {
            "due": run.due,
            "emailed": run.emailed,
            "failed": run.failed,
            "error": run.error,
            # Who it couldn't reach, and why.
            "missed": _with_addresses([_missed_entry(entry) for entry in run.missed]),
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        } if run and run.started_at else None,
    }
