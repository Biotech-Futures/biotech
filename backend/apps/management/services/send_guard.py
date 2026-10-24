"""What the bulk emails sent from Management wait for, and how they are sent:
the finalist notification, the non-finalist invitation and non-submission
notice, and the two results emails. Announcements and the scheduled emails
(RSVP, submission and guardian reminders, the unread messages digest) wait
their turn in the same queues and send in it (``JOBS``).

Queues: one per mailbox the emails go from (picked on System Emails), so an
email from one mailbox never waits on another's. Emails to one person that
someone is waiting on (a login code, Email Guardian) don't queue.

Waiting: none goes out while a team can still submit, on the deadline or an
extension, grace hours included. Until then who submitted, who is a
finalist, and the marks can all still change.

Sending: pressing Send queues a run on the server that emails everyone due,
whether or not the page stays open. One run sends at a time from each
mailbox: one pressed while another is going waits its turn, and starts a few
seconds after the one before it finishes (``BULK_EMAIL_QUEUE_GAP_SECONDS``).
Who it emails is worked out when it starts. A run sends over a few mail
server connections at once (``BULK_EMAIL_WORKERS``), each taking the next
email as it's free; when the server pushes back one drops out at once, and
that mailbox's runs use fewer for a while (see ``_Crew``). Once every email has
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
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from importlib import import_module
from typing import Callable

from django.conf import settings
from django.db import connection as db_connection
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.services.email_registry import get_email_type
from apps.services.email_metrics import record_email_delivery
from apps.services.system_email import is_email_enabled, sender_connection, sender_for, senders
from apps.services.waiting_email import JOB as WAITING_JOB
from apps.services.resend import JOB as RESEND_JOB
from apps.services.waiting_email import WAITING_NOTE, WAITING_REASON
from apps.submissions.models import GroupExtension
from apps.submissions.services import active_deadline, current_cohort

from ..models import EmailSendRun, QueuedEmailSend
from .delivery import already_sent, server_trouble
from .finalist_notify import SYMPOSIUM_TZ, _long_date

logger = logging.getLogger(__name__)

# The runs that aren't a system email's own key.
FINALIST_SEND = "finalist_notification"
# The row held while the first mailbox's queue is sending (see ``_kick``);
# another mailbox's is this with ":" and its key (see ``queue_key``).
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
# Why a job's run stopped short, when it broke partway.
JOB_FAILED = "The send stopped partway. Anyone it missed is tried again next time."

# The sends that aren't a team's emails, queued the same way (``queue_job``):
# each runs its own send in its turn, given who queued it and its options,
# and gives what it sent ({"sent", "failed"}). "module:function", imported
# when its turn comes; keyed by its email, so it queues for that mailbox.
JOBS: dict[str, str] = {
    "announcement": "apps.admin.services.announcement:announcement_job",
    "rsvp_reminder": "apps.events.services:rsvp_reminder_job",
    "unread_messages": "apps.chat.services.digest:digest_job",
    "submission_reminder": "apps.submissions.reminders:reminder_job",
    "finalist_submission_reminder": "apps.submissions.finalist_reminders:reminder_job",
    "guardian_details_request": "apps.users.guardian_details:reminder_job",
    "guardian_consent_request": "apps.users.guardian_reminders:reminder_job",
    "supervisor_registration_status": "apps.users.supervisor_status:digest_job",
    # Emails kept while the mail server couldn't be reached, sent every 10
    # minutes once it can be: one run per mailbox ("waiting_emails:info").
    **{
        f"{WAITING_JOB}:{mailbox}": "apps.services.waiting_email:waiting_job"
        for mailbox in settings.EMAIL_SENDERS
    },
    # Resend on System Emails' Log, one run per mailbox ("resend:info").
    **{f"{RESEND_JOB}:{mailbox}": "apps.services.resend:resend_job" for mailbox in settings.EMAIL_SENDERS},
}


def lane(key: str) -> str:
    """The mailbox ``key``'s email goes from, whose queue it waits in. A run
    of waiting emails, or of a Resend, names its mailbox: "waiting_emails:info"."""
    if key.startswith((f"{WAITING_JOB}:", f"{RESEND_JOB}:")):
        return key.split(":", 1)[1]
    return sender_for(key).key


def queue_key(mailbox: str) -> str:
    """The row held while ``mailbox``'s queue is sending: the first
    mailbox's keeps the name the one queue always had."""
    return QUEUE_KEY if mailbox == senders()[0].key else f"{QUEUE_KEY}:{mailbox}"


