"""Emails the mail server couldn't be reached to send: kept, and tried again
every 10 minutes for 3 days.

* ``send_or_wait(message, key=...)``: send ``message``. When the connection
  drops it's opened again and the email sent once more (see ``retry``); when
  the server still can't be reached, the email is kept as it was built
  (``WaitingEmail``) and ``WAITING`` given. Login codes and password reset
  links aren't kept: they expire within minutes.
* ``queue_waiting()``: every 10 minutes (the "Send waiting emails" workflow):
  gives up on emails past their time, then queues a run for each mailbox
  with emails still waiting, in its turn after any bulk email going from it
  (``send_guard``). The run, ``send_waiting(mailbox)``, sends them oldest
  first once the server can be reached.
* ``waiting_for()``: who each email is waiting to reach, for the Log.

An email that fails for good (turned away, or given up on after 3 days) is
kept too, as missed, for Resend on System Emails' Log (``resend_missed``),
for 30 days or until it's out of date. Announcements and Management's bulk
emails aren't: their Resend builds them again (see ``resend``).

Once a kept email goes, or is given up on, the hooks it was kept with run
(``on_sent``'s "due", "sent" and "missed", each a function's dotted path,
given ``on_sent`` and the addresses), so whatever recorded the first send
records this one too: the announcement's counts, or the Management emails'
record of who has each email, so pressing Send again emails nobody twice.
"""
from __future__ import annotations

import logging
import re
import smtplib
import threading
import time
from datetime import timedelta
from email import policy
from email.parser import BytesHeaderParser
from email.utils import formatdate

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.module_loading import import_string

from .email_log import UNREACHABLE, WAITING_REASON, note_send, reason_for
from .email_metrics import mailbox_address, record_email_delivery
from .models import WaitingEmail
from .retry import WAITING as WAITING_SENT
from .retry import MailServerDown, reopen, send_noting_refused, send_reconnecting, worth_retrying

logger = logging.getLogger(__name__)

# How long a kept email is tried for, every 10 minutes.
WAIT_FOR = timedelta(days=3)
# Their codes and links expire within minutes: a late copy would only confuse.
NEVER_WAIT = frozenset({"login_code", "password_reset"})
# How long an email that failed is kept for Resend.
MISSED_FOR = timedelta(days=30)
# The emails whose Resend builds them again, so a copy isn't kept for it.
OWN_RESEND = frozenset({
    "announcement", "finalist_notification", "nonfinalist_invitation", "nonsubmission_notice",
    "results_team", "results_supervisor",
})
WAITING = WaitingEmail.State.WAITING
MISSED = WaitingEmail.State.MISSED
# A run's note on the Management pages when some of its emails wait.
WAITING_NOTE = (
    "Couldn't reach the mail server for some people. Their emails are sent once it can be "
    "reached, tried every 10 minutes for 3 days."
)
# The runs that send them, one per mailbox: "waiting_emails:info".
JOB = "waiting_emails"
# How long a run holds an email while sending it.
HOLD = timedelta(minutes=10)

# Mailboxes just found unreachable, and until when (``time.monotonic``): a run
# keeps the rest of its emails at once rather than waiting on the server for
# each (``MAIL_SERVER_DOWN_SECONDS``).
_down: dict[str, float] = {}
_down_lock = threading.Lock()


def job_key(mailbox: str) -> str:
    """The run that sends ``mailbox``'s waiting emails, e.g. "waiting_emails:info"."""
    return f"{JOB}:{mailbox}"


def _down_seconds() -> int:
    return int(getattr(settings, "MAIL_SERVER_DOWN_SECONDS", 60))


def _is_down(mailbox: str) -> bool:
    if _down_seconds() <= 0:
        return False
    with _down_lock:
        return time.monotonic() < _down.get(mailbox, 0)


def _note_down(mailbox: str) -> None:
    if _down_seconds() > 0:
        with _down_lock:
            _down[mailbox] = time.monotonic() + _down_seconds()


def _note_up(mailbox: str) -> None:
    with _down_lock:
        _down.pop(mailbox, None)


def _mailbox(message, key: str) -> str:
    """The mailbox ``message`` goes from: the sender whose address is its From,
    else the one picked for ``key`` on System Emails."""
    from .system_email import sender_for, senders

    address = mailbox_address(message.from_email)
    for sender in senders():
        if sender.address.lower() == address:
            return sender.key
    return sender_for(key).key


