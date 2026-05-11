from __future__ import annotations

from apps.common.storage import ManagedFileService, get_chat_storage


CHAT_FILE_SERVICE = ManagedFileService(get_chat_storage)


def stored_chat_file(uploaded_file):
    # Context manager: deletes blob on caller-side error.
    return CHAT_FILE_SERVICE.stored_file(
        uploaded_file,
        original_filename_field="attachment_filename",
        content_type_field="attachment_mime_type",
        size_field="attachment_size",
    )
