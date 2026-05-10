from __future__ import annotations

from apps.common.storage import ManagedFileService, get_chat_storage


CHAT_FILE_SERVICE = ManagedFileService(get_chat_storage)


def stored_chat_file(uploaded_file):
    # Chat attachments stay isolated from resource files at the storage backend level;
    # only the repeated mechanics are shared. Use as a context manager so a DB rollback
    # after the upload deletes the orphan blob.
    return CHAT_FILE_SERVICE.stored_file(
        uploaded_file,
        original_filename_field="attachment_filename",
        content_type_field="attachment_mime_type",
        size_field="attachment_size",
    )
