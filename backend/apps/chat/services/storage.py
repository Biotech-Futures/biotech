from __future__ import annotations

from apps.common.storage import ManagedFileService, get_chat_storage


CHAT_FILE_SERVICE = ManagedFileService(get_chat_storage)


def save_uploaded_chat_file(uploaded_file) -> dict:
    # Developer note: chat attachments stay isolated from resource files at the
    # storage backend level; only the repeated mechanics are shared.
    return CHAT_FILE_SERVICE.save_uploaded_file(
        uploaded_file,
        original_filename_field="attachment_filename",
        content_type_field="attachment_mime_type",
        size_field="attachment_size",
    )
