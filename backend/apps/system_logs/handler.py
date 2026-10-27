"""Keeps log records in the database for the admin System Logs page.

``DatabaseLogHandler`` sits beside the console handler in ``LOGGING``. Logging
must never break or slow a request, so:

* Everything the row needs (message, traceback, request id, user, path) is
  worked out and redacted in ``emit``, in the thread that logged. The
  background writer only receives finished rows: it never reads context
  variables or the request.
* ``emit`` then only puts the row on an in-memory queue. A full queue drops
  the row (and counts it) rather than wait.
* One writer thread per process saves the queue in batches. It starts on the
  first record a process emits, and again in a forked child (gunicorn), so a
  thread started before a fork is never relied on.
* Any failure is reported on stderr, at most once a minute, and never through
  ``logging`` (which would loop back here). Records logged by this module, by
  the database layer, or from the writer thread are not kept.

Because the writer saves on its own connection after the request, a record
logged inside a transaction that then rolls back is still kept.

Tests set ``SYSTEM_LOG_DISPATCH_SYNC`` to write inline instead. Inline rows go
through the caller's connection, so unlike in production they roll back with
the caller's transaction (tests/apps/system_logs/test_context.py tests the
real writer for that case).
"""
import atexit
import logging
import os
import queue
import sys
import threading
import time
import traceback
from datetime import datetime, timezone

from django.conf import settings

from . import redaction
from .context import current_request, current_request_id, user_id_of

# Loggers never kept (each with its children):
# * the database layer and this app: a failed write logging about itself
#   would loop back here;
# * the servers' access and request logs: one coloured line per request
#   ("HTTP POST /x/ 400 [5.02, 127.0.0.1]"), repeating what the app logs
#   itself. django.request is not among them, so 5xx errors are still kept.
_LOOPING_LOGGERS = ("django.db.backends", "apps.system_logs", "django.utils.autoreload")
SERVER_ACCESS_LOGGERS = (
    "django.server",           # runserver
    "django.channels.server",  # daphne's runserver
    "daphne.server",
    "daphne.http_protocol",
    "uvicorn.access",
    "gunicorn.access",
)
EXCLUDED_LOGGERS = _LOOPING_LOGGERS + SERVER_ACCESS_LOGGERS

BATCH_SIZE = 100
FLUSH_SECONDS = 2.0
REPORT_INTERVAL_SECONDS = 60.0

# The attributes every LogRecord has; anything else came from ``extra=``.
_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message", "asctime", "taskName", "request", "status_code",
}

_local = threading.local()
_last_report = 0.0


def _report(problem: str) -> None:
    """Say on stderr that System Logs lost something, at most once a minute."""
    global _last_report
    now = time.monotonic()
    if now - _last_report < REPORT_INTERVAL_SECONDS:
        return
    _last_report = now
    try:
        sys.stderr.write(f"[system_logs] {problem}\n")
    except Exception:  # noqa: BLE001
        pass


def _setting(name: str, default):
    try:
        return getattr(settings, name, default)
    except Exception:  # noqa: BLE001 - settings not configured yet
        return default


def _threshold() -> int:
    level = logging.getLevelName(str(_setting("SYSTEM_LOG_DB_LEVEL", "WARNING")).upper())
    return level if isinstance(level, int) else logging.WARNING


def _is_within(name: str, loggers) -> bool:
    """Whether logger ``name`` is one of ``loggers`` or a child of one."""
    return any(name == logger or name.startswith(logger + ".") for logger in loggers)


def is_wanted(record: logging.LogRecord) -> bool:
    """Whether System Logs keeps ``record``: WARNING and above (or the
    configured level), plus INFO from the auth and email loggers."""
    if not _setting("SYSTEM_LOG_DB_ENABLED", False):
        return False
    name = record.name
    if _is_within(name, EXCLUDED_LOGGERS):
        return False
    if record.levelno >= _threshold():
        return True
    if record.levelno < logging.INFO:
        return False
    return _is_within(name, _setting("SYSTEM_LOG_DB_INFO_LOGGERS", ()))


