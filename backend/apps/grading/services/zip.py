"""Zip builder for submission bundles.

Used by both the sync per-group endpoint (small, in-memory response) and the
async per-component job (built to memory, uploaded to Azure Blob for polling).

Structure inside the archive:

    <group_name>/
        <component_code>/
            <original filename>          # if file present
            text.txt                     # if SAQ text present
            link.txt                     # if prototype link present

Missing / unreadable blobs are skipped with a placeholder ``MISSING.txt`` note
in the same folder so the archive still opens and the marker tells the grader
what to chase up. This matches the codebase's other Azure Blob handling — a
missing SAS-signed URL never crashes the request.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from typing import Iterable

from apps.submissions.models import Submission

logger = logging.getLogger(__name__)


_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(name: str) -> str:
    """Filesystem-safe segment. Collapses runs of unsafe chars to ``_`` and
    trims leading/trailing dots to keep Windows extractors happy."""
    cleaned = _UNSAFE.sub("_", (name or "").strip())
    cleaned = cleaned.strip("._")
    return cleaned or "unnamed"


def _read_file_bytes(field) -> bytes | None:
    """Read a FileField's bytes or return None if the backing blob is gone.

    Azure Blob returns 404s for deleted objects — we don't want a single bad
    blob to nuke a 180-group export.
    """
    try:
        with field.open("rb") as fh:
            return fh.read()
    except Exception:  # noqa: BLE001 — narrow logging, broad recovery is the point
        logger.warning("Missing / unreadable submission blob: %s", getattr(field, "name", "?"))
        return None


def build_submissions_zip(submissions: Iterable[Submission]) -> bytes:
    """Materialise a zip archive of the given submissions to memory.

    Callers stream small results directly to the client (per-group endpoint)
    or hand the bytes off to storage for async jobs. For the current cohort
    size (~180 groups × ≤ 4 components × a handful of MB each) in-memory
    materialisation stays comfortably below process limits; if that grows,
    swap for a temp-file / true streaming implementation.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for submission in submissions:
            group_folder = _safe(submission.group.group_name)
            component_folder = _safe(submission.component.code)
            base = f"{group_folder}/{component_folder}"

            if submission.file:
                data = _read_file_bytes(submission.file)
                original = submission.file.name.rsplit("/", 1)[-1] or "file.bin"
                if data is None:
                    zf.writestr(f"{base}/MISSING.txt", f"Original blob missing: {submission.file.name}\n")
                else:
                    zf.writestr(f"{base}/{_safe(original)}", data)

            if submission.text:
                zf.writestr(f"{base}/text.txt", submission.text)

            if submission.link:
                zf.writestr(f"{base}/link.txt", submission.link + "\n")

    return buffer.getvalue()


def zip_filename(prefix: str) -> str:
    """Timestamped filename for a zip download. Prefix is caller-controlled;
    kept short (e.g. ``"group-3"`` or ``"POSTER"``) so the resulting name
    stays readable in the browser's download bar."""
    from datetime import datetime
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"{_safe(prefix)}-{ts}.zip"
