"""URL detection + OpenGraph metadata extraction.

Pure functions only — no network I/O, no Django, no Redis. The Celery task in
``apps.chat.tasks`` is the side-effecting wrapper that calls into here.

Keeping the parsing layer pure means:

1. The unit tests can drive it with raw HTML fixtures, no mocking.
2. We can swap the underlying transport (requests / aiohttp / httpx) without
   touching the parser.
3. ``fetch_og_data`` stays small and trivially auditable.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


# Spec calls this out as "URL Regex". We deliberately only match http/https
# schemes — the Celery worker fetches whatever URL we surface, so allowing
# ``file://`` / ``ftp://`` / ``javascript:`` would be a SSRF / arbitrary-read
# foot-gun. ``\b`` boundaries keep us from matching inside identifiers like
# ``my_https_token``.
URL_REGEX = re.compile(
    r"\bhttps?://[^\s<>\"'\)\]]+", flags=re.IGNORECASE
)

# Cache namespace — short, colon-separated, MD5-derived (per Redis key-naming
# guidance: don't store full URLs as keys; they waste memory and slow lookups).
CACHE_KEY_PREFIX = "cache:og:"


def extract_urls(text: str | None) -> list[str]:
    """Return every http(s) URL found in ``text`` in order, deduped.

    Trailing punctuation (``.``, ``,``, ``)``, ``]``, ``!``, ``?``) is stripped
    so users typing ``check https://example.com.`` don't have the period sent
    to the fetcher. We don't try to be clever about balanced parentheses —
    the cache + retry logic absorbs the occasional 404.
    """
    if not text:
        return []
    seen: dict[str, None] = {}
    for raw in URL_REGEX.findall(text):
        cleaned = raw.rstrip(".,!?;:)]'\"")
        if not cleaned:
            continue
        parsed = urlparse(cleaned)
        if not parsed.netloc:
            continue
        seen.setdefault(cleaned, None)
    return list(seen)


def has_url(text: str | None) -> bool:
    """``True`` if ``text`` contains at least one http(s) URL.

    Cheaper than ``extract_urls`` because it short-circuits on first match —
    used by the view's hot path during ``POST /chat/.../messages/``.
    """
    if not text:
        return False
    return URL_REGEX.search(text) is not None


def cache_key_for(url: str) -> str:
    """Stable cache key for ``url``.

    MD5 is fine here — we are deduping previews, not signing anything. The
    digest is shorter than the URL and constant-width, which keeps Redis key
    overhead predictable.
    """
    digest = hashlib.md5(url.encode("utf-8")).hexdigest()
    return f"{CACHE_KEY_PREFIX}{digest}"


def _meta_lookup(soup: BeautifulSoup, names: Iterable[str]) -> str | None:
    """Return the first non-empty ``<meta>`` value for any of ``names``.

    OpenGraph uses ``property=`` while Twitter / generic descriptors use
    ``name=`` — we check both and take the first hit.
    """
    for name in names:
        for attr in ("property", "name"):
            tag = soup.find("meta", attrs={attr: name})
            if tag:
                value = (tag.get("content") or "").strip()
                if value:
                    return value
    return None


def parse_og_metadata(html: str, base_url: str) -> dict[str, str]:
    """Parse OG / Twitter / generic meta tags from ``html``.

    Always returns a dict with the three keys the websocket contract requires
    (``title``, ``desc``, ``img``) — empty string when missing — so consumers
    don't have to special-case partial payloads.

    Relative ``og:image`` values (e.g. ``/static/og.png``) are resolved against
    ``base_url`` so the front end can render them without knowing the origin.
    """
    if not html:
        return {"title": "", "desc": "", "img": ""}

    soup = BeautifulSoup(html, "html.parser")

    title = (
        _meta_lookup(soup, ("og:title", "twitter:title"))
        or (soup.title.string.strip() if soup.title and soup.title.string else "")
    )

    desc = _meta_lookup(
        soup, ("og:description", "twitter:description", "description")
    ) or ""

    img_raw = _meta_lookup(
        soup, ("og:image", "og:image:url", "twitter:image", "twitter:image:src")
    ) or ""
    img = urljoin(base_url, img_raw) if img_raw else ""

    return {
        "title": title or "",
        "desc": desc,
        "img": img,
    }