def _clip(value, limit: int) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def build_row(record: logging.LogRecord) -> dict:
    """The ``SystemLogEntry`` fields for ``record``, redacted. Runs in the
    thread that logged, so the request it belongs to can still be read."""
    try:
        message = record.getMessage()
    except Exception:  # noqa: BLE001 - arguments that don't fit the message
        message = str(record.msg)

    tb = ""
    if record.exc_info and record.exc_info[0] is not None:
        tb = "".join(traceback.format_exception(*record.exc_info))
    elif record.exc_text:
        tb = record.exc_text
    if record.stack_info:
        tb = f"{tb}\n{record.stack_info}".strip()

    # django.request passes the request it logs about; otherwise it's the
    # request this thread is serving, if any.
    request = record.__dict__.get("request")
    request = getattr(request, "_request", request)  # a DRF Request wraps Django's
    if not hasattr(request, "META"):
        request = current_request()

    method = path = ""
    user_id = None
    if request is not None:
        method = getattr(request, "method", "") or ""
        match = getattr(request, "resolver_match", None)
        path = redaction.scrub_path(getattr(request, "path", "") or "", getattr(match, "kwargs", None))
        user_id = user_id_of(request)

    status_code = record.__dict__.get("status_code")
    if not (isinstance(status_code, int) and 100 <= status_code <= 599):
        status_code = None

    extra = {key: value for key, value in record.__dict__.items() if key not in _STANDARD_ATTRS and not key.startswith("_")}

    return {
        "created_at": datetime.fromtimestamp(record.created, tz=timezone.utc),
        "level": record.levelno,
        "level_name": _clip(record.levelname, 16),
        "logger_name": _clip(record.name, 200),
        "message": redaction.truncate(redaction.scrub_text(message), redaction.MESSAGE_MAX_CHARS),
        "traceback": redaction.truncate(redaction.scrub_text(tb), redaction.TRACEBACK_MAX_CHARS),
        "request_id": _clip(current_request_id() or getattr(request, "system_log_request_id", ""), 64),
        "request_method": _clip(method, 10),
        "request_path": _clip(path, 500),
        "status_code": status_code,
        "user_id": user_id,
        "module": _clip(record.module, 200),
        "func_name": _clip(record.funcName, 200),
        "line_no": record.lineno if isinstance(record.lineno, int) and record.lineno >= 0 else None,
        "extra": redaction.clean_extra(extra),
    }


def write_now(row: dict) -> None:
    """Save one row inline (tests). Its own savepoint, so a failure leaves the
    caller's transaction usable."""
    from django.db import transaction

    from .models import SystemLogEntry

    with transaction.atomic():
        SystemLogEntry.objects.create(**row)


