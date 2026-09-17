"""Validation rules for the poster, report and prototype attachments."""
from __future__ import annotations

from django.conf import settings
from rest_framework import serializers

from apps.common.upload_validation import (
    validate_unrestricted_upload,
    validate_uploaded_file,
)


POSTER = "poster"
REPORT = "report"
PROTOTYPE = "prototype"

SLOTS = (POSTER, REPORT, PROTOTYPE)
PDF_SLOTS = (POSTER, REPORT)

SLOT_LABELS = {
    POSTER: "Poster",
    REPORT: "Scientific report",
    PROTOTYPE: "Prototype",
}

_PDF_EXTENSIONS = ("pdf",)
_PDF_MIME_TYPES = ("application/pdf",)

# Searched for in the first kilobyte, since some exporters write a BOM first.
_PDF_MAGIC = b"%PDF-"
_PDF_MAGIC_SEARCH_BYTES = 1024


def _looks_like_pdf(uploaded_file) -> bool:
    """Whether the file's contents are a PDF; its name and declared type can be faked."""
    read = getattr(uploaded_file, "read", None)
    seek = getattr(uploaded_file, "seek", None)
    if read is None or seek is None:
        return False
    try:
        seek(0)
        head = read(_PDF_MAGIC_SEARCH_BYTES)
    except Exception:
        return False
    finally:
        try:
            seek(0)
        except Exception:
            pass
    return bool(head) and _PDF_MAGIC in head


def max_size_for(slot: str) -> int:
    if slot in PDF_SLOTS:
        return settings.SUBMISSION_PDF_MAX_UPLOAD_SIZE
    return settings.SUBMISSION_FILE_MAX_UPLOAD_SIZE


def max_sizes() -> dict:
    return {slot: max_size_for(slot) for slot in SLOTS}


def validate_submission_file(uploaded_file, slot: str):
    """Raise a student-facing ValidationError if the upload breaks its slot's rules."""
    if slot not in SLOTS:
        raise serializers.ValidationError(f"Unknown attachment slot '{slot}'.")

    label = SLOT_LABELS[slot]
    max_size = max_size_for(slot)

    if slot in PDF_SLOTS:
        validate_uploaded_file(
            uploaded_file,
            max_size=max_size,
            allowed_extensions=_PDF_EXTENSIONS,
            allowed_mime_types=_PDF_MIME_TYPES,
            field_label=label,
        )
        if not _looks_like_pdf(uploaded_file):
            raise serializers.ValidationError(
                f"{label} must be a PDF. The file was named like one but its "
                "contents are not a PDF."
            )
        return uploaded_file

    # The prototype accepts any type except executables.
    return validate_unrestricted_upload(
        uploaded_file,
        max_size=max_size,
        field_label=label,
    )
