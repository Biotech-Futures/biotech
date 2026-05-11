"""Re-export shim. Real implementation lives in ``apps.common.text``."""

from apps.common.text import (  # noqa: F401
    DEFAULT_BLACKLIST,
    DEFAULT_REPLACEMENT,
    LEET_MAP,
    MAX_GAP_BETWEEN_LETTERS,
    STEM_MARKER,
    reset_pattern_cache,
    sanitize_text,
)
