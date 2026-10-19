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
from django.db.models import F, Q
from django.utils import timezone
from django.utils.module_loading import import_string

from .email_log import UNREACHABLE, WAITING_REASON, note_send, reason_for
from .email_metrics import mailbox_address, record_email_delivery
from .models import WaitingEmail
from .retry import WAITING, MailServerDown, reopen, send_noting_refused, send_reconnecting, worth_retrying

logger = logging.getLogger(__name__)

# How long a kept email is tried for, every 10 minutes.
WAIT_FOR = timedelta(days=3)
# Their codes and links expire within minutes: a late copy would only confuse.
NEVER_WAIT = frozenset({"login_code", "password_reset"})
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


def send_or_wait(message, *, key: str, send=None, retry: bool = False, on_sent=None, sent_by=None, until=None):
    """Send ``message`` (``send()`` sends it, ``message.send`` by default),
    giving what ``send`` gives. The connection dropping is mended at once (see
    ``retry.send_reconnecting``); with ``retry``, any other failure but a
    refused address is tried once more, as ``send_with_retry`` does.

    When the mail server still can't be reached, the email is kept to send
    later and ``WAITING`` given, with ``on_sent`` its hooks and ``until`` when
    it's out of date (3 days on at most). A login code or password reset link,
    or one already out of date, isn't kept: the failure is raised. Any other
    failure is raised as it is."""
    send = send or (lambda: message.send(fail_silently=False))
    connection = message.connection
    mailbox = _mailbox(message, key)
    can_wait = key not in NEVER_WAIT and (until is None or until > timezone.now())
    if can_wait and _is_down(mailbox):
        keep(message, key=key, mailbox=mailbox, on_sent=on_sent, sent_by=sent_by, until=until)
        return WAITING
    tries = 2 if retry else 1
    for attempt in range(tries):
        try:
            result = send_reconnecting(connection, send)
        except MailServerDown as down:
            _note_down(mailbox)
            if not can_wait:
                raise (down.__cause__ or down) from None
            keep(message, key=key, mailbox=mailbox, on_sent=on_sent, sent_by=sent_by, until=until)
            return WAITING
        except Exception as exc:  # noqa: BLE001
            if attempt + 1 >= tries or not worth_retrying(exc):
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


def keep(message, *, key: str, mailbox: str, on_sent=None, sent_by=None, until=None) -> WaitingEmail:
    """Keep ``message`` as it was built, to send once the mail server can be
    reached: tried every 10 minutes until ``until``, 3 days on at most."""
    now = timezone.now()
    give_up_at = now + WAIT_FOR if until is None else min(now + WAIT_FOR, until)
    row = WaitingEmail.objects.create(
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
        "waiting_email.kept key=%s mailbox=%s recipients=%s", key, mailbox, len(row.recipients),
    )
    return row


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
    )
    _hook(row, "missed", missed)


def give_up(now=None) -> int:
    """Give up on the emails past their time: those they were due are noted
    as missed. How many were given up on."""
    now = now or timezone.now()
    count = 0
    rows = WaitingEmail.objects.filter(give_up_at__lte=now).filter(Q(held_until__isnull=True) | Q(held_until__lt=now))
    for row in rows:
        _missed(row, dict.fromkeys(_due(row), UNREACHABLE))
        logger.warning("waiting_email.gave_up key=%s recipients=%s", row.key, len(row.recipients))
        row.delete()
        count += 1
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
        row.delete()
        return 0, 1
    why = {
        address.lower(): reason_for(smtplib.SMTPRecipientsRefused({address: reply}))
        for address, reply in (refused or {}).items()
    }
    _sent(row, [address for address in due if address.lower() not in why])
    _missed(row, {address: why[address.lower()] for address in due if address.lower() in why})
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
    rows = list(WaitingEmail.objects.filter(mailbox=mailbox).order_by("id"))
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
    mailboxes = sorted(set(WaitingEmail.objects.values_list("mailbox", flat=True)))
    for mailbox in mailboxes:
        queue_job(job_key(mailbox), None, {"mailbox": mailbox})
    return mailboxes


def waiting_for() -> dict[str, list[dict]]:
    """Who each email is waiting to reach, and until when: ``{key:
    [{"address", "until"}]}``, oldest first."""
    waiting: dict[str, list[dict]] = {}
    for row in WaitingEmail.objects.defer("message").order_by("id"):
        for address in row.recipients:
            waiting.setdefault(row.key, []).append({"address": address, "until": row.give_up_at})
    return waiting
