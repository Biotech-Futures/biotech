from apps.common.storage import ManagedFileService, get_resource_storage


RESOURCE_FILE_SERVICE = ManagedFileService(get_resource_storage)


def is_external_storage_key(storage_key: str | None) -> bool:
    value = (storage_key or "").strip()
    return value.startswith(("http://", "https://"))


def is_managed_storage_key(storage_key: str | None) -> bool:
    value = (storage_key or "").strip()
    return bool(value) and not is_external_storage_key(value)


def build_managed_storage_name(original_name: str) -> str:
    # Developer note: resource files keep their own container/backend even though
    # the low-level save/delete/open/url mechanics are shared in common.storage.
    return RESOURCE_FILE_SERVICE.build_storage_name(original_name)


def save_uploaded_resource_file(uploaded_file) -> dict:
    return RESOURCE_FILE_SERVICE.save_uploaded_file(
        uploaded_file,
        content_type_field="file_mime_type",
        size_field="file_size",
    )


def delete_managed_resource_file(storage_key: str | None) -> None:
    if not is_managed_storage_key(storage_key):
        return
    RESOURCE_FILE_SERVICE.delete(storage_key)


def resolve_managed_storage_url(
    storage_key: str | None,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    as_attachment: bool = False,
):
    if not is_managed_storage_key(storage_key):
        return None
    return RESOURCE_FILE_SERVICE.resolve_url(
        storage_key,
        filename=filename,
        content_type=content_type,
        as_attachment=as_attachment,
    )


def open_managed_resource_file(storage_key: str):
    return RESOURCE_FILE_SERVICE.open(storage_key, "rb")
