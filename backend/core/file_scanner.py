"""Centralised logic for validating and scanning uploaded files."""

from __future__ import annotations

import logging
import mimetypes
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.core.exceptions import ValidationError


class FileScanError(Exception):
    """Raised when a scanning backend reports a suspicious file."""


logger = logging.getLogger(__name__)


def scan_uploaded_file(uploaded_file) -> None:
    """
    Validate and optionally virus-scan an uploaded file before storage.

    Raises ``ValidationError`` if the file violates allow/deny rules, or
    ``FileScanError`` if an external scanner reports a problem.
    """

    _enforce_size_limit(uploaded_file)
    _enforce_extension_policy(uploaded_file)
    _enforce_mime_policy(uploaded_file)
    _run_external_scanner(uploaded_file)


def _enforce_size_limit(uploaded_file) -> None:
    max_bytes = getattr(settings, "FILE_UPLOAD_MAX_BYTES", None)
    if max_bytes and uploaded_file.size > max_bytes:
        raise ValidationError(
            {
                "file": f"File is too large ({uploaded_file.size} bytes). Allowed maximum is {max_bytes} bytes.",
            }
        )


def _enforce_extension_policy(uploaded_file) -> None:
    blocked_extensions = getattr(settings, "FILE_UPLOAD_BLOCKED_EXTENSIONS", [])
    if not blocked_extensions:
        return

    name = getattr(uploaded_file, "name", "") or ""
    extension = Path(name).suffix.lower()
    if extension and extension in blocked_extensions:
        raise ValidationError({"file": f"Files with extension '{extension}' are not allowed."})


def _enforce_mime_policy(uploaded_file) -> None:
    allowed = [mime.lower() for mime in getattr(settings, "FILE_UPLOAD_ALLOWED_MIME_TYPES", [])]
    if not allowed:
        return

    content_type = (uploaded_file.content_type or "").lower()
    if not content_type:
        guessed, _ = mimetypes.guess_type(getattr(uploaded_file, "name", ""))
        content_type = (guessed or "application/octet-stream").lower()

    if not _is_mime_allowed(content_type, allowed):
        raise ValidationError({"file": f"Files of type '{content_type}' are not permitted."})


def _is_mime_allowed(mime: str, allowed: Iterable[str]) -> bool:
    for pattern in allowed:
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            if mime.startswith(prefix):
                return True
        elif mime == pattern:
            return True
    return False


def _run_external_scanner(uploaded_file) -> None:
    command_template = getattr(settings, "FILE_UPLOAD_SCAN_COMMAND", None)
    if not command_template:
        return

    # Persist the file to disk for scanners that require a filesystem path.
    uploaded_file.seek(0)
    tmp_file_path = None
    with tempfile.NamedTemporaryFile(prefix="upload_scan_", delete=False) as tmp_file:
        for chunk in uploaded_file.chunks():
            tmp_file.write(chunk)
        tmp_file_path = Path(tmp_file.name)

    try:
        command = command_template.format(file=str(tmp_file_path))
        logger.debug("Running upload scanner: %s", command)

        result = subprocess.run(
            shlex.split(command),
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            message = result.stdout.strip() or result.stderr.strip() or "Unknown scanner error"
            raise FileScanError(message)
    finally:
        uploaded_file.seek(0)
        if tmp_file_path is not None:
            try:
                os.remove(tmp_file_path)
            except OSError:
                logger.warning("Failed to remove temporary scan file: %s", tmp_file_path)
