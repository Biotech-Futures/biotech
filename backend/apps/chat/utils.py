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
# Bare ``@everyone`` keyword. Mirrors the FE pattern at
# GroupDetailPage.vue:3494 so a message authored in the composer survives
# the round-trip and still gets fanned out server-side. The lookbehind
# rejects ``foo@everyone`` and ``@@everyone`` so only standalone usages
# count.
_EVERYONE_RE = re.compile(r"(?<![\w@])@everyone\b", re.IGNORECASE)


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
