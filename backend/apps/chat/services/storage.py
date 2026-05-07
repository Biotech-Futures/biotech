from __future__ import annotations

from apps.common.filenames import sanitize_upload_filename
from apps.common.storage import ManagedFileService, get_chat_storage


CHAT_FILE_SERVICE = ManagedFileService(get_chat_storage)


def build_managed_attachment_name(original_name: str) -> str:
    # Developer note: chat attachments stay isolated from resource files at the
    # storage backend level; only the repeated mechanics are shared.
    return CHAT_FILE_SERVICE.build_storage_name(original_name)


def original_filename(name: str | None) -> str:
    return sanitize_upload_filename(name)


def save_uploaded_chat_file(uploaded_file) -> dict:
    return CHAT_FILE_SERVICE.save_uploaded_file(
        uploaded_file,
        original_filename_field="attachment_filename",
        content_type_field="attachment_mime_type",
        size_field="attachment_size",
    )


def delete_managed_chat_file(storage_key: str | None) -> None:
    CHAT_FILE_SERVICE.delete(storage_key)


def resolve_managed_chat_file_url(
    storage_key: str | None,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    as_attachment: bool = False,
):
    return CHAT_FILE_SERVICE.resolve_url(
        storage_key,
        filename=filename,
        content_type=content_type,
        as_attachment=as_attachment,
    )


def open_managed_chat_file(storage_key: str):
    return CHAT_FILE_SERVICE.open(storage_key, "rb")
