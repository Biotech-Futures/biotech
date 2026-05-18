import uuid
from typing import Optional

from azure.storage.blob import BlobServiceClient, ContentSettings

# ── Azure Blob config (mirrors blob_upload.py test script) ───────────────────
_ACCOUNT_NAME = "btfuturesblobstorage"
_ACCOUNT_KEY = "SLreKCgSbLMq9th/QXYaSfPGwsRo75J/JxV0OFOp9ZkrRcnuTULShfhpID3aLzxYixGlKSzrWkFR+AStamaR4g=="
_CONTAINER_NAME = "media"
_CONNECTION_STRING = (
    f"DefaultEndpointsProtocol=https;"
    f"AccountName={_ACCOUNT_NAME};"
    f"AccountKey={_ACCOUNT_KEY};"
    f"EndpointSuffix=core.windows.net"
)

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}
_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def upload_event_image(file) -> dict:
    """
    Upload an event image file to Azure Blob Storage.

    Args:
        file: Django InMemoryUploadedFile / TemporaryUploadedFile from request.FILES

    Returns:
        {"msg": ..., "data": {"url": <blob_url>}} on success
        {"msg": ..., "data": None}                on failure
    """
    content_type: str = getattr(file, "content_type", "") or ""
    if content_type not in _ALLOWED_CONTENT_TYPES:
        return {
            "msg": f"Unsupported file type '{content_type}'. Allowed: jpeg, png, gif, webp.",
            "data": None,
        }

    if file.size > _MAX_SIZE_BYTES:
        return {
            "msg": "File too large. Maximum size is 5 MB.",
            "data": None,
        }

    # Build a unique blob name so re-uploads never collide
    ext = _ext_from_content_type(content_type)
    blob_name = f"event-images/{uuid.uuid4().hex}{ext}"

    try:
        blob_service = BlobServiceClient.from_connection_string(_CONNECTION_STRING)
        container = blob_service.get_container_client(_CONTAINER_NAME)
        blob_client = container.get_blob_client(blob_name)

        file.seek(0)
        blob_client.upload_blob(
            file,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
    except Exception as exc:
        return {"msg": f"Upload failed: {exc}", "data": None}

    url = f"https://{_ACCOUNT_NAME}.blob.core.windows.net/{_CONTAINER_NAME}/{blob_name}"
    return {"msg": "Event image uploaded successfully", "data": {"url": url}}


def _ext_from_content_type(content_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(content_type, ".jpg")