def send_or_wait(
    message, *, key: str, send=None, retry: bool = False, later: bool = False, keep_missed: bool = True,
    on_sent=None, sent_by=None, until=None,
):
    """Send ``message`` (``send()`` sends it, ``message.send`` by default),
    giving what ``send`` gives. The connection dropping is mended at once (see
    ``retry.send_reconnecting``); with ``retry``, any other failure but a
    refused address is tried once more, as ``send_with_retry`` does.

    When the mail server still can't be reached, the email is kept to send
    later and ``WAITING`` given, with ``on_sent`` its hooks and ``until`` when
    it's out of date (3 days on at most). A login code or password reset link,
    or one already out of date, isn't kept: the failure is raised. Any other
    failure is raised as it is, and the email kept, as missed, for Resend on
    the Log (unless ``later``, its run tries it again at its end, or
    ``keep_missed`` is off: an email whose Resend builds it again)."""
    send = send or (lambda: message.send(fail_silently=False))
    connection = message.connection
    mailbox = _mailbox(message, key)
    can_wait = key not in NEVER_WAIT and (until is None or until > timezone.now())
    if can_wait and _is_down(mailbox):
        keep(message, key=key, mailbox=mailbox, on_sent=on_sent, sent_by=sent_by, until=until)
        return WAITING_SENT
    tries = 2 if retry else 1
    for attempt in range(tries):
        try:
            result = send_reconnecting(connection, send)
        except MailServerDown as down:
            _note_down(mailbox)
            if not can_wait:
                raise (down.__cause__ or down) from None
            keep(message, key=key, mailbox=mailbox, on_sent=on_sent, sent_by=sent_by, until=until)
            return WAITING_SENT
        except Exception as exc:  # noqa: BLE001
            if attempt + 1 >= tries or not worth_retrying(exc):
                # Failed for good, unless its run tries it again at its end.
                if keep_missed and can_wait and key not in OWN_RESEND and not (later and worth_retrying(exc)):
                    _keep_missed(message, key=key, mailbox=mailbox, sent_by=sent_by, until=until)
                raise
            # Not the exception itself: SMTP errors carry recipient addresses.
            logger.warning("email.retrying key=%s error=%s", key, type(exc).__name__)
            try:
                reopen(connection)
            except Exception:  # noqa: BLE001
                pass  # the next try finds the server can't be reached
            continue
        _note_up(mailbox)
        return result
    raise AssertionError("unreachable")  # pragma: no cover


def keep(message, *, key: str, mailbox: str, on_sent=None, sent_by=None, until=None, state=WAITING) -> WaitingEmail:
    """Keep ``message`` as it was built: waiting, to send once the mail server
    can be reached, tried every 10 minutes until ``until``, 3 days on at most;
    or missed, for Resend, until ``until``, 30 days on at most."""
    now = timezone.now()
    span = WAIT_FOR if state == WAITING else MISSED_FOR
    give_up_at = now + span if until is None else min(now + span, until)
    row = WaitingEmail.objects.create(
        state=state,
        stale_at=until,
        key=key,
        mailbox=mailbox,
        from_email=message.from_email or "",
        recipients=list(message.recipients()),
        message=message.message().as_bytes(linesep="\r\n"),
        on_sent=on_sent or {},
        sent_by=sent_by if getattr(sent_by, "pk", None) else None,
        created_at=now,
        give_up_at=give_up_at,
    )
    logger.warning(
        "waiting_email.kept key=%s mailbox=%s state=%s recipients=%s", key, mailbox, state, len(row.recipients),
    )
    return row


def _keep_missed(message, **kwargs) -> None:
    """Keep ``message``, which failed, for Resend; never in the way of the
    failure itself being reported."""
    try:
        # Its own savepoint: a copy that can't be kept leaves the send's own work be.
        with transaction.atomic():
            keep(message, state=MISSED, **kwargs)
    except Exception:  # noqa: BLE001
        logger.exception("waiting_email.keep_missed_failed key=%s", kwargs.get("key"))