def _is_queue_row(key: str) -> bool:
    return key == QUEUE_KEY or key.startswith(f"{QUEUE_KEY}:")


def _switched_off(key: str) -> str:
    """Why a run stops because its email was switched off on System Emails
    after Send was pressed, or "" while it's on. Read after "Emailed 3 people."
    on the page; nobody it skipped counts as missed, so Send emails them later."""
    try:
        if is_email_enabled(key):
            return ""
    except KeyError:
        return ""  # not a System Email of its own, so there's no switch
    return (
        f"{_email_name(key)} was switched off on System Emails, so the rest weren't sent. "
        "Switch it back on and press Send to email them."
    )


def _stop(key: str, reason: str) -> None:
    EmailSendRun.objects.filter(key=key).update(error=reason)


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
    # The address behind each of ``people``, in the same order, so the run can
    # keep its recipient list (see ``_record_run_metrics``).
    addresses: list[str] = field(default_factory=list)


# What each email's send emails: ``BUILDERS[key](actor, options)`` gives its
# work, called when its turn in the queue comes so it reaches whoever is due
# then. Each email's module adds its own.
BUILDERS: dict[str, Callable[[object, dict], list[Work]]] = {}


def queue_send(key: str, actor, options: dict | None = None) -> None:
    """Queue a send of ``key``'s email (``options`` as its builder takes
    them), then start the queue if nothing is sending (see ``_kick``)."""
    QueuedEmailSend.objects.create(key=key, options=options or {}, queued_by=actor)
    _kick()


def queue_job(key: str, actor=None, options: dict | None = None) -> None:
    """Queue one of ``JOBS``, unless the same one is still waiting its turn
    (a scheduled send that comes round again first), then start the queue."""
    options = options or {}
    waiting = any(item.options == options for item in QueuedEmailSend.objects.filter(key=key))
    if not waiting:
        QueuedEmailSend.objects.create(key=key, options=options, queued_by=actor)
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


def _runs(mailbox: str):
    """The runs of emails that go from ``mailbox``."""
    return [
        run for run in EmailSendRun.objects.all()
        if not _is_queue_row(run.key) and lane(run.key) == mailbox
    ]


def _queued(mailbox: str) -> list[QueuedEmailSend]:
    """``mailbox``'s queue, oldest first."""
    return [
        item for item in QueuedEmailSend.objects.select_related("queued_by").order_by("id")
        if lane(item.key) == mailbox
    ]


def _sending_elsewhere(mailbox: str) -> bool:
    """A run from ``mailbox`` is going that its queue didn't start, e.g. one
    from before an update: the queue waits for it."""
    now = timezone.now()
    return any(run.held_until and run.held_until >= now for run in _runs(mailbox))


def _gap_left(mailbox: str) -> float:
    """How much longer to wait after ``mailbox``'s last run finished, so its
    runs start a few seconds apart."""
    finished = [run.finished_at for run in _runs(mailbox) if run.finished_at]
    if not finished:
        return 0
    return settings.BULK_EMAIL_QUEUE_GAP_SECONDS - (timezone.now() - max(finished)).total_seconds()


def _kick() -> None:
    """Start sending each mailbox's queue that has sends waiting (see
    ``_kick_queue``). Called on every press, and on the pages' checks, which
    picks a queue up again after a restart."""
    for mailbox in sorted({lane(key) for key in QueuedEmailSend.objects.values_list("key", flat=True)}):
        _kick_queue(mailbox)


def _kick_queue(mailbox: str) -> None:
    """Start sending ``mailbox``'s queue unless it's sending already: take
    its hold, start the first run at once when nothing finished just now (so
    the page sees it sending), and send the rest in turn."""
    if not _queued(mailbox) or not _take(queue_key(mailbox)):
        return
    try:
        if _sending_elsewhere(mailbox):
            _let_go(mailbox)
            return
        first = _next(mailbox) if _gap_left(mailbox) <= 0 else None
    except Exception:
        _let_go(mailbox)
        raise
    if settings.BULK_EMAIL_DISPATCH_SYNC:
        _send_queue(mailbox, first, threaded=False)
    else:
        threading.Thread(
            target=_send_queue, args=(mailbox, first), kwargs={"threaded": True}, daemon=True,
            name=f"email-queue-{mailbox}",
        ).start()


def _let_go(mailbox: str | None = None) -> None:
    """Let go of ``mailbox``'s queue, the first mailbox's by default."""
    EmailSendRun.objects.filter(key=queue_key(mailbox or senders()[0].key)).update(held_until=None)


