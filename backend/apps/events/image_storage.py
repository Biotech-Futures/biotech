"""Durable storage + URL signing for event banner images.

The blob is private, so an event's ``event_image`` column stores only the durable
blob *key* (or an external absolute URL an admin pasted). A fresh, short-lived
signed URL is minted on every read via :func:`resolve_event_image_url`. Persisting
the signed URL itself (the old behaviour) meant the link died after
``AZURE_URL_EXPIRATION_SECS`` and the image stopped loading.

Security: because reads now mint a *valid* signature for whatever key they are
given, the key is validated before signing — otherwise a crafted ``event_image``
(e.g. ``.../media/<some-other-blob>``) would let a caller obtain a signed read URL
for an arbitrary blob in the shared ``media`` container. Only a bare, single-segment
filename with an image extension is ever signed.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from urllib.parse import urlparse

from django.conf import settings
from storages.backends.azure_storage import AzureStorage

from apps.common.storage import ManagedContainerStorage

logger = logging.getLogger(__name__)

# Blobs live at the root of this container (see upload_event_image); the
# "event-images" namespace only names the local-dev media subfolder.
_EVENT_IMAGE_CONTAINER = "media"
_ALLOWED_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")


@lru_cache(maxsize=1)
def get_event_image_storage() -> ManagedContainerStorage:
    # Cached because reads sign one URL per event row — rebuilding the Azure
    # client per row on a list endpoint would be needless overhead.
    class EventImageAzureStorage(AzureStorage):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("azure_container", _EVENT_IMAGE_CONTAINER)
            kwargs.setdefault("expiration_secs", settings.AZURE_URL_EXPIRATION_SECS)
            kwargs.setdefault("custom_domain", settings.AZURE_CUSTOM_DOMAIN or None)
            connection_string = getattr(settings, "AZURE_CONNECTION_STRING", "") or ""
            if connection_string:
                kwargs.setdefault("connection_string", connection_string)
            super().__init__(*args, **kwargs)

    return ManagedContainerStorage("event-images", EventImageAzureStorage)


def reset_event_image_storage_cache() -> None:
    # Prod never flips USE_AZURE_BLOB_STORAGE at runtime; tests do via override_settings.
    get_event_image_storage.cache_clear()


def _account_name_from_connection_string() -> str:
    # Ops may configure Azure via connection string only (no AZURE_ACCOUNT_NAME);
    # pull the account name out of it so legacy-URL recovery still matches our host.
    conn = getattr(settings, "AZURE_CONNECTION_STRING", "") or ""
    for part in conn.split(";"):
        if part.strip().lower().startswith("accountname="):
            return part.split("=", 1)[1].strip()
    return ""


def _managed_hosts() -> set[str]:
    hosts = set()
    account = (getattr(settings, "AZURE_ACCOUNT_NAME", "") or "") or _account_name_from_connection_string()
    if account:
        hosts.add(f"{account}.blob.core.windows.net")
    custom = getattr(settings, "AZURE_CUSTOM_DOMAIN", "") or ""
    if custom:
        hosts.add(custom)
    return hosts


def _is_safe_key(key: str | None) -> bool:
    """A signable event-image key: a single-segment image filename, no traversal.

    Blocks ``/`` and ``\\`` (nested/other-prefix blobs like ``resources/x.pdf``) and
    ``..`` (traversal), and requires an image extension — so only the event-image
    namespace at the container root is ever signable.
    """
    if not key or "/" in key or "\\" in key or ".." in key:
        return False
    return key.lower().endswith(_ALLOWED_EXTS)


def _classify(value: str):
    """Return ('key', safe_key) | ('url', external_url) | (None, None)."""
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        if parsed.netloc in _managed_hosts():
            path = parsed.path.lstrip("/")
            prefix = f"{_EVENT_IMAGE_CONTAINER}/"
            key = path[len(prefix):] if path.startswith(prefix) else path
            return ("key", key) if _is_safe_key(key) else (None, None)
        # External absolute URL: only http(s) is rendered; reject javascript:/data:/file:.
        if parsed.scheme in ("http", "https"):
            return ("url", value)
        return (None, None)
    # No scheme → a bare blob key.
    return ("key", value) if _is_safe_key(value) else (None, None)


def extract_event_image_key(value: str | None) -> str | None:
    """Normalize an incoming/stored value to what we persist.

    A signed URL for our own blob → its bare key (so an edit round-trip can't
    re-persist an expiring link); an external http(s) URL → unchanged; anything
    unsafe (traversal, non-image, bad scheme) → ``None``.
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    _, normalized = _classify(value)
    return normalized


def resolve_event_image_url(value: str | None) -> str | None:
    """Turn a stored value (blob key, legacy SAS URL, or external URL) into a fresh URL."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None

    kind, normalized = _classify(value)
    if kind == "url":
        return normalized
    if kind == "key":
        try:
            return get_event_image_storage().url(normalized)
        except Exception:
            # Surface Azure/SAS misconfig instead of every banner silently vanishing.
            logger.exception("Failed to sign event image URL for key %s", normalized)
            return None
    return None
