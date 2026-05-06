from pathlib import Path
from uuid import uuid4

from django.utils import timezone
from django.utils.text import slugify

from apps.common.storage import get_resource_storage


def is_external_storage_key(storage_key: str | None) -> bool:
    value = (storage_key or "").strip()
    return value.startswith(("http://", "https://"))


def is_managed_storage_key(storage_key: str | None) -> bool:
    value = (storage_key or "").strip()
    return bool(value) and not is_external_storage_key(value)


def build_managed_storage_name(original_name: str) -> str:
    original = Path(original_name or "upload.bin").name
    suffix = Path(original).suffix.lower()
    stem = slugify(Path(original).stem) or "file"
    day = timezone.now().strftime("%Y/%m/%d")
    # Storage keys are container-relative; the resource/chat container split is chosen
    # by the storage backend, not encoded into the key.
    return f"{day}/{uuid4().hex}/{stem}{suffix}"


def save_uploaded_resource_file(uploaded_file) -> dict:
    storage = get_resource_storage()
    storage_name = build_managed_storage_name(uploaded_file.name)
    saved_name = storage.save(storage_name, uploaded_file)
    return {
        "storage_key": saved_name,
        "file_mime_type": getattr(uploaded_file, "content_type", None) or None,
        "file_size": getattr(uploaded_file, "size", None),
    }


def delete_managed_resource_file(storage_key: str | None) -> None:
    if not is_managed_storage_key(storage_key):
        return
    storage = get_resource_storage()
    if storage.exists(storage_key):
        storage.delete(storage_key)


def resolve_managed_storage_url(
    storage_key: str | None,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    as_attachment: bool = False,
):
    if not is_managed_storage_key(storage_key):
        return None
    try:
        return get_resource_storage().url(
            storage_key,
            filename=filename,
            content_type=content_type,
            as_attachment=as_attachment,
        )
    except Exception:
        return None


def open_managed_resource_file(storage_key: str):
    return get_resource_storage().open(storage_key, "rb")
