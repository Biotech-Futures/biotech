"""URL detection + OpenGraph metadata extraction.

Pure functions only — no network I/O, no Django, no Redis, **no third-party
HTML parser**. The worker in ``apps.chat.tasks`` is the side-effecting wrapper
that calls into here.

Keeping the parsing layer pure means:

1. Unit tests can drive it with raw HTML fixtures, no mocking.
2. We can swap the underlying transport (requests / aiohttp / httpx) without
   touching the parser.
3. ``fetch_og_data`` stays small and trivially auditable.

The parser uses Python's stdlib ``html.parser`` — enough for ``<meta>`` tag
extraction (the only thing we need for OG). Skipping BeautifulSoup drops one
runtime dependency.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlparse


# We deliberately only match http/https schemes — the worker fetches whatever
# URL we surface, so allowing ``file://`` / ``ftp://`` / ``javascript:`` would
# be a SSRF / arbitrary-read foot-gun. ``\b`` boundaries keep us from matching
# inside identifiers like ``my_https_token``.
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
    to the fetcher.
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


class _MetaCollector(HTMLParser):
    """Collect ``<meta>`` attribute dicts and the contents of ``<title>``.

    We only care about the document's ``<head>``; anything past ``<body>`` is
    irrelevant for OG, so we stop recording then to save work on huge pages.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: list[dict[str, str]] = []
        self._title_parts: list[str] = []
        self._in_title = False
        self._stopped = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._stopped:
            return
        tag = tag.lower()
        if tag == "meta":
            self.meta.append(
                {k.lower(): (v or "") for k, v in attrs}
            )
        elif tag == "title":
            self._in_title = True
        elif tag == "body":
            self._stopped = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "head":
            self._stopped = True

    def handle_data(self, data: str) -> None:
        if self._in_title and not self._stopped:
            self._title_parts.append(data)

    @property
    def title(self) -> str:
        return "".join(self._title_parts).strip()


def _meta_lookup(metas: Iterable[dict[str, str]], names: Iterable[str]) -> str | None:
    """Return the first non-empty ``<meta>`` content value matching ``names``.

    OpenGraph uses ``property=`` while Twitter / generic descriptors use
    ``name=`` — we check both and take the first hit, in the order ``names``
    was supplied.
    """
    wanted = tuple(n.lower() for n in names)
    for name in wanted:
        for meta in metas:
            key = meta.get("property") or meta.get("name") or ""
            if key.lower() != name:
                continue
            value = (meta.get("content") or "").strip()
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

    parser = _MetaCollector()
    try:
        parser.feed(html)
    except Exception:
        # html.parser is tolerant; this catches only catastrophic cases.
        # Whatever we collected so far is still usable.
        pass

    title = (
        _meta_lookup(parser.meta, ("og:title", "twitter:title"))
        or parser.title
        or ""
    )
    desc = _meta_lookup(
        parser.meta, ("og:description", "twitter:description", "description")
    ) or ""
    img_raw = _meta_lookup(
        parser.meta, ("og:image", "og:image:url", "twitter:image", "twitter:image:src")
    ) or ""
    img = urljoin(base_url, img_raw) if img_raw else ""

    return {"title": title, "desc": desc, "img": img}
