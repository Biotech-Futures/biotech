"""One more try for an email that didn't go.

Every email gets a second try, over a fresh connection, unless the mail server
refused the address itself (a second try would only be refused again).

* ``send_with_retry(message)``: tries again at once. For a single email,
  which someone may be waiting on.
* ``send_reconnecting(connection, send)``: when the connection itself fails
  (dropped, timed out, or closed by the server), it's opened again and the
  same email sent once more, so one drop doesn't fail every email after it.
  Raises ``MailServerDown`` when the server still can't be reached; the
  email is then kept to send later (see ``waiting_email``).
* ``RetryLater``: for a run sending many emails over one connection. Those
  that fail are kept, and once the run has tried everyone, ``run()`` waits a
  few seconds (``BULK_EMAIL_RETRY_SECONDS``) and tries each once more, as the
  Management emails do.
"""
from __future__ import annotations

import logging
import smtplib
import time
from typing import Callable

from django.conf import settings

logger = logging.getLogger(__name__)


class _Waiting:
    """What a send gives when the mail server couldn't be reached and the
    email was kept to send later (see ``waiting_email``)."""

    def __repr__(self) -> str:
        return "WAITING"


WAITING = _Waiting()


class MailServerDown(Exception):
    """The mail server couldn't be reached, even with the connection opened
    again. Its cause is the last failure."""


def worth_retrying(exc: BaseException) -> bool:
    """Whether a second try could go where the first didn't: anything but the
    server refusing the address."""
    return not isinstance(exc, smtplib.SMTPRecipientsRefused)


def _reply_code(exc: BaseException) -> int | None:
    """The mail server's reply code, if it gave one."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused) and exc.recipients:
        return next(iter(exc.recipients.values()))[0]
    if isinstance(exc, smtplib.SMTPResponseException):
        return exc.smtp_code
    return None


def lost_connection(exc: BaseException) -> bool:
    """Whether ``exc`` is the connection itself failing, not the server turning
    one email away: dropped, reset or timed out (no reply code), refused at
    the door, or closed by the server (421, "service not available")."""
    if isinstance(exc, smtplib.SMTPConnectError):
        return True
    code = _reply_code(exc)
    if code is not None:
        return code == 421
    return isinstance(exc, OSError)


def send_reconnecting(connection, send: Callable[[], object]):
    """``send()``, giving what it gives. When the connection itself fails, it's
    opened again and ``send()`` tried once more. Raises ``MailServerDown`` when
    it can't be opened again or fails the same way again; any other failure
    as it is."""
    try:
        return send()
    except Exception as exc:  # noqa: BLE001
        if not lost_connection(exc):
            raise
        # Not the exception itself: SMTP errors carry recipient addresses.
        logger.warning("email.reconnecting error=%s", type(exc).__name__)
    try:
        reopen(connection)
    except Exception as exc:  # noqa: BLE001
        raise MailServerDown(type(exc).__name__) from exc
    try:
        return send()
    except Exception as exc:  # noqa: BLE001
        if lost_connection(exc):
            raise MailServerDown(type(exc).__name__) from exc
        raise


def _close(connection) -> None:
    try:
        connection.close()
    except Exception:  # noqa: BLE001
        pass


def reopen(connection) -> None:
    """``connection`` closed and opened again, for a fresh start after a
    failure. Raises if the server can't be reached."""
    if connection is None:
        return
    _close(connection)
    connection.open()


def reset(connection) -> None:
    """Clear a failed send's half-done SMTP transaction, so the next email on
    the same connection starts clean."""
    try:
        if getattr(connection, "connection", None):
            connection.connection.rset()
    except Exception:  # noqa: BLE001
        pass


def send_noting_refused(message) -> dict:
    """Send ``message``, giving each address the mail server refused while it
    took the rest: ``{address: (code, reply)}``. smtplib reports those, but
    Django's sender drops them, so this send's ``sendmail`` reply is kept."""
    smtp = getattr(message.connection, "connection", None)
    if smtp is None or not hasattr(smtp, "sendmail"):
        message.send(fail_silently=False)
        return {}
    refused: dict = {}
    original = smtp.sendmail

    def sendmail(*args, **kwargs):
        result = original(*args, **kwargs)
        refused.update(result or {})
        return result

    smtp.sendmail = sendmail
    try:
        message.send(fail_silently=False)
    finally:
        smtp.sendmail = original
    return refused


def send_with_retry(message):
    """Send ``message``; if it fails for any reason but a refused address,
    once more at once over a fresh connection. Returns what ``send`` returns;
    raises the second failure, or the refusal."""
    try:
        return message.send(fail_silently=False)
    except Exception as exc:
        if not worth_retrying(exc):
            raise
        # Not the exception itself: SMTP errors carry recipient addresses.
        logger.warning("email.retrying error=%s", type(exc).__name__)
    # A message with no connection of its own makes a new one each send.
    reopen(message.connection)
    return message.send(fail_silently=False)


class RetryLater:
    """The emails of a run that failed, to try once more once it's done.

    ``keep(exc, item, resend)`` keeps ``item`` when ``exc`` (why it failed)
    is worth a second try, returning whether it did; ``resend()`` sends it
    again. ``run()`` then waits ``BULK_EMAIL_RETRY_SECONDS``, opens
    ``connection`` afresh and resends each, giving ``(item, error)`` for
    each: ``error`` None when it went, ``WAITING`` when ``resend`` kept it to
    send later (see ``waiting_email``), else why it failed.
    """

    def __init__(self, connection=None):
        self.connection = connection
        self._kept: list[tuple[object, Callable[[], object]]] = []

    def __bool__(self) -> bool:
        return bool(self._kept)

    def keep(self, exc: BaseException, item, resend: Callable[[], object]) -> bool:
        if not worth_retrying(exc):
            return False
        self._kept.append((item, resend))
        return True

    def run(self) -> list[tuple[object, BaseException | None]]:
        if not self._kept:
            return []
        kept, self._kept = self._kept, []
        time.sleep(settings.BULK_EMAIL_RETRY_SECONDS)
        logger.warning("email.retrying_run count=%s", len(kept))
        try:
            reopen(self.connection)
        except Exception as exc:  # noqa: BLE001
            # The server can't be reached: each resend still decides, and one
            # that keeps its email to send later does so (see ``waiting_email``).
            logger.warning("email.retrying_run_unreachable error=%s", type(exc).__name__)
        results: list[tuple[object, object]] = []
        try:
            for item, resend in kept:
                try:
                    outcome = resend()
                except Exception as exc:  # noqa: BLE001
                    results.append((item, exc))
                    reset(self.connection)
                else:
                    results.append((item, WAITING if outcome is WAITING else None))
        finally:
            # Opened here, so closed here too.
            if self.connection is not None:
                _close(self.connection)
        return results