def _to_missed(row: WaitingEmail, now) -> None:
    """``row`` won't go by itself (turned away, or given up on): kept for
    Resend, unless its email's Resend builds it again or it's out of date."""
    if row.key in OWN_RESEND or (row.stale_at and row.stale_at <= now):
        row.delete()
        return
    row.state = MISSED
    row.give_up_at = min(now + MISSED_FOR, row.stale_at) if row.stale_at else now + MISSED_FOR
    row.held_until = None
    row.save(update_fields=["state", "give_up_at", "held_until", "recipients"])


def _to_waiting(row: WaitingEmail, now) -> bool:
    """``row``, resent while the mail server can't be reached: waiting for it
    instead, tried every 10 minutes. False when it's out of date."""
    if row.stale_at and row.stale_at <= now:
        row.delete()
        return False
    row.state = WAITING
    row.give_up_at = min(now + WAIT_FOR, row.stale_at) if row.stale_at else now + WAIT_FOR
    row.held_until = None
    row.save(update_fields=["state", "give_up_at", "held_until"])
    return True


# --- sending them later ------------------------------------------------------

_DATE_HEADER = re.compile(rb"(?im)^Date:[^\r\n]*(?:\r\n[ \t][^\r\n]*)*")


def _fresh_date(raw: bytes) -> bytes:
    """``raw`` dated now, as it goes, rather than when it was first tried."""
    head, sep, body = raw.partition(b"\r\n\r\n")
    head = _DATE_HEADER.sub(f"Date: {formatdate(localtime=True)}".encode(), head, count=1)
    return head + sep + body


class _Raw:
    """A kept email's bytes, as Django's mail backends read a message."""

    def __init__(self, raw: bytes):
        self._raw = raw

    def as_bytes(self, unixfrom=False, linesep="\n"):
        return self._raw if linesep == "\r\n" else self._raw.replace(b"\r\n", linesep.encode())

    def as_string(self, unixfrom=False, linesep="\n"):
        return self.as_bytes(linesep=linesep).decode("utf-8", "replace")

    def get_charset(self):
        return None


class _KeptMessage(EmailMessage):
    """A kept email, sent as it was built, to ``recipients``: those it's still
    due. Its To and CC headers stay as they were."""

    def __init__(self, row: WaitingEmail, recipients, connection):
        super().__init__(from_email=row.from_email, to=list(recipients), connection=connection)
        self._raw = _fresh_date(bytes(row.message))
        self.subject = str(BytesHeaderParser(policy=policy.default).parsebytes(self._raw).get("Subject", ""))

    def message(self, *args, **kwargs):
        return _Raw(self._raw)


def _due(row: WaitingEmail) -> list[str]:
    """Who ``row`` is still due: everyone, unless its "due" hook says some
    have had it since (pressing Send again on a Management email, say)."""
    path = (row.on_sent or {}).get("due")
    if not path:
        return list(row.recipients)
    try:
        return list(import_string(path)(row.on_sent, list(row.recipients)))
    except Exception:  # noqa: BLE001
        logger.exception("waiting_email.due_hook_failed key=%s", row.key)
        return list(row.recipients)


def _hook(row: WaitingEmail, name: str, addresses) -> None:
    path = (row.on_sent or {}).get(name)
    if not path:
        return
    try:
        import_string(path)(row.on_sent, addresses)
    except Exception:  # noqa: BLE001
        logger.exception("waiting_email.hook_failed key=%s hook=%s", row.key, name)


def _sent(row: WaitingEmail, delivered: list[str]) -> None:
    """``row`` went to ``delivered``: counted, and its "sent" hook run."""
    if not delivered:
        return
    record_email_delivery(
        row.key,
        source_mailbox=row.from_email,
        attempted=len(delivered),
        delivered=len(delivered),
        failed=0,
        initiated_by=row.sent_by,
        started_at=row.created_at,
    )
    _hook(row, "sent", delivered)


def _missed(row: WaitingEmail, missed: dict[str, str]) -> None:
    """``row`` won't reach ``missed`` ({address: why}): noted in the Log, and
    its "missed" hook run."""
    if not missed:
        return
    note_send(
        row.key,
        missed=missed,
        by=row.sent_by,
        attempted=len(missed),
        delivered=0,
        failed=len(missed),
        source_mailbox=row.from_email,
        started_at=row.created_at,
        last_sent=False,
        ref=(row.on_sent or {}).get("ref"),
    )
    _hook(row, "missed", missed)


