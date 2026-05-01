"""Lightweight text sanitisation for chat messages.

Single Responsibility: this module owns the blacklist + replacement logic and
nothing else. It has no Django, DRF, or Channels imports so the public
``sanitize_text`` function can be unit-tested as a pure function.

Call sites (REST serializer, WebSocket consumer) import ``sanitize_text`` and
apply it to the raw user-supplied text before the message is persisted.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# Default blacklist applied to every chat message. Lowercase entries only;
# matching is case-insensitive at runtime. Kept intentionally short — the goal
# is a lightweight filter, not a full profanity model. Extend by editing this
# tuple or by passing a custom ``blacklist=`` to ``sanitize_text``.
DEFAULT_BLACKLIST: tuple[str, ...] = (
    "damn",
    "hell",
    "shit",
    "fuck",
    "fucking",
    "fucker",
    "bitch",
    "bastard",
    "asshole",
    "arsehole",
    "crap",
    "dick",
    "piss",
    "cunt",
    "wanker",
    "twat",
)

REPLACEMENT = "***"


def _build_pattern(blacklist: Iterable[str]) -> re.Pattern[str]:
    # Sort longest first so e.g. "fucking" is tried before "fuck"; without this
    # the shorter alternative could win and leave a partial match in place.
    words = sorted({w.lower() for w in blacklist if w}, key=len, reverse=True)
    if not words:
        # ``(?!)`` is a regex that can never match, which gives a no-op sub().
        return re.compile(r"(?!)")
    alternation = "|".join(re.escape(w) for w in words)
    # ``\b`` word boundaries avoid the Scunthorpe problem — substrings inside
    # other words ("classic", "shitake") are not censored.
    return re.compile(rf"\b(?:{alternation})\b", flags=re.IGNORECASE)


_DEFAULT_PATTERN = _build_pattern(DEFAULT_BLACKLIST)


def sanitize_text(text: str, blacklist: Optional[Iterable[str]] = None) -> str:
    """Return ``text`` with any blacklisted word replaced by ``***``.

    Pure function: deterministic, no I/O, no global state mutation, no Django
    dependencies. Safe to unit-test in isolation.

    Non-string and empty inputs are returned unchanged so the caller does not
    have to special-case them.
    """
    if not isinstance(text, str) or not text:
        return text
    pattern = _DEFAULT_PATTERN if blacklist is None else _build_pattern(blacklist)
    return pattern.sub(REPLACEMENT, text)
