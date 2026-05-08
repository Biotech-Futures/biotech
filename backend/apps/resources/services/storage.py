from apps.common.storage import ManagedFileService, get_resource_storage


RESOURCE_FILE_SERVICE = ManagedFileService(get_resource_storage)


def is_external_storage_key(storage_key: str | None) -> bool:
    value = (storage_key or "").strip()
    return value.startswith(("http://", "https://"))


def is_managed_storage_key(storage_key: str | None) -> bool:
    value = (storage_key or "").strip()
    return bool(value) and not is_external_storage_key(value)


def save_uploaded_resource_file(uploaded_file) -> dict:
    # Developer note: resource files keep their own container/backend even though
    # the low-level save/delete/open/url mechanics are shared in common.storage.
    return RESOURCE_FILE_SERVICE.save_uploaded_file(
        uploaded_file,
        content_type_field="file_mime_type",
        size_field="file_size",
    )