class _Writer:
    """The per-process queue and the thread that saves it."""

    def __init__(self):
        self._lock = threading.Lock()
        self._exit_registered = False
        self._clear()

    def _clear(self):
        self.pid = None
        self.queue = None
        self.dropped = 0

    def after_fork_in_child(self):
        # The parent's thread doesn't exist here and its lock may have been
        # held mid-fork: start from nothing.
        self._lock = threading.Lock()
        self._clear()

    def submit(self, row: dict) -> None:
        if self.pid != os.getpid():
            self._start()
        try:
            self.queue.put_nowait(row)
        except queue.Full:
            # Approximate under contention; it only feeds the "dropped" note.
            self.dropped += 1

    def _start(self):
        with self._lock:
            if self.pid == os.getpid():
                return
            # At least 1: a Queue of size 0 has no limit at all.
            self.queue = queue.Queue(maxsize=max(1, int(_setting("SYSTEM_LOG_QUEUE_SIZE", 10_000))))
            thread = threading.Thread(target=self._run, name="system-log-writer", daemon=True)
            self.pid = os.getpid()
            thread.start()
            if not self._exit_registered:
                atexit.register(self.flush_at_exit)
                self._exit_registered = True

    def _run(self):
        # Anything logged on this thread (say, by the database driver) is
        # never queued again.
        _local.in_writer = True
        own_queue = self.queue
        while self.queue is own_queue:
            try:
                batch = self._next_batch(own_queue)
                if self.dropped:
                    dropped, self.dropped = self.dropped, 0
                    batch.append(_dropped_row(dropped))
                self.write_batch(batch)
                if own_queue.empty():
                    _close_connection()
            except Exception as exc:  # noqa: BLE001 - the thread must not die
                _report(f"writer error: {type(exc).__name__}")
                time.sleep(1)

    @staticmethod
    def _next_batch(own_queue) -> list[dict]:
        batch = [own_queue.get()]
        deadline = time.monotonic() + FLUSH_SECONDS
        while len(batch) < BATCH_SIZE:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                batch.append(own_queue.get(timeout=remaining))
            except queue.Empty:
                break
        return batch

    @staticmethod
    def write_batch(batch: list[dict], *, retry: bool = True) -> None:
        """Save ``batch``. A dropped or stale connection is closed and the
        batch tried once more on a new one. A missing table (before
        ``migrate`` has run) drops the batch; a row the database refuses is
        skipped without losing the rest."""
        from django.db import DatabaseError, InterfaceError, OperationalError, ProgrammingError, close_old_connections

        from .models import SystemLogEntry

        # As at the start of a request: drop a connection that's past
        # CONN_MAX_AGE or broken, and health-check the one kept.
        close_old_connections()
        try:
            SystemLogEntry.objects.bulk_create([SystemLogEntry(**row) for row in batch])
            return
        except (OperationalError, InterfaceError) as exc:
            _close_connection()
            if not retry:
                _report(f"lost {len(batch)} log entries: {type(exc).__name__}")
                return
        except ProgrammingError as exc:
            # No table yet, or one that doesn't match: every row would fail
            # the same way, so they're not tried one by one.
            _report(f"lost {len(batch)} log entries: {type(exc).__name__} (has migrate run?)")
            return
        except DatabaseError:
            _Writer._write_one_by_one(batch)
            return
        _Writer.write_batch(batch, retry=False)

    @staticmethod
    def _write_one_by_one(batch: list[dict]) -> None:
        from django.db import InterfaceError, OperationalError

        from .models import SystemLogEntry

        lost = 0
        for row in batch:
            try:
                SystemLogEntry.objects.create(**row)
            except (OperationalError, InterfaceError):
                lost += 1
                # Only a broken connection needs a new one; a refused row
                # leaves it usable (each statement commits on its own).
                _close_connection()
            except Exception:  # noqa: BLE001
                lost += 1
        if lost:
            _report(f"lost {lost} log entries the database refused")

    def flush_at_exit(self):
        """Save what's still queued when the process exits normally."""
        if self.pid != os.getpid() or self.queue is None:
            return
        rows = []
        while True:
            try:
                rows.append(self.queue.get_nowait())
            except queue.Empty:
                break
        if rows:
            try:
                self.write_batch(rows, retry=False)
            except Exception:  # noqa: BLE001
                pass


def _close_connection():
    from django.db import connection

    try:
        connection.close()
    except Exception:  # noqa: BLE001
        pass


def _dropped_row(count: int) -> dict:
    return {
        "created_at": datetime.now(tz=timezone.utc),
        "level": logging.WARNING,
        "level_name": "WARNING",
        "logger_name": "apps.system_logs",
        "message": f"{count} log entries were not kept because the System Logs queue was full.",
        "extra": {"count": count},
    }


_writer = _Writer()
if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_writer.after_fork_in_child)


class DatabaseLogHandler(logging.Handler):
    """Keeps wanted records (``is_wanted``) for the System Logs page."""

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(_local, "busy", False) or getattr(_local, "in_writer", False):
            return
        _local.busy = True
        try:
            if not is_wanted(record):
                return
            row = build_row(record)
            if _setting("SYSTEM_LOG_DISPATCH_SYNC", False):
                write_now(row)
            else:
                _writer.submit(row)
        except Exception as exc:  # noqa: BLE001 - logging must never raise
            _report(f"could not keep a log entry: {type(exc).__name__}")
        finally:
            _local.busy = False
