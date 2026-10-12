from __future__ import annotations

from uuid import uuid4

from django.core.files.base import ContentFile
from rest_framework import serializers

from apps.common.storage import ManagedFileService, get_profile_image_storage


PROFILE_IMAGE_MAX_BYTES = 5 * 1024 * 1024
PROFILE_IMAGE_TYPES = {
    "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": ("jpg", b"\xff\xd8\xff"),
    "image/webp": ("webp", b"RIFF"),
}


def validate_profile_image(uploaded_file) -> tuple[str, str]:
    """Validate the bytes, rather than trusting the browser supplied MIME type."""
    if uploaded_file.size > PROFILE_IMAGE_MAX_BYTES:
        raise serializers.ValidationError({"image": "Choose an image smaller than 5 MB."})

    header = uploaded_file.read(12)
    uploaded_file.seek(0)
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    if content_type not in PROFILE_IMAGE_TYPES:
        raise serializers.ValidationError({"image": "Use a PNG, JPEG, or WebP image."})

    extension, signature = PROFILE_IMAGE_TYPES[content_type]
    is_webp = content_type == "image/webp" and header.startswith(signature) and header[8:12] == b"WEBP"
    if (content_type != "image/webp" and not header.startswith(signature)) or (content_type == "image/webp" and not is_webp):
        raise serializers.ValidationError({"image": "The uploaded file is not a valid image."})
    return content_type, extension


def save_profile_image(*, user, uploaded_file) -> str:
    content_type, extension = validate_profile_image(uploaded_file)
    storage_key = f"users/{user.pk}/{uuid4().hex}.{extension}"
    storage = get_profile_image_storage()
    saved_key = storage.save(storage_key, uploaded_file)
    old_key = user.profile_image_key
    try:
        user.profile_image_key = saved_key
        user.profile_image_content_type = content_type
        user.save(update_fields=["profile_image_key", "profile_image_content_type"])
    except Exception:
        storage.delete(saved_key)
        raise

    if old_key and old_key != saved_key:
        ManagedFileService(get_profile_image_storage).delete(old_key)
    return saved_key
