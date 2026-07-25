import uuid

from apps.events.image_storage import get_event_image_storage

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
}
_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


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
        storage = get_event_image_storage()
        saved_name = storage.save(blob_name, file)
    except Exception as exc:
        return {"msg": f"Upload failed: {exc}", "data": None}

    # Persist the durable key, not a signed URL — the URL is minted fresh on read.
    return {"msg": "Event image uploaded successfully", "data": {"key": saved_name}}
