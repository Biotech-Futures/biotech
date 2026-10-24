"""Re-export shim. Real implementation lives in ``apps.common.text``."""

import re

from apps.common.text import (  # noqa: F401
    DEFAULT_BLACKLIST,
    DEFAULT_REPLACEMENT,
    LEET_MAP,
    MAX_GAP_BETWEEN_LETTERS,
    STEM_MARKER,
    contains_blacklisted,
    reset_pattern_cache,
    sanitize_text,
)


_MENTION_RE = re.compile(r"<@(\d+)>")
# The same tokens whole, captured so ``re.split`` keeps them in the result.
_MENTION_TOKEN_RE = re.compile(r"(<@\d+>)")
# Bare ``@everyone`` keyword. Mirrors the FE pattern at
# GroupDetailPage.vue:3494 so a message authored in the composer survives
# the round-trip and still gets fanned out server-side. The lookbehind
# rejects ``foo@everyone`` and ``@@everyone`` so only standalone usages
# count.
_EVERYONE_RE = re.compile(r"(?<![\w@])@everyone\b", re.IGNORECASE)


def sanitize_message_text(text: str | None) -> str:
    """``sanitize_text`` for a chat message: the text around its ``<@123>``
    mention tokens is filtered, the tokens themselves never are. The filter
    reads "@" and digits as letters, so a token like ``<@555>`` reads "@55"
    as "ass", and filtering it would drop the mention."""
    parts = _MENTION_TOKEN_RE.split(text or "")
    return "".join(part if i % 2 else sanitize_text(part) for i, part in enumerate(parts))


def message_contains_blacklisted(text: str | None) -> bool:
    """``contains_blacklisted`` for a chat message, with the same carve-out
    as ``sanitize_message_text``: only the text around its ``<@123>`` mention
    tokens is read, so a mention can never get a message refused."""
    return any(contains_blacklisted(part) for part in _MENTION_TOKEN_RE.split(text or "")[::2])


def parse_mentions(text: str) -> tuple[set[int], bool]:
    """Extract mentions from ``text``.

    Returns a tuple of (user IDs from ``<@123>`` tokens, ``@everyone`` flag).
    The two token shapes are kept distinct because ``@everyone`` resolves
    against group membership at apply-time — the caller cannot know who
    "everyone" is without the message's group context.

    Duplicates collapse; the ``@everyone`` flag is a single bool regardless
    of how many times the keyword appears.
    """
    if not text:
        return set(), False
    user_ids = {int(m) for m in _MENTION_RE.findall(text)}
    has_everyone = bool(_EVERYONE_RE.search(text))
    return user_ids, has_everyone