def give_up(now=None) -> int:
    """Give up on the waiting emails past their time: those they were due are
    noted as missed, and each kept for Resend. Kept-for-Resend copies past
    theirs go. How many waiting emails were given up on."""
    now = now or timezone.now()
    count = 0
    unheld = Q(held_until__isnull=True) | Q(held_until__lt=now)
    for row in WaitingEmail.objects.filter(state=WAITING, give_up_at__lte=now).filter(unheld):
        due = _due(row)
        _missed(row, dict.fromkeys(due, UNREACHABLE))
        logger.warning("waiting_email.gave_up key=%s recipients=%s", row.key, len(row.recipients))
        row.recipients = due
        _to_missed(row, now)
        count += 1
    WaitingEmail.objects.filter(state=MISSED, give_up_at__lte=now).filter(unheld).delete()
    return count


def _is_on(key: str) -> bool:
    from .system_email import is_email_enabled

    try:
        return is_email_enabled(key)
    except KeyError:
        return True


def _hold(row: WaitingEmail, now) -> bool:
    """Hold ``row`` while it's sent: of two runs, only one gets it."""
    return bool(
        WaitingEmail.objects.filter(pk=row.pk)
        .filter(Q(held_until__isnull=True) | Q(held_until__lt=now))
        .update(held_until=now + HOLD)
    )


def _send_row(row: WaitingEmail, connection, now) -> tuple[int, int] | None:
    """Send ``row`` to those still due it: ``(sent, failed)``, or None when the
    mail server can't be reached (it waits for the next run)."""
    due = _due(row)
    if not due:
        row.delete()
        return 0, 0
    message = _KeptMessage(row, due, connection)
    try:
        refused = send_reconnecting(connection, lambda: send_noting_refused(message))
    except MailServerDown:
        WaitingEmail.objects.filter(pk=row.pk).update(held_until=None, tries=F("tries") + 1, tried_at=now)
        return None
    except Exception as exc:  # noqa: BLE001
        # The server took the connection but turned the email away.
        logger.error("waiting_email.send_failed key=%s error=%s", row.key, type(exc).__name__)
        _missed(row, dict.fromkeys(due, reason_for(exc)))
        row.recipients = due
        _to_missed(row, now)
        return 0, 1
    why = {
        address.lower(): reason_for(smtplib.SMTPRecipientsRefused({address: reply}))
        for address, reply in (refused or {}).items()
    }
    _sent(row, [address for address in due if address.lower() not in why])
    _missed(row, {address: why[address.lower()] for address in due if address.lower() in why})
    refused_too = [address for address in due if address.lower() in why]
    if refused_too:
        # Those it turned away, kept for Resend.
        row.recipients = refused_too
        _to_missed(row, now)
    else:
        row.delete()
    return 1, 0


def send_waiting(mailbox: str, now=None) -> dict:
    """Send ``mailbox``'s waiting emails, oldest first, once the mail server can
    be reached; one whose email is switched off on System Emails keeps
    waiting. A run that can't reach the server, or loses it partway, leaves
    the rest for the next. Gives ``{"sent", "failed"}``."""
    from .system_email import _sender, sender_connection, senders

    now = now or timezone.now()
    give_up(now)
    rows = list(WaitingEmail.objects.filter(mailbox=mailbox, state=WAITING).order_by("id"))
    if not rows:
        return {"sent": 0, "failed": 0}
    connection = sender_connection(_sender(mailbox) or senders()[0], fail_silently=False)
    sent = failed = 0
    try:
        try:
            connection.open()
        except Exception as exc:  # noqa: BLE001
            logger.warning("waiting_email.unreachable mailbox=%s error=%s", mailbox, type(exc).__name__)
            WaitingEmail.objects.filter(pk__in=[row.pk for row in rows]).update(
                tries=F("tries") + 1, tried_at=now,
            )
            return {"sent": 0, "failed": 0}
        _note_up(mailbox)
        for row in rows:
            if not _is_on(row.key) or not _hold(row, now):
                continue
            outcome = _send_row(row, connection, now)
            if outcome is None:
                _note_down(mailbox)
                break
            sent += outcome[0]
            failed += outcome[1]
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass
    logger.info("waiting_email.run mailbox=%s sent=%s failed=%s", mailbox, sent, failed)
    return {"sent": sent, "failed": failed}


