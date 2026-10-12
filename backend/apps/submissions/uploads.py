"""Validation rules for the poster, report and prototype attachments."""
from __future__ import annotations

from django.conf import settings
from rest_framework import serializers

from apps.common.upload_validation import (
    _format_bytes,
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


FINALIST_MAX_UPLOAD_SIZE = getattr(settings, "SUBMISSION_FINALIST_MAX_UPLOAD_SIZE", 25 * 1024 * 1024)

# The file's first bytes must match its extension; the declared type is not trusted.
_OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
_ZIP_MAGIC = b"PK\x03\x04"
_PRESENTATION_MIME_TYPES = {
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "ppt": "application/vnd.ms-powerpoint",
}


def _head(uploaded_file, size: int) -> bytes:
    try:
        uploaded_file.seek(0)
        return uploaded_file.read(size) or b""
    except Exception:
        return b""
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass


def _is_pptx(uploaded_file) -> bool:
    import zipfile

    if not _head(uploaded_file, 4).startswith(_ZIP_MAGIC):
        return False
    try:
        with zipfile.ZipFile(uploaded_file) as archive:
            return "ppt/presentation.xml" in archive.namelist()
    except Exception:
        return False
    finally:
        uploaded_file.seek(0)


def validate_presentation_file(uploaded_file):
    """A PDF, PPT or PPTX within the finalist size limit, checked by content."""
    size = getattr(uploaded_file, "size", 0) or 0
    if size > FINALIST_MAX_UPLOAD_SIZE:
        raise serializers.ValidationError(
            f"The presentation is larger than {FINALIST_MAX_UPLOAD_SIZE // (1024 * 1024)} MB."
        )
    name = (getattr(uploaded_file, "name", "") or "").lower()
    extension = name.rsplit(".", 1)[-1] if "." in name else ""
    checks = {
        "pdf": lambda f: _looks_like_pdf(f),
        "pptx": _is_pptx,
        "ppt": lambda f: _head(f, 8) == _OLE_MAGIC,
    }
    if extension not in checks:
        raise serializers.ValidationError("The presentation must be a PDF or PowerPoint file.")
    if not checks[extension](uploaded_file):
        raise serializers.ValidationError(
            f"The file is named like a .{extension} but its contents are not."
        )
    # Stored as the type the content check proved, never the one the uploader declared.
    uploaded_file.content_type = _PRESENTATION_MIME_TYPES[extension]
    return uploaded_file


def max_size_for(slot: str) -> int:
    if slot in PDF_SLOTS:
        return settings.SUBMISSION_PDF_MAX_UPLOAD_SIZE
    return settings.SUBMISSION_FILE_MAX_UPLOAD_SIZE


def max_sizes() -> dict:
    return {slot: max_size_for(slot) for slot in SLOTS}


def _require_pdf(uploaded_file, noun: str, max_size: int) -> None:
    """The checks a student can fix, worded for them; the shared validator still runs after."""
    size = getattr(uploaded_file, "size", None) or 0
    if size > max_size:
        raise serializers.ValidationError(
            f"This file is {_format_bytes(size)}, over the {_format_bytes(max_size)} limit. "
            "Please reduce its size and try again."
        )
    name = (getattr(uploaded_file, "name", "") or "").lower()
    content_type = (getattr(uploaded_file, "content_type", "") or "").strip().lower()
    if not name.endswith(".pdf") or content_type not in _PDF_MIME_TYPES:
        raise serializers.ValidationError(
            f"Your {noun} must be a PDF. Please export it as a PDF and try again."
        )
    if not _looks_like_pdf(uploaded_file):
        raise serializers.ValidationError(
            f"This file is named as a PDF but isn't one. Please export your {noun} as a PDF and try again."
        )


def validate_submission_file(uploaded_file, slot: str):
    """Raise a student-facing ValidationError if the upload breaks its slot's rules."""
    if slot not in SLOTS:
        raise serializers.ValidationError(f"Unknown attachment slot '{slot}'.")

    label = SLOT_LABELS[slot]
    max_size = max_size_for(slot)

    if slot in PDF_SLOTS:
        _require_pdf(uploaded_file, label.lower(), max_size)
        try:
            validate_uploaded_file(
                uploaded_file,
                max_size=max_size,
                allowed_extensions=_PDF_EXTENSIONS,
                allowed_mime_types=_PDF_MIME_TYPES,
                field_label=label,
            )
        except serializers.ValidationError:
            # Size, name and type pass above, so only the security checks are left.
            raise serializers.ValidationError(
                f"This file can't be accepted. Please upload your {label.lower()} as a PDF."
            ) from None
        return uploaded_file

    # The prototype accepts any type except executables.
    return validate_unrestricted_upload(
        uploaded_file,
        max_size=max_size,
        field_label=label,
    )
