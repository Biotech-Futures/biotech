"""Assertions shared by tests for instrumented outgoing email."""

from __future__ import annotations

import html
import re
from urllib.parse import urlparse

from apps.services.email_tracking import decode_click


CLICK_PATH = "/api/v1/services/email/track/click/"
HREF_RE = re.compile(r"\bhref\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)


def delivered_destination(href: str) -> str:
    """Resolve a signed click URL to the destination a recipient will open.

    Non-web links and uninstrumented preview links are returned unchanged so
    the same assertion works for both rendered previews and delivered email.
    """
    href = html.unescape(href)
    parsed = urlparse(href)
    if CLICK_PATH not in parsed.path:
        return href

    payload = parsed.path.split(CLICK_PATH, 1)[1].rstrip("/")
    decoded = decode_click(payload)
    if decoded is None:
        raise AssertionError(f"Invalid email click-tracking URL: {href}")
    return decoded[1]


def delivered_destinations(html_body: str) -> list[str]:
    """Return the final destinations of every href in an email body."""
    return [delivered_destination(href) for href in HREF_RE.findall(html_body)]
