"""Tenor v2 GIF proxy with Redis-backed caching.

Why this lives in the backend
-----------------------------
1. The Tenor API key never reaches the browser.
2. Query strings flow through ``contains_blacklisted`` before any upstream call,
   so a slur-laden search returns ``{items: []}`` with zero outbound traffic.
3. Identical search/trending requests share a short Redis TTL so we don't
   re-spend the rate-limit budget on duplicate panel opens.

Fail-soft posture
-----------------
Provider errors (network, HTTP 5xx, JSON decode, missing API key) are caught at
the ``cached_fetch`` boundary and converted to an empty list. Endpoints never
surface a 502 to the client — a flaky upstream just renders an empty GIF panel
with a "No GIFs found" hint, which the FE already handles.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

import requests
from django.conf import settings

from apps.chat.redis_client import get_redis

logger = logging.getLogger(__name__)

TENOR_V1_BASE_URL = "https://g.tenor.com/v1"
TENOR_V2_BASE_URL = "https://tenor.googleapis.com/v2"
# The v1 demo key ``LIVDSRZULELA`` works against the v1 endpoint only. A real
# Google-issued Tenor key is needed for v2. We sniff the configured key to
# decide which base URL + response parser to use, so swapping keys is just an
# env-var change.
_V1_KEY_PREFIX = "LIVDSR"

_MAX_LIMIT = 50
_DEFAULT_LIMIT = 20
_MAX_QUERY_LEN = 120


class GifProviderError(RuntimeError):
    """Raised when the upstream GIF provider cannot serve a result."""


class TenorClient:
    """Thin wrapper around the Tenor ``search`` / ``featured`` (v2) or
    ``trending`` (v1) endpoints.

    Always forwards ``contentfilter=high`` so we get SFW results on the wire.
    The v2 base URL also accepts ``media_filter`` for a slimmer payload; v1
    returns the legacy ``media`` array which we normalise downstream.
    """

    def _api_version(self) -> str:
        key = getattr(settings, "TENOR_API_KEY", "") or ""
        # The published demo key + any short legacy key target v1. Real Google
        # Cloud keys are ~39 characters and target v2.
        if not key:
            return "v1"
        if key.startswith(_V1_KEY_PREFIX) or len(key) < 30:
            return "v1"
        return "v2"

    @property
    def base_url(self) -> str:
        return TENOR_V1_BASE_URL if self._api_version() == "v1" else TENOR_V2_BASE_URL

    def search(self, query: str, pos: str = "", limit: int = _DEFAULT_LIMIT) -> dict[str, Any]:
        return self._call("search", {"q": query, "pos": pos, "limit": limit})

    def featured(self, pos: str = "", limit: int = _DEFAULT_LIMIT) -> dict[str, Any]:
        # v1 names this ``trending``; v2 renamed it to ``featured``.
        endpoint = "trending" if self._api_version() == "v1" else "featured"
        return self._call(endpoint, {"pos": pos, "limit": limit})

    def _call(self, endpoint: str, extra_params: dict[str, Any]) -> dict[str, Any]:
        api_key = getattr(settings, "TENOR_API_KEY", "")
        if not api_key:
            raise GifProviderError("TENOR_API_KEY is not configured")

        params: dict[str, Any] = {
            "key": api_key,
            "contentfilter": "high",
        }
        # v2 supports a richer media-format filter; v1 ignores it but the param
        # is harmless. ``client_key`` is v2-only.
        if self._api_version() == "v2":
            params["client_key"] = getattr(settings, "TENOR_CLIENT_KEY", "biotech-chat")
            params["media_filter"] = "gif,tinygif"

        for k, v in extra_params.items():
            if v in (None, ""):
                continue
            params[k] = v

        url = f"{self.base_url}/{endpoint}"
        timeout = float(getattr(settings, "TENOR_TIMEOUT", 5))
        try:
            response = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            raise GifProviderError(f"Tenor request failed: {exc}") from exc

        if response.status_code >= 400:
            raise GifProviderError(
                f"Tenor returned HTTP {response.status_code} for {endpoint}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise GifProviderError("Tenor response was not JSON") from exc


TENOR = TenorClient()


def _extract_v2_media(entry: dict[str, Any]) -> tuple[str, str]:
    """Pull (gif_url, preview_url) out of a v2 ``media_formats`` block."""
    media_formats = entry.get("media_formats") or {}
    gif = media_formats.get("gif") or {}
    tinygif = media_formats.get("tinygif") or {}
    gif_url = gif.get("url") or ""
    preview_url = tinygif.get("url") or gif_url
    return gif_url, preview_url


def _extract_v1_media(entry: dict[str, Any]) -> tuple[str, str]:
    """Pull (gif_url, preview_url) out of a v1 ``media`` list entry.

    v1 layout::

        {
          "media": [{
            "gif":     {"url": "...full.gif"},
            "tinygif": {"url": "...tiny.gif"},
            ...
          }],
          ...
        }
    """
    media_list = entry.get("media") or []
    media = media_list[0] if media_list else {}
    if not isinstance(media, dict):
        return "", ""
    gif = media.get("gif") or {}
    tinygif = media.get("tinygif") or {}
    gif_url = gif.get("url") or ""
    preview_url = tinygif.get("url") or gif_url
    return gif_url, preview_url


def normalize_tenor(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Convert a Tenor v1 *or* v2 payload to ``{items: [...], next_pos}``.

    Items that lack a usable GIF URL are dropped rather than failing the whole
    page — Tenor occasionally returns records where the requested media format
    is missing. We sniff the payload shape (``media`` array vs ``media_formats``
    dict) instead of relying on the active API version so a mixed response
    can't accidentally come back empty.
    """
    if not isinstance(payload, dict):
        return {"items": [], "next_pos": None}

    raw_items = payload.get("results") or []
    items: list[dict[str, Any]] = []
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        if "media_formats" in entry:
            gif_url, preview_url = _extract_v2_media(entry)
        else:
            gif_url, preview_url = _extract_v1_media(entry)
        if not gif_url:
            continue
        items.append({
            "id": str(entry.get("id") or gif_url),
            "url": gif_url,
            "previewUrl": preview_url,
            "title": entry.get("content_description") or entry.get("title") or "",
        })

    next_pos = payload.get("next") or None
    return {"items": items, "next_pos": next_pos or None}


