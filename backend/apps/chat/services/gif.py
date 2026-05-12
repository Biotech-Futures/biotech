from __future__ import annotations

import hashlib
import json
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_TENOR_BASE = "https://g.tenor.com/v1"
_CACHE_TTL = 60 * 60  # 1 hour


def _cache_key(prefix: str, **kwargs) -> str:
    """Generate a stable cache key from query parameters."""
    raw = json.dumps(kwargs, sort_keys=True)
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"gif:{prefix}:{digest}"


def _map_tenor_result(result: dict) -> dict:
    """Map a single Tenor v1 result to our internal DTO — API key never included."""
    media_list = result.get("media", [])
    media = media_list[0] if media_list else {}
    gif = media.get("gif", {})
    tinygif = media.get("tinygif", {})
    return {
        "id": result.get("id", ""),
        "url": gif.get("url", ""),
        "preview": tinygif.get("url", ""),
    }


def search_gifs(query: str, limit: int = 20) -> list[dict]:
    """Search Tenor for GIFs matching *query*. Results are cached for 1 hour."""
    key = _cache_key("search", query=query, limit=limit)
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            f"{_TENOR_BASE}/search",
            params={
                "q": query,
                "limit": limit,
                "key": settings.TENOR_API_KEY,
                "contentfilter": "medium",
            },
            timeout=5,
        )
        response.raise_for_status()
        results = [_map_tenor_result(r) for r in response.json().get("results", [])]
    except requests.RequestException as exc:
        logger.error("Tenor search failed: %s", exc)
        return []

    cache.set(key, results, _CACHE_TTL)
    return results


def trending_gifs(limit: int = 20) -> list[dict]:
    """Fetch trending GIFs from Tenor. Results are cached for 1 hour."""
    key = _cache_key("trending", limit=limit)
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            f"{_TENOR_BASE}/trending",
            params={
                "limit": limit,
                "key": settings.TENOR_API_KEY,
                "contentfilter": "medium",
            },
            timeout=5,
        )
        response.raise_for_status()
        results = [_map_tenor_result(r) for r in response.json().get("results", [])]
    except requests.RequestException as exc:
        logger.error("Tenor trending failed: %s", exc)
        return []

    cache.set(key, results, _CACHE_TTL)
    return results