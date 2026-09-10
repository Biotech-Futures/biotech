"""Per-slot rules for the three submission attachments.

Slots are fixed by the competition: a poster, an optional scientific report,
and an optional prototype. The first two must be PDFs; the third is
deliberately open-ended.
"""
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

# Every PDF begins with this. Some exporters emit a BOM or whitespace first,
# so the first kilobyte is searched rather than only the opening bytes.
_PDF_MAGIC = b"%PDF-"
_PDF_MAGIC_SEARCH_BYTES = 1024


def _looks_like_pdf(uploaded_file) -> bool:
    """True when the file's *contents* actually start as a PDF.

    Extension and declared content type are both supplied by the client and
    are trivially faked — renaming ``notes.txt`` to ``poster.pdf`` passes both.
    Reading the file itself is the only check that means anything.
    """
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
        # Always rewind: whatever we do next has to read from the start.
        try:
            seek(0)
        except Exception:
            pass
    return bool(head) and _PDF_MAGIC in head


def max_size_for(slot: str) -> int:
    """Upload ceiling for one slot.

    The PDF slots are held to a tighter limit than the prototype, which may
    legitimately be an archive, a CAD model or a video.
    """
    if slot in PDF_SLOTS:
        return settings.SUBMISSION_PDF_MAX_UPLOAD_SIZE
    return settings.SUBMISSION_FILE_MAX_UPLOAD_SIZE


def max_sizes() -> dict:
    """Per-slot ceilings, published so the page can state and pre-check them."""
    return {slot: max_size_for(slot) for slot in SLOTS}


def validate_submission_file(uploaded_file, slot: str):
    """Validate one upload against the rules for its slot.

    Raises ``serializers.ValidationError`` with a message meant to be shown to
    the student, since a rejected upload needs to say what to do about it.
    """
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

    # Prototype: anything a team might plausibly build, minus executables.
    return validate_unrestricted_upload(
        uploaded_file,
        max_size=max_size,
        field_label=label,
    )