def _cache_key(endpoint: str, query: str, pos: str, limit: int) -> str:
    digest = hashlib.sha1(
        f"{endpoint}|{query}|{pos}|{limit}".encode("utf-8")
    ).hexdigest()
    return f"cache:gif:{digest}"


def cached_fetch(endpoint: str, query: str, pos: str, limit: int) -> dict[str, Any]:
    """Fetch normalised GIF results from cache or upstream, fail-soft on error.

    ``endpoint`` is ``"search"`` or ``"featured"``. Returns
    ``{"items": [], "next_pos": None}`` if the provider fails so the API never
    surfaces a 5xx to the client.
    """
    cache = get_redis()
    cache_key = _cache_key(endpoint, query, pos, limit)
    try:
        raw = cache.get(cache_key)
    except Exception:  # pragma: no cover - cache failure shouldn't break reads
        raw = None
    if raw:
        try:
            cached = json.loads(raw)
            if isinstance(cached, dict) and "items" in cached:
                return cached
        except ValueError:
            pass

    try:
        if endpoint == "search":
            payload = TENOR.search(query=query, pos=pos, limit=limit)
        elif endpoint == "featured":
            payload = TENOR.featured(pos=pos, limit=limit)
        else:
            raise GifProviderError(f"Unknown GIF endpoint: {endpoint}")
    except GifProviderError as exc:
        logger.info("GIF provider fail-soft: %s", exc)
        return {"items": [], "next_pos": None}

    normalised = normalize_tenor(payload)

    try:
        ttl = int(getattr(settings, "GIF_CACHE_TTL", 300))
        cache.setex(cache_key, ttl, json.dumps(normalised))
    except Exception:  # pragma: no cover - cache failure shouldn't break reads
        pass

    return normalised


def clamp_limit(value: Any) -> int:
    """Clamp incoming ``limit`` query param into ``[1, _MAX_LIMIT]`` with a
    safe default of :data:`_DEFAULT_LIMIT`."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    if n < 1:
        return 1
    if n > _MAX_LIMIT:
        return _MAX_LIMIT
    return n


def clamp_query(value: Any) -> str:
    """Strip + clamp the user query so a runaway URL doesn't reach Tenor."""
    if value is None:
        return ""
    s = str(value).strip()
    return s[:_MAX_QUERY_LEN]


def clamp_pos(value: Any) -> str:
    """Pos cursors are opaque strings; bound length to avoid header abuse."""
    if value is None:
        return ""
    s = str(value).strip()
    return s[:128]
