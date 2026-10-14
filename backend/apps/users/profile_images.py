from uuid import uuid4
import warnings

from django.conf import settings
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from apps.common.storage import get_profile_image_storage


PROFILE_IMAGE_MAX_BYTES = 5 * 1024 * 1024
PROFILE_IMAGE_TYPES = {
    "image/png": ("png", b"\x89PNG\r\n\x1a\n", "PNG"),
    "image/jpeg": ("jpg", b"\xff\xd8\xff", "JPEG"),
    "image/webp": ("webp", b"RIFF", "WEBP"),
}


def validate_profile_image(uploaded_file):
    if uploaded_file.size > PROFILE_IMAGE_MAX_BYTES:
        raise serializers.ValidationError("Choose an image no larger than 5 MB.")
    content_type = (uploaded_file.content_type or "").lower()
    if content_type not in PROFILE_IMAGE_TYPES:
        raise serializers.ValidationError("Use a PNG, JPEG, or WebP image.")
    extension, signature, image_format = PROFILE_IMAGE_TYPES[content_type]
    header = uploaded_file.read(12)
    uploaded_file.seek(0)
    if not header.startswith(signature) or (image_format == "WEBP" and header[8:12] != b"WEBP"):
        raise serializers.ValidationError("The uploaded file is not a valid image.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(uploaded_file) as image:
                if image.format != image_format:
                    raise serializers.ValidationError("The uploaded file is not a valid image.")
                image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise serializers.ValidationError("The uploaded file is not a valid image.")
    finally:
        uploaded_file.seek(0)
    return content_type, extension


def save_profile_image(user, uploaded_file):
    content_type, extension = validate_profile_image(uploaded_file)
    storage = get_profile_image_storage()
    key = storage.save(f"users/{user.pk}/{uuid4().hex}.{extension}", uploaded_file)
    try:
        user.profile_image_key = key
        user.profile_image_content_type = content_type
        user.save(update_fields=["profile_image_key", "profile_image_content_type"])
    except Exception:
        storage.delete(key)
        raise
    return key


def profile_image_url(user):
    if not user.profile_image_key:
        return None
    url = get_profile_image_storage().url(
        user.profile_image_key, content_type=user.profile_image_content_type or None,
    )
    return f"{settings.BACKEND_URL.rstrip('/')}{url}" if url.startswith("/") else url
