"""Backwards-compatible shim — sanitize_text now lives in apps.common.text.

The text-sanitization helpers were promoted to ``apps.common`` so
``apps.common.filenames`` could reuse them without depending on the chat app
(which would have created a common -> chat import cycle). Existing imports
from ``apps.chat.utils`` keep working via this re-export.
"""

from apps.common.text import (  # noqa: F401
    DEFAULT_BLACKLIST,
    DEFAULT_REPLACEMENT,
    LEET_MAP,
    MAX_GAP_BETWEEN_LETTERS,
    STEM_MARKER,
    reset_pattern_cache,
    sanitize_text,
)
