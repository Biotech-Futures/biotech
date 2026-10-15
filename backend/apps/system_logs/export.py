"""Streaming the System Logs out as CSV or JSON lines.

Rows are read from the database in chunks and written out as they're read,
so an export of many rows never sits in memory whole.

Under ASGI (daphne/uvicorn) Django can't stream a plain generator: it reads
the whole thing into memory first. ``streaming_content`` therefore hands ASGI
an async generator that pulls the lines in batches on the request's thread.
"""
import csv
import json
from datetime import timezone as dt_timezone
from itertools import islice

from asgiref.sync import sync_to_async
from django.core.handlers.asgi import ASGIRequest

# The most rows one export holds; narrow the filters for more.
EXPORT_MAX_ROWS = 100_000
CHUNK_SIZE = 2_000

COLUMNS = [
    ("created_at", "Time (UTC)"),
    ("level_name", "Level"),
    ("logger_name", "Source"),
    ("message", "Message"),
    ("traceback", "Traceback"),
    ("request_id", "Request ID"),
    ("request_method", "Method"),
    ("request_path", "Path"),
    ("status_code", "Status"),
    ("user_id", "User ID"),
    ("user_email", "User email"),
    ("module", "Module"),
    ("func_name", "Function"),
    ("line_no", "Line"),
]

# A spreadsheet runs a cell starting with these as a formula.
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _rows(queryset):
    fields = [name for name, _ in COLUMNS if name != "user_email"]
    for row in queryset[:EXPORT_MAX_ROWS].values(*fields, "user__email").iterator(chunk_size=CHUNK_SIZE):
        row["user_email"] = row.pop("user__email") or ""
        row["created_at"] = row["created_at"].astimezone(dt_timezone.utc).isoformat()
        yield row


def _csv_cell(value) -> str:
    if value is None:
        return ""
    text = str(value)
    # Opened in Excel, "=HYPERLINK(...)" in a log message must stay text.
    return f"'{text}" if text.startswith(_FORMULA_STARTS) else text


class _Echo:
    """A file-like object whose write() hands back what was written, so
    ``csv.writer`` can produce one line at a time."""

    def write(self, value):
        return value


def csv_lines(queryset):
    writer = csv.writer(_Echo())
    yield "﻿"  # so Excel reads the file as UTF-8
    yield writer.writerow([label for _, label in COLUMNS])
    for row in _rows(queryset):
        yield writer.writerow([_csv_cell(row[name]) for name, _ in COLUMNS])


def json_lines(queryset):
    """One JSON object per line (NDJSON), so the file can be streamed and read
    back line by line."""
    for row in _rows(queryset):
        yield json.dumps(row, ensure_ascii=False) + "\n"


# Lines sent to the client per hop to the database thread under ASGI.
ASYNC_BATCH_LINES = 500


async def _async_lines(lines):
    # thread_sensitive keeps every batch on the request's own thread, so the
    # database cursor is always used from the connection that opened it.
    take = sync_to_async(lambda: "".join(islice(lines, ASYNC_BATCH_LINES)), thread_sensitive=True)
    while True:
        chunk = await take()
        if not chunk:
            return
        yield chunk


def streaming_content(request, lines):
    """``lines`` in the form this server streams without buffering."""
    django_request = getattr(request, "_request", request)
    return _async_lines(lines) if isinstance(django_request, ASGIRequest) else lines