def waiting_job(actor, options: dict) -> dict:
    """The queued run for one mailbox (``send_guard.JOBS``)."""
    return send_waiting(options.get("mailbox", ""))


def queue_waiting(now=None) -> list[str]:
    """Give up on the emails past their time, then queue a run for each
    mailbox with emails still waiting. Gives those mailboxes."""
    from apps.management.services.send_guard import queue_job

    give_up(now)
    mailboxes = sorted(set(WaitingEmail.objects.filter(state=WAITING).values_list("mailbox", flat=True)))
    for mailbox in mailboxes:
        queue_job(job_key(mailbox), None, {"mailbox": mailbox})
    return mailboxes


def waiting_for() -> dict[str, list[dict]]:
    """Who each email is waiting to reach, and until when: ``{key:
    [{"address", "until"}]}``, oldest first."""
    waiting: dict[str, list[dict]] = {}
    for row in WaitingEmail.objects.filter(state=WAITING).defer("message").order_by("id"):
        for address in row.recipients:
            waiting.setdefault(row.key, []).append({"address": address, "until": row.give_up_at})
    return waiting


# --- Resend on the Log -------------------------------------------------------


def resend_missed(key: str, actor=None, now=None) -> dict:
    """Resend on System Emails' Log, for an email kept when it failed: each
    copy of ``key``'s still kept sent again, oldest first, over its mailbox's
    connection. Those it reaches come off the Log's missed list; those it
    misses again are listed again, with why, and stay kept for another
    Resend. When the mail server can't be reached, they wait for it instead,
    tried every 10 minutes. Gives ``{"sent", "failed"}``."""
    from .email_log import forget_missed
    from .system_email import _sender, sender_connection, senders

    now = now or timezone.now()
    rows = list(WaitingEmail.objects.filter(key=key, state=MISSED, give_up_at__gt=now).order_by("id"))
    delivered: list[str] = []
    missed: dict[str, str] = {}
    waiting: list[str] = []
    for mailbox in dict.fromkeys(row.mailbox for row in rows):
        connection = sender_connection(_sender(mailbox) or senders()[0], fail_silently=False)
        try:
            try:
                connection.open()
            except Exception:  # noqa: BLE001
                pass  # each send tries again, and they wait for the server if it can't be reached
            left = [row for row in rows if row.mailbox == mailbox]
            for index, row in enumerate(left):
                if not _hold(row, now):
                    continue
                due = _due(row)
                message = _KeptMessage(row, due, connection)
                try:
                    refused = send_reconnecting(connection, lambda message=message: send_noting_refused(message))
                except MailServerDown:
                    for still in left[index:]:
                        if _to_waiting(still, now):
                            waiting.extend(still.recipients)
                    break
                except Exception as exc:  # noqa: BLE001
                    missed.update(dict.fromkeys(due, reason_for(exc)))
                    WaitingEmail.objects.filter(pk=row.pk).update(held_until=None, tries=F("tries") + 1, tried_at=now)
                    continue
                why = {
                    address.lower(): reason_for(smtplib.SMTPRecipientsRefused({address: reply}))
                    for address, reply in (refused or {}).items()
                }
                delivered.extend(address for address in due if address.lower() not in why)
                refused_too = [address for address in due if address.lower() in why]
                missed.update({address: why[address.lower()] for address in refused_too})
                if refused_too:
                    row.recipients = refused_too
                    row.held_until = None
                    row.save(update_fields=["recipients", "held_until"])
                else:
                    row.delete()
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass
    # Their earlier entries go; this send is noted as one of its own.
    forget_missed(key, [*delivered, *missed, *waiting])
    if delivered or missed:
        note_send(
            key,
            missed=missed,
            by=actor,
            attempted=len(delivered) + len(missed),
            delivered=len(delivered),
            failed=len(missed),
            source_mailbox=rows[0].from_email if rows else None,
            last_sent=bool(delivered),
        )
    logger.info("waiting_email.resend key=%s sent=%s failed=%s waiting=%s", key, len(delivered), len(missed), len(waiting))
    return {"sent": len(delivered), "failed": len(missed)}


def kept_for_resend(now=None) -> set[str]:
    """The emails with copies kept for Resend, by key."""
    now = now or timezone.now()
    return set(WaitingEmail.objects.filter(state=MISSED, give_up_at__gt=now).values_list("key", flat=True))
