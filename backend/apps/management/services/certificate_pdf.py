"""Certificates as PDFs, for the results emails and every certificate download.

A filled Word certificate is converted by Gotenberg (LibreOffice behind a small
web service), run as a sidecar beside the backend, at CERTIFICATE_PDF_URL
(e.g. http://localhost:3000). A certificate stays the Word file it was, so
results emails and downloads never stop for it, when:

* no converter is set;
* the converter fails or doesn't answer, after one retry; for a minute after
  that, it isn't asked at all, so an outage costs no waiting;
* the PDF doesn't read back as the certificate's own words (a font the
  converter lacks turning text unreadable);
* a batch runs past its time budget (a zip download, inside the request limit).
"""
from __future__ import annotations

import html
import io
import logging
import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

import requests
from django.conf import settings
from pypdf import PdfReader

logger = logging.getLogger(__name__)

PDF = "application/pdf"
# Certificates converted at once for a zip or an email's attachments.
_WORKERS = 4
# Seconds to reach the converter, apart from the time a conversion takes.
_CONNECT_SECONDS = 5
# After a failure, the converter is left alone this long.
_RESTING_SECONDS = 60
# The share of the certificate's words its PDF must read back.
_LEGIBLE_SHARE = 0.8

_resting_until = 0.0
_resting_lock = threading.Lock()


def enabled() -> bool:
    return bool(_url())


def _url() -> str:
    return (getattr(settings, "CERTIFICATE_PDF_URL", "") or "").strip().rstrip("/")


def extension() -> str:
    """What a certificate's file name ends in: "pdf" while the converter is set, else "docx"."""
    return "pdf" if enabled() else "docx"


def pdf_name(name: str) -> str:
    """"..._Amy_Chen.docx" as "..._Amy_Chen.pdf"."""
    stem, dot, _ = name.rpartition(".")
    return f"{stem if dot else name}.pdf"


def _word_name(name: str) -> str:
    stem, dot, _ = name.rpartition(".")
    return f"{stem if dot else name}.docx"


def _resting() -> bool:
    with _resting_lock:
        return time.monotonic() < _resting_until


def _rest() -> None:
    global _resting_until
    with _resting_lock:
        _resting_until = time.monotonic() + _RESTING_SECONDS


def _ask(url: str, docx: bytes, name: str):
    """One request; the response, or None when it couldn't be had."""
    try:
        return requests.post(
            f"{url}/forms/libreoffice/convert",
            files={"files": (_word_name(name), docx)},
            timeout=(_CONNECT_SECONDS, float(getattr(settings, "CERTIFICATE_PDF_TIMEOUT_SECONDS", 30))),
        )
    except requests.RequestException as exc:
        logger.warning("certificate_pdf.unreachable name=%s error=%s", name, type(exc).__name__)
        return None


def _words(text: str) -> list[str]:
    return [word.casefold() for word in re.findall(r"[^\W_]{3,}", text)]


def _docx_text(docx: bytes) -> str:
    """The Word file's own text, text boxes, headers and footers included, a line per paragraph."""
    lines = []
    with zipfile.ZipFile(io.BytesIO(docx)) as archive:
        for part in archive.namelist():
            if re.fullmatch(r"word/(document|header\d*|footer\d*)\.xml", part):
                xml = archive.read(part).decode("utf8", errors="ignore")
                for paragraph in xml.split("</w:p>"):
                    lines.append("".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", paragraph)))
    return html.unescape("\n".join(lines))


def legible(docx: bytes, pdf: bytes) -> bool:
    """Whether the PDF reads back as the certificate: most of its words found
    in the PDF's text, however the converter spaced them."""
    try:
        wanted = _words(_docx_text(docx))
        if not wanted:
            return True
        found = re.sub(r"\s+", "", "".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)).casefold()
    except Exception:  # noqa: BLE001 - a PDF that can't be read isn't legible
        return False
    return sum(word in found for word in wanted) >= _LEGIBLE_SHARE * len(wanted)


def to_pdf(docx: bytes, name: str) -> bytes | None:
    """The certificate as a legible PDF, or None (no converter, a failure, or unreadable text)."""
    url = _url()
    if not url or _resting():
        return None
    response = _ask(url, docx, name)
    if response is None or response.status_code >= 500:
        time.sleep(1)
        response = _ask(url, docx, name)
    if response is None or response.status_code != 200 or not response.content.startswith(b"%PDF"):
        if response is not None:
            logger.error("certificate_pdf.refused name=%s status=%s", name, response.status_code)
        _rest()
        return None
    if not legible(docx, response.content):
        logger.error("certificate_pdf.illegible name=%s", name)
        return None
    return response.content


def as_pdf(name: str, docx: bytes, mimetype: str) -> tuple[str, bytes, str]:
    """``(name, data, mimetype)`` for the certificate: the PDF when it converts,
    otherwise the Word file under its Word name."""
    pdf = to_pdf(docx, name)
    if pdf is None:
        return _word_name(name), docx, mimetype
    return pdf_name(name), pdf, PDF


def _as_word(name: str, docx: bytes, mimetype: str) -> tuple[str, bytes, str]:
    return _word_name(name), docx, mimetype


def many_as_pdf(
    files: list[tuple[str, bytes, str]], budget_seconds: float | None = None
) -> list[tuple[str, bytes, str]]:
    """``as_pdf`` for each, a few at a time, in the order given. With a budget,
    any not converted once it's spent stay Word files, so the batch ends in time."""
    if not enabled() or len(files) < 2:
        return [as_pdf(*file) for file in files]
    pool = ThreadPoolExecutor(max_workers=_WORKERS)
    try:
        futures = [pool.submit(as_pdf, *file) for file in files]
        if budget_seconds is None:
            return [future.result() for future in futures]
        deadline = time.monotonic() + budget_seconds
        done = []
        for file, future in zip(files, futures):
            try:
                done.append(future.result(timeout=max(0.0, deadline - time.monotonic())))
            except FutureTimeout:
                done.append(_as_word(*file))
        late = sum(1 for (name, _, _), (made, _, _) in zip(files, done) if not made.endswith(".pdf"))
        if late:
            logger.warning("certificate_pdf.batch_left_as_word count=%s of=%s", late, len(files))
        return done
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
