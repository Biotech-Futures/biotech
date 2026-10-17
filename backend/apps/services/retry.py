"""One more try for an email that didn't go.

Every email gets a second try, over a fresh connection, unless the mail server
refused the address itself (a second try would only be refused again).

* ``send_with_retry(message)``: tries again at once. For a single email,
  which someone may be waiting on.
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


def worth_retrying(exc: BaseException) -> bool:
    """Whether a second try could go where the first didn't: anything but the
    server refusing the address."""
    return not isinstance(exc, smtplib.SMTPRecipientsRefused)


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
    each, ``error`` None when it went.
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
            # The server can't be reached: none of them goes.
            return [(item, exc) for item, _ in kept]
        results: list[tuple[object, BaseException | None]] = []
        try:
            for item, resend in kept:
                try:
                    resend()
                except Exception as exc:  # noqa: BLE001
                    results.append((item, exc))
                    reset(self.connection)
                else:
                    results.append((item, None))
        finally:
            # Opened here, so closed here too.
            if self.connection is not None:
                _close(self.connection)
        return results