@dataclass
class _Job:
    """One of ``JOBS``, its turn come: who queued it, and its options."""

    actor: object
    options: dict


def _next(mailbox: str | None = None) -> tuple[str, list[Work] | _Job] | None:
    """Start the oldest send queued for ``mailbox`` (the first mailbox by
    default): work out who it emails now, start its run's progress and take
    it off the queue. None once the queue is empty."""
    mailbox = mailbox or senders()[0].key
    while True:
        queued = _queued(mailbox)
        item = queued[0] if queued else None
        if item is None:
            return None
        if item.key in JOBS:
            # A job works out who it emails itself, and stops itself when switched off.
            _begin(item.key, item.queued_by, [])
            item.delete()
            return item.key, _Job(item.queued_by, item.options)
        # Switched off while it waited: started and stopped at once, emailing nobody.
        off = _switched_off(item.key)
        if off:
            _begin(item.key, item.queued_by, [])
            EmailSendRun.objects.filter(key=item.key).update(
                held_until=None, finished_at=timezone.now(), error=off,
            )
            item.delete()
            continue
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
        "connections": None,
    })


def _send_queue(mailbox: str, first, *, threaded: bool) -> None:
    """Send ``mailbox``'s queue in turn, a few seconds apart, then let it go.
    A send queued as it lets go starts the queue again."""
    try:
        while True:
            if first is None:
                if not _queued(mailbox):
                    break
                wait = _gap_left(mailbox)
                if wait > 0:
                    time.sleep(wait)
                first = _next(mailbox)
                if first is None:
                    break
            key, work = first
            first = None
            if isinstance(work, _Job):
                _run_job(key, work, threaded=threaded)
                continue
            _run(key, work, workers=connections_for(key) if threaded else 1, threaded=threaded)
    except Exception:  # noqa: BLE001
        logger.exception("email queue failed")
    finally:
        _let_go(mailbox)
        try:
            _kick()
        except Exception:  # noqa: BLE001
            logger.exception("email queue failed to start again")


def _run_job(key: str, job: _Job, *, threaded: bool) -> None:
    """Run one of ``JOBS`` in its turn, holding its run (and its mailbox's
    queue) while it sends, then note what it sent. It retries its own misses
    (see ``services.retry``)."""
    stop = threading.Event()
    keeper = None
    if threaded:
        keeper = threading.Thread(target=_keep_held, args=(key, stop), daemon=True, name=f"email-job-{key}")
        keeper.start()
    result: dict = {}
    error = ""
    try:
        module, name = JOBS[key].split(":")
        result = getattr(import_module(module), name)(job.actor, job.options) or {}
    except Exception:  # noqa: BLE001
        logger.exception("email job %s failed", key)
        error = JOB_FAILED
    finally:
        stop.set()
        if keeper is not None:
            keeper.join()
        EmailSendRun.objects.filter(key=key).update(
            held_until=None,
            finished_at=timezone.now(),
            emailed=int(result.get("sent") or 0),
            failed=int(result.get("failed") or 0),
            error=error,
        )


def _keep_held(key: str, stop: threading.Event) -> None:
    """Renew a job's hold, and its queue's, every minute until it's done: a
    big send can outlast one hold."""
    try:
        while not stop.wait(60):
            EmailSendRun.objects.filter(key__in=[key, queue_key(lane(key))]).update(
                held_until=timezone.now() + SEND_LEASE,
            )
    except Exception:  # noqa: BLE001
        logger.exception("email job %s: couldn't keep its hold", key)
    finally:
        # Always on its own thread: its database connection goes with it.
        db_connection.close()


class _Crew:
    """A run's connections and the pile of its emails. Each connection takes
    the next email as it's free, so none sits idle while there's more to
    send. When the mail server pushes back (won't take a connection, or
    emails start failing for anything but an address refused), one
    connection drops out at once (``back_off``), down to
    BULK_EMAIL_MIN_WORKERS."""

    def __init__(self, key: str, size: int, items: list[Work]):
        self.key = key
        self.size = size
        self.minimum = max(1, min(settings.BULK_EMAIL_MIN_WORKERS, size))
        self._pile = deque(items)
        self._lock = threading.Lock()

    def take(self) -> Work | None:
        with self._lock:
            return self._pile.popleft() if self._pile else None

    def back_off(self) -> bool:
        """Whether the connection asking should stop: yes while there are
        more than the minimum, and the mailbox's runs use fewer for a while."""
        with self._lock:
            if self.size <= self.minimum:
                return False
            self.size -= 1
            size = self.size
        _fewer_connections(self.key, size)
        return True


