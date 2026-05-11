"""Re-export shim. Real implementation lives in ``apps.common.text``."""

import re

from apps.common.text import (  # noqa: F401
    DEFAULT_BLACKLIST,
    DEFAULT_REPLACEMENT,
    LEET_MAP,
    MAX_GAP_BETWEEN_LETTERS,
    STEM_MARKER,
    reset_pattern_cache,
    sanitize_text,
)


_MENTION_RE = re.compile(r"<@(\d+)>")


def parse_mentions(text: str) -> set[int]:
    """Return the set of user IDs referenced by ``<@123>`` tokens in ``text``.

    The token shape is fixed (Slack-style) so the FE owns the
    autocomplete UX while the backend can find mentions without
    ambiguity. Duplicates collapse — a user mentioned twice in the same
    message still gets one ``MessageMention`` row.

    Cross-group membership is *not* enforced here; this util just
    extracts IDs. The serializer is responsible for filtering the
    resulting set against the message's group membership before
    inserting rows.
    """
    if not text:
        return set()
    return {int(m) for m in _MENTION_RE.findall(text)}
