from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from django.utils import timezone
from django.utils.text import slugify

from apps.common.storage import get_chat_storage


def build_managed_attachment_name(original_name: str) -> str:
    original = Path(original_name or "attachment.bin").name
    suffix = Path(original).suffix.lower()
    stem = slugify(Path(original).stem) or "attachment"
    day = timezone.now().strftime("%Y/%m/%d")
    # Attachment keys are also container-relative so chat files can move between local
    # and Azure storage backends without changing the persisted message data shape.
    return f"{day}/{uuid4().hex}/{stem}{suffix}"


def original_filename(name: str | None) -> str:
    return Path(name or "attachment.bin").name


def save_uploaded_chat_file(uploaded_file) -> dict:
    storage = get_chat_storage()
    storage_name = build_managed_attachment_name(uploaded_file.name)
    saved_name = storage.save(storage_name, uploaded_file)
    return {
        "storage_key": saved_name,
        "attachment_filename": original_filename(uploaded_file.name),
        "attachment_mime_type": getattr(uploaded_file, "content_type", None) or None,
        "attachment_size": getattr(uploaded_file, "size", None),
    }


def delete_managed_chat_file(storage_key: str | None) -> None:
    if not storage_key:
        return
    storage = get_chat_storage()
    if storage.exists(storage_key):
        storage.delete(storage_key)


def resolve_managed_chat_file_url(
    storage_key: str | None,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    as_attachment: bool = False,
):
    if not storage_key:
        return None
    try:
        return get_chat_storage().url(
            storage_key,
            filename=filename,
            content_type=content_type,
            as_attachment=as_attachment,
        )
    except Exception:
        return None


def open_managed_chat_file(storage_key: str):
    return get_chat_storage().open(storage_key, "rb")

