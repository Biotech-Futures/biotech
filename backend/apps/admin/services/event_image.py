import uuid
from apps.common.storage import ManagedContainerStorage
from storages.backends.azure_storage import AzureStorage
from django.conf import settings

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
}
_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def _get_event_image_storage() -> ManagedContainerStorage:
    class EventImageAzureStorage(AzureStorage):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("azure_container", "media")
            kwargs.setdefault("expiration_secs", settings.AZURE_URL_EXPIRATION_SECS)
            kwargs.setdefault("custom_domain", settings.AZURE_CUSTOM_DOMAIN or None)
            connection_string = getattr(settings, "AZURE_CONNECTION_STRING", "") or ""
            if connection_string:
                kwargs.setdefault("connection_string", connection_string)
            super().__init__(*args, **kwargs)

    return ManagedContainerStorage("event-images", EventImageAzureStorage)


def upload_event_image(file) -> dict:
    content_type: str = getattr(file, "content_type", "") or ""
    if content_type not in _ALLOWED_CONTENT_TYPES:
        return {
            "msg": f"Unsupported file type '{content_type}'. Allowed: jpeg, png, gif, webp.",
            "data": None,
        }

    if file.size > _MAX_SIZE_BYTES:
        return {"msg": "File too large. Maximum size is 5 MB.", "data": None}

    ext = {"image/jpeg": ".jpg", "image/png": ".png",
           "image/gif": ".gif", "image/webp": ".webp"}.get(content_type, ".jpg")
    blob_name = f"{uuid.uuid4().hex}{ext}"

    try:
        storage = _get_event_image_storage()
        saved_name = storage.save(blob_name, file)
        url = storage.url(saved_name)
    except Exception as exc:
        return {"msg": f"Upload failed: {exc}", "data": None}

    return {"msg": "Event image uploaded successfully", "data": {"url": url}}