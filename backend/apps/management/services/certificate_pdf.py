"""Certificates as PDFs, for the results emails and every certificate download.

A filled Word certificate is converted by Gotenberg (LibreOffice behind a small
web service), run as a sidecar beside the backend, at CERTIFICATE_PDF_URL
(e.g. http://localhost:3000). Unset, or when the converter fails or doesn't
answer in time, a certificate stays the Word file it was, so results emails
and downloads never stop for it.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PDF = "application/pdf"
# Certificates converted at once for a zip or an email's attachments.
_WORKERS = 4


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


def to_pdf(docx: bytes, name: str) -> bytes | None:
    """The certificate as a PDF, or None when there's no converter or it failed."""
    url = _url()
    if not url:
        return None
    try:
        response = requests.post(
            f"{url}/forms/libreoffice/convert",
            files={"files": (_word_name(name), docx)},
            timeout=float(getattr(settings, "CERTIFICATE_PDF_TIMEOUT_SECONDS", 30)),
        )
    except requests.RequestException as exc:
        logger.error("certificate_pdf.unreachable name=%s error=%s", name, type(exc).__name__)
        return None
    if response.status_code != 200 or not response.content.startswith(b"%PDF"):
        logger.error("certificate_pdf.refused name=%s status=%s", name, response.status_code)
        return None
    return response.content


def as_pdf(name: str, docx: bytes, mimetype: str) -> tuple[str, bytes, str]:
    """``(name, data, mimetype)`` for the certificate: the PDF when it converts,
    otherwise the Word file under its Word name."""
    pdf = to_pdf(docx, name)
    if pdf is None:
        return _word_name(name), docx, mimetype
    return pdf_name(name), pdf, PDF


def many_as_pdf(files: list[tuple[str, bytes, str]]) -> list[tuple[str, bytes, str]]:
    """``as_pdf`` for each, a few at a time, in the order given."""
    if not enabled() or len(files) < 2:
        return [as_pdf(*file) for file in files]
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        return list(pool.map(lambda file: as_pdf(*file), files))
