from apps.common.storage import ManagedFileService, get_resource_storage


RESOURCE_FILE_SERVICE = ManagedFileService(get_resource_storage)


def is_external_storage_key(storage_key: str | None) -> bool:
    value = (storage_key or "").strip()
    return value.startswith(("http://", "https://"))


def is_managed_storage_key(storage_key: str | None) -> bool:
    value = (storage_key or "").strip()
    return bool(value) and not is_external_storage_key(value)


def stored_resource_file(uploaded_file):
    # Context manager: deletes blob on caller-side error.
    return RESOURCE_FILE_SERVICE.stored_file(
        uploaded_file,
        content_type_field="file_mime_type",
        size_field="file_size",
    )