def _fewer_connections(key: str, size: int) -> None:
    """Note that the mail server pushed back: this run is down to ``size``
    connections, and its mailbox's runs start with the fewest for a while."""
    logger.warning("email run %s: the mail server pushed back, sending over %s connections", key, size)
    until = timezone.now() + timedelta(minutes=settings.BULK_EMAIL_FEWER_MINUTES)
    EmailSendRun.objects.filter(key=key).update(connections=size)
    EmailSendRun.objects.update_or_create(key=queue_key(lane(key)), defaults={"fewer_connections_until": until})


def connections_for(key: str) -> int:
    """How many mail server connections ``key``'s run starts with: the most,
    unless its mailbox's server pushed back lately."""
    most = max(1, settings.BULK_EMAIL_WORKERS)
    row = EmailSendRun.objects.filter(key=queue_key(lane(key))).only("fewer_connections_until").first()
    if row is not None and row.fewer_connections_until and row.fewer_connections_until > timezone.now():
        return max(1, min(settings.BULK_EMAIL_MIN_WORKERS, most))
    return most


def _run(key: str, work: list[Work], *, workers: int, threaded: bool) -> None:
    """Email every item of ``work`` over ``workers`` connections, each taking
    the next as it's free (side by side on threads, else in turn), then try
    once more those that missed someone (see ``_retry``)."""
    try:
        crew = _Crew(key, max(1, workers), work)
        EmailSendRun.objects.filter(key=key).update(connections=crew.size)
        # Each item that missed someone, with who: added to by every worker.
        failures: list[tuple[Work, list[dict]]] = []
        senders = [_Sender(key, crew, failures, threaded) for _ in range(crew.size)]
        if threaded:
            threads = [threading.Thread(target=sender.run, daemon=True) for sender in senders]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        else:
            for sender in senders:
                sender.open()
            going = [sender for sender in senders if not sender.done]
            while going:
                going = [sender for sender in going if sender.step()]
            for sender in senders:
                sender.close()
        if failures:
            _retry(key, failures)
    except Exception:  # noqa: BLE001
        logger.exception("email run %s failed", key)
    finally:
        completed_at = timezone.now()
        EmailSendRun.objects.filter(key=key).update(
            held_until=None, finished_at=completed_at
        )
        _record_run_metrics(key, completed_at, work)


def _record_run_metrics(key: str, completed_at, work: list[Work] = ()) -> None:
    """Record the final, de-duplicated recipient outcome for one bulk run,
    with every address ``work`` emailed and the reason for each one the run
    still missed."""
    try:
        run = EmailSendRun.objects.filter(key=key).first()
        if run is None:
            return
        address_of = {
            label: address
            for item in work
            for label, address in zip(item.people, item.addresses)
        }
        # Those waiting for the mail server are counted, and their addresses
        # recorded, once their emails go.
        waiting = {address_of.get(_missed_entry(entry)["who"]) for entry in run.missed if _waiting(entry)}
        missed = {}
        failed = 0
        for entry in run.missed:
            if _waiting(entry):
                continue
            failed += 1
            entry = _missed_entry(entry)
            address = address_of.get(entry["who"])
            if address:
                missed[address] = entry["reason"] or NOT_SENT
        record_email_delivery(
            key,
            source_mailbox=sender_for(key).address,
            attempted=run.emailed + failed,
            delivered=run.emailed,
            failed=failed,
            initiated_by=run.started_by,
            started_at=run.started_at,
            completed_at=completed_at,
            recipients=[address for address in address_of.values() if address not in waiting] if address_of else None,
            missed=missed,
        )
    except Exception:  # noqa: BLE001 - metrics must never break the send queue
        logger.exception("email run %s: metric write failed", key)


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


