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

The SAQ answers can also come as one PDF per group (``build_saq_pdf_zip``):
``<Year>_<GroupName>_SAQs.pdf``, flat.

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
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Iterable

from fpdf import FPDF

from apps.submissions.services import current_cohort

from .content import ComponentEntry, open_file

logger = logging.getLogger(__name__)


_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(name: str) -> str:
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

# Blob reads are pure network I/O against Azure, so a thread pool overlaps
# them well despite the GIL (the Azure SDK's clients are thread-safe). The
# bulk export reads hundreds of blobs; fetched sequentially, per-request
# round-trips dominated its wall-clock time. 10 workers matches requests'
# default per-host connection pool (urllib3 pool_maxsize) — more would still
# work but would churn extra TLS handshakes and log pool-full warnings.
# _FETCH_AHEAD caps how many fetched-but-unwritten payloads can pile up in
# front of the writer, so peak memory stays close to the sequential
# implementation's.
_FETCH_WORKERS = 10
_FETCH_AHEAD = _FETCH_WORKERS * 2

# Types the program that made them already compressed (PDF makers, cameras,
# Office, video apps): they go into the zip as they are, since compressing
# them again takes time and saves almost nothing. Anything else, our own
# text files and unknown types included, is compressed as before.
_ALREADY_COMPRESSED = frozenset({
    "pdf",
    "jpg", "jpeg", "png", "gif", "webp", "heic",
    "docx", "pptx", "xlsx",
    "zip", "rar", "7z", "gz",
    "mp4", "mov", "mkv", "webm", "avi", "mp3", "m4a",
})


def _compression_for(filename: str) -> int:
    """How a file goes into the zip: stored as-is if already compressed."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return zipfile.ZIP_STORED if extension in _ALREADY_COMPRESSED else zipfile.ZIP_DEFLATED


def build_submissions_zip(
    entries: Iterable[ComponentEntry], *, group_folder: bool = True
) -> bytes:
    """Materialise a zip archive of the given component entries to memory.

    File blobs are prefetched on a thread pool with a bounded look-ahead;
    the archive itself is still written in entry order, so output is
    deterministic. Callers stream small results directly to the client
    (per-group endpoint) or hand the bytes off to storage for async jobs.
    For the current cohort size (~180 groups × ≤ 4 components × a handful
    of MB each) in-memory materialisation stays comfortably below process
    limits; if that grows, swap for a temp-file / true streaming
    implementation.
    """
    year = current_cohort()
    buffer = io.BytesIO()
    entry_iter = iter(entries)
    # (entry, future-or-None) in output order; a future only where the entry
    # has a stored file. ``inflight`` counts unconsumed futures — the bound
    # that keeps look-ahead (and buffered payload bytes) in check.
    pending: deque[tuple[ComponentEntry, Future | None]] = deque()

    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool, zipfile.ZipFile(
        buffer, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as zf:
        inflight = 0

        def top_up() -> None:
            nonlocal inflight
            while inflight < _FETCH_AHEAD:
                entry = next(entry_iter, None)
                if entry is None:
                    return
                future = pool.submit(_read_entry_bytes, entry) if entry.file else None
                if future is not None:
                    inflight += 1
                pending.append((entry, future))

        top_up()
        while pending:
            entry, future = pending.popleft()
            data = None
            if future is not None:
                data = future.result()  # never raises; _read_entry_bytes swallows
                inflight -= 1
            top_up()

            label = _COMPONENT_LABELS.get(entry.component_code, entry.component_code)
            stem = f"{year}_{safe_name(entry.group_name)}"
            # Single-group downloads skip the folder — the zip itself is
            # already named after the group, so a same-named subfolder
            # would just be an extra layer to click through.
            base = f"{stem}/{stem}_{label}" if group_folder else f"{stem}_{label}"

            if entry.file:
                original = entry.file.get("name") or "file.bin"
                if data is None:
                    zf.writestr(
                        f"{base}_MISSING.txt",
                        f"Original blob missing: {entry.file.get('storage_key', '?')}\n",
                    )
                else:
                    ext = os.path.splitext(original)[1]
                    ext = f".{safe_name(ext[1:])}" if ext else ".bin"
                    zf.writestr(f"{base}{ext}", data, compress_type=_compression_for(ext))

            if entry.text:
                # The SAQ answers, under the team's project title.
                text = f"Title: {entry.project_title}\n\n{entry.text}" if entry.project_title else entry.text
                zf.writestr(f"{base}.txt", text)

            if entry.link:
                zf.writestr(f"{base}_Link.txt", entry.link + "\n")

    return buffer.getvalue()


# --- SAQ answers as PDFs ---------------------------------------------------------------

# The PDF's built-in fonts write Windows-1252: accented letters, curly quotes,
# dashes and bullets come through; anything else (emoji, other scripts) is "?".
_PDF_ENCODING = "cp1252"


def _pdf_text(text: str) -> str:
    return text.encode(_PDF_ENCODING, "replace").decode(_PDF_ENCODING)


def saq_pdf(entry: ComponentEntry) -> bytes:
    """One group's SAQ answers as a PDF: "Title: " and its project title, then
    each question in bold, as the submission page has them, with its answer
    below. The group's name is in the file's name."""
    pdf = FPDF(format="A4")
    pdf.core_fonts_encoding = _PDF_ENCODING
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_title(_pdf_text(entry.group_name))
    pdf.add_page()

    # The project title in 14pt, not bold.
    if entry.project_title:
        pdf.set_font("Helvetica", "", 14)
        pdf.multi_cell(0, 7.5, _pdf_text(f"Title: {entry.project_title}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # Questions and answers in 12pt.
    for prompt, answer in entry.answers:
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 6.5, _pdf_text(prompt), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 12)
        pdf.multi_cell(0, 6.5, _pdf_text(answer), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
    return bytes(pdf.output())


def build_saq_pdf_zip(entries: Iterable[ComponentEntry]) -> bytes:
    """A zip of each group's SAQ answers as its own PDF, flat, as the TXT
    download has them: ``<Year>_<GroupName>_SAQs.pdf``."""
    year = current_cohort()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for entry in entries:
            if not entry.answers:
                continue
            # The PDFs it makes are compressed already.
            zf.writestr(
                f"{year}_{safe_name(entry.group_name)}_SAQs.pdf", saq_pdf(entry), compress_type=zipfile.ZIP_STORED,
            )
    return buffer.getvalue()
