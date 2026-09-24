"""Zip builder for submission bundles.

Used by both the sync per-group endpoint (small, in-memory response) and the
async per-component job (built to memory, uploaded to Azure Blob for polling).

One folder per group, flat files inside — no component subfolders. Both
the folder and every file carry the current year:

    <Year>_<GroupName>/
        <Year>_<GroupName>_<Component>.<ext>        # stored file, original ext
        <Year>_<GroupName>_SAQs.txt                 # SAQ answer text
        <Year>_<GroupName>_Prototype_Link.txt       # prototype link
        <Year>_<GroupName>_<Component>_MISSING.txt  # blob gone — see below

Missing / unreadable blobs are skipped with the placeholder ``_MISSING.txt``
note so the archive still opens and the marker tells the grader what to
chase up. This matches the codebase's other Azure Blob handling — a
missing SAS-signed URL never crashes the request.
"""
from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from typing import Iterable

from django.utils import timezone

from .content import ComponentEntry, open_file

logger = logging.getLogger(__name__)


_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(name: str) -> str:
    """Filesystem-safe segment. Collapses runs of unsafe chars to ``_`` and
    trims leading/trailing dots to keep Windows extractors happy."""
    cleaned = _UNSAFE.sub("_", (name or "").strip())
    cleaned = cleaned.strip("._")
    return cleaned or "unnamed"


def _read_entry_bytes(entry: ComponentEntry) -> bytes | None:
    """Read an entry's stored file or return None if the blob is gone.

    Azure Blob returns 404s for deleted objects — we don't want a single bad
    blob to nuke a 180-group export.
    """
    try:
        with open_file(entry) as fh:
            return fh.read()
    except Exception:  # noqa: BLE001 — narrow logging, broad recovery is the point
        logger.warning(
            "Missing / unreadable submission blob: %s",
            (entry.file or {}).get("storage_key", "?"),
        )
        return None


# Friendly component labels for the flat file names, matching the export.
_COMPONENT_LABELS = {"SAQ": "SAQs", "POSTER": "Poster", "REPORT": "Report", "PROTOTYPE": "Prototype"}


def build_submissions_zip(
    entries: Iterable[ComponentEntry], *, group_folder: bool = True
) -> bytes:
    """Materialise a zip archive of the given component entries to memory.

    Callers stream small results directly to the client (per-group endpoint)
    or hand the bytes off to storage for async jobs. For the current cohort
    size (~180 groups × ≤ 4 components × a handful of MB each) in-memory
    materialisation stays comfortably below process limits; if that grows,
    swap for a temp-file / true streaming implementation.
    """
    year = timezone.now().year
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for entry in entries:
            label = _COMPONENT_LABELS.get(entry.component_code, entry.component_code)
            stem = f"{year}_{_safe(entry.group_name)}"
            # Single-group downloads skip the folder — the zip itself is
            # already named after the group, so a same-named subfolder
            # would just be an extra layer to click through.
            base = f"{stem}/{stem}_{label}" if group_folder else f"{stem}_{label}"

            if entry.file:
                data = _read_entry_bytes(entry)
                original = entry.file.get("name") or "file.bin"
                if data is None:
                    zf.writestr(
                        f"{base}_MISSING.txt",
                        f"Original blob missing: {entry.file.get('storage_key', '?')}\n",
                    )
                else:
                    ext = os.path.splitext(original)[1]
                    ext = f".{_safe(ext[1:])}" if ext else ".bin"
                    zf.writestr(f"{base}{ext}", data)

            if entry.text:
                zf.writestr(f"{base}.txt", entry.text)

            if entry.link:
                zf.writestr(f"{base}_Link.txt", entry.link + "\n")

    return buffer.getvalue()
