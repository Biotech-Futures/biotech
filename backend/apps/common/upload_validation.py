from __future__ import annotations

from pathlib import Path

from rest_framework import serializers


def _normalized_extensions(values) -> set[str]:
    return {
        str(value).strip().lower().lstrip(".")
        for value in (values or [])
        if str(value).strip()
    }


def _normalized_mime_types(values) -> set[str]:
    return {
        str(value).strip().lower()
        for value in (values or [])
        if str(value).strip()
    }


def _format_bytes(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size // (1024 * 1024)} MB"
    if size >= 1024:
        return f"{size // 1024} KB"
    return f"{size} bytes"


def validate_uploaded_file(
    uploaded_file,
    *,
    max_size: int,
    allowed_extensions,
    allowed_mime_types,
    field_label: str,
):
    if uploaded_file is None:
        return uploaded_file

    file_size = getattr(uploaded_file, "size", None)
    if file_size is not None and file_size > max_size:
        raise serializers.ValidationError(
            f"{field_label} exceeds the maximum allowed size of {_format_bytes(max_size)}."
        )

    extension = Path(getattr(uploaded_file, "name", "")).suffix.lower().lstrip(".")
    normalized_extensions = _normalized_extensions(allowed_extensions)
    if not extension or extension not in normalized_extensions:
        raise serializers.ValidationError(
            f"{field_label} must use an allowed file extension."
        )

    content_type = (getattr(uploaded_file, "content_type", "") or "").strip().lower()
    normalized_mime_types = _normalized_mime_types(allowed_mime_types)
    if not content_type or content_type not in normalized_mime_types:
        raise serializers.ValidationError(
            f"{field_label} must use an allowed content type."
        )

    return uploaded_file