class _Sender:
    """One of a run's connections, signed in as ``key``'s sender. Who each
    item reaches counts at once; those that missed someone go on
    ``failures`` for ``_retry``. When the server pushes back, it stops at
    once if the crew can spare it."""

    def __init__(self, key: str, crew: _Crew, failures: list, threaded: bool):
        self.key = key
        self.crew = crew
        self.failures = failures
        self.threaded = threaded
        self.connection = None
        self.cache: dict = {}
        self.done = False

    def run(self) -> None:
        try:
            self.open()
            while not self.done and self.step():
                pass
        finally:
            self.close()

    def open(self) -> None:
        self.connection = sender_connection(sender_for(self.key), fail_silently=False)
        try:
            self.connection.open()
        except Exception as exc:  # noqa: BLE001
            # The server wouldn't take this connection: one fewer, if spared.
            if self.crew.back_off():
                self.done = True
                return
            # Each email tries again, and is kept to send later when the
            # server still can't be reached (see ``delivery``).
            logger.error("email run %s: mail server unreachable error=%s", self.key, type(exc).__name__)

    def step(self) -> bool:
        """Send the next email from the pile: False once there are none, the
        email's switched off, or this connection has dropped out."""
        if self.done:
            return False
        # Switched off part way: the rest isn't sent.
        off = _switched_off(self.key)
        if off:
            _stop(self.key, off)
            self.done = True
            return False
        item = self.crew.take()
        if item is None:
            self.done = True
            return False
        missed = _send(self.key, item, self.connection, self.cache)
        waiting = [entry for entry in missed if _waiting(entry)]
        missed = [entry for entry in missed if not _waiting(entry)]
        # Those waiting are listed now, and come off once their emails go.
        _note(
            self.key, emailed=len(item.people) - len(missed) - len(waiting), missed=waiting,
            error=WAITING_NOTE if waiting else "",
        )
        if missed:
            self.failures.append((item, missed))
        # Emails starting to fail (for anything but an address refused), or
        # being kept until the server can be reached: one connection fewer.
        if (waiting or any(server_trouble(entry["reason"]) for entry in missed)) and self.crew.back_off():
            self.done = True
            return False
        return True

    def close(self) -> None:
        if self.connection is not None:
            _close(self.connection)
        if self.threaded:
            db_connection.close()


def _retry(key: str, failures: list[tuple[Work, list[dict]]]) -> None:
    """After every email has been tried, a few seconds' wait, then each that
    missed someone once more, over a fresh connection. Only those it missed
    are emailed again (see ``delivery``); whoever it still misses is the
    run's missed list."""
    time.sleep(settings.BULK_EMAIL_RETRY_SECONDS)
    # Switched off since: not tried again, and those missed stay missed.
    off = _switched_off(key)
    if off:
        for _, missed in failures:
            _note(key, failed=1, missed=missed, error=off)
        return
    logger.warning("email run %s: trying %s emails once more", key, len(failures))
    connection = sender_connection(sender_for(key), fail_silently=False)
    try:
        connection.open()
    except Exception as exc:  # noqa: BLE001
        # Each email tries again, and is kept to send later when the server
        # still can't be reached.
        logger.error("email run %s: mail server unreachable error=%s", key, type(exc).__name__)
    try:
        cache: dict = {}
        for item, missed in failures:
            # Only someone missed the first time can still be missed.
            first = {m["who"] for m in missed}
            result = [m for m in _send(key, item, connection, cache) if m["who"] in first]
            waiting = [m for m in result if _waiting(m)]
            still = [m for m in result if not _waiting(m)]
            _note(
                key, emailed=len(missed) - len(still) - len(waiting), failed=1 if still else 0,
                missed=still + waiting, error=WAITING_NOTE if waiting else "",
            )
    finally:
        _close(connection)


def _note(key: str, *, emailed: int = 0, failed: int = 0, missed: list[dict] = (), error: str = "") -> None:
    """Add an item's outcome to the run, and renew its hold and the queue's."""
    held_until = timezone.now() + SEND_LEASE
    EmailSendRun.objects.filter(key=queue_key(lane(key))).update(held_until=held_until)
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


def _waiting(entry) -> bool:
    """A missed entry whose email is kept until the mail server can be reached."""
    return isinstance(entry, dict) and entry.get("reason") == WAITING_REASON


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
    if key.startswith(f"{WAITING_JOB}:"):
        return "Emails waiting to send"
    if key.startswith(f"{RESEND_JOB}:"):
        return "Resend"
    try:
        return get_email_type(key).name
    except Exception:  # noqa: BLE001
        return key


def _ahead(item: QueuedEmailSend) -> list[str]:
    """The emails sending, and queued before ``item``, from its mailbox, by
    name, each once."""
    mailbox = lane(item.key)
    now = timezone.now()
    keys = [run.key for run in _runs(mailbox) if run.held_until and run.held_until >= now]
    keys += [queued.key for queued in _queued(mailbox) if queued.id < item.id]
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
            # Sent over fewer connections, the mail server having pushed back.
            "limited": bool(run.connections and run.connections < max(1, settings.BULK_EMAIL_WORKERS)),
        } if run and run.started_at else None,
    }
