"""Lightweight text sanitisation, shared across chat messages and upload filenames.

Single Responsibility: this module owns the blacklist + replacement logic and
nothing else. The public ``sanitize_text`` function is a pure function that can
be unit-tested without Django/DRF/Channels. Django settings are consulted only
through a lazy import, so the same function works in non-Django contexts (e.g.
the unit-test suite that runs without ``DJANGO_SETTINGS_MODULE``).

Design decisions
----------------
1. **Persistent mutation, not display-time filtering.**
   ``sanitize_text`` is applied *before* ``serializer.save()`` so the cleaned
   text is what is persisted to the database and broadcast over WebSocket. The
   raw input is intentionally not preserved — the requirement is to protect
   younger students, and a leaky audit trail (e.g. an admin endpoint that
   bypassed the chat serializer) would defeat that. Capture raw text in an
   audit log *before* this filter if you ever need it for moderation review.

2. **Configurable via Django settings / env vars.** ``CHAT_SANITIZER_BLACKLIST``
   (comma-separated) and ``CHAT_SANITIZER_REPLACEMENT`` override the defaults
   without code changes. See ``config/settings.py``.

3. **Stems vs whole-words.** Each blacklist entry is one of:
     - **Stem** (trailing ``*``):  substring match.
       ``fuck*`` catches ``fuck``, ``fucker``, ``fucking``, ``motherfucker``,
       ``brainfuck``, ``clusterfuck``, ``fuckface``, ``f*ck``, ``fuuuck`` —
       any word that contains the stem (or its leet/spaced variant).
       Surrounding letters of the host word are gobbled into the replacement
       so ``motherfucker`` -> ``***``, not ``mother***er``.
     - **Whole-word** (no trailing ``*``):  letter-boundary match.
       Used for letter sequences that are too common as substrings to safely
       treat as stems — e.g. ``hell`` would otherwise flag ``hello``,
       ``hellish``, ``helmet``, and ``ass`` would flag ``passive``, ``Mass``,
       ``embarrass``, ``Massachusetts``.

4. **Bypass resistance** (applies to both stems and whole-words):
     - case variants:                  ``SHIT`` / ``Shit``
     - leetspeak digits / symbols:     ``sh1t``, ``5h1t``, ``$h!t``, ``5hlthole``
     - censoring stars:                ``f*ck``, ``sh*t``
     - punctuation injection:          ``s.h.i.t``, ``s*h*i*t``
     - spaced-out (gap <= 2 chars):    ``s h i t``
     - repeated letters:               ``shiiiit``, ``fuuuck``
     - visual i/l swap:                ``5hlthole`` (l reading as i)

5. **Known accepted false positives** (substring stems intentionally trade
   precision for coverage; document, don't whack-a-mole):
     - ``shitake`` / ``shiitake`` (mushroom)   — stem ``shit*``   matches
     - ``Scunthorpe`` (English town)           — stem ``cunt*``   matches
     - ``peacock``, ``cocktail``, ``cockpit``  — stem ``cock*``   matches
     - ``Dick`` (the given name)               — stem ``dick*``   matches
     - ``pussycat``, ``pussyfoot``             — stem ``pussy*``  matches
     - ``snigger`` / ``sniggered``             — stem ``nigger*`` matches
   Override via ``CHAT_SANITIZER_BLACKLIST`` env var if these are unacceptable
   for your audience (e.g. drop ``cock*`` to keep peacock, or downgrade
   ``pussy*`` to a whole-word ``pussy`` to keep ``pussycat``).

6. **Will NOT catch:** zero-width-space attacks, homoglyph attacks
   (cyrillic ``а`` for latin ``a``), creative misspellings, transliteration.
   Pair with rate-limiting + reporting for serious abuse.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable

# Default blacklist used when Django settings are unavailable or unset.
# Production runtime reads from ``settings.CHAT_SANITIZER_BLACKLIST``.
#
# Convention: trailing ``*`` = substring stem, no ``*`` = whole-word.
# A stem catches every compound automatically — ``fuck*`` covers ``fucker``,
# ``brainfuck``, ``motherfucker``, ``clusterfuck``, etc. without needing
# individual entries.
DEFAULT_BLACKLIST: tuple[str, ...] = (
    # Stems — substring match (low false-positive rate; few innocent English
    # words share these letter sequences). Stems also catch leet/spaced
    # variants automatically, so e.g. ``fuck*`` covers ``fucker``,
    # ``brainfuck``, ``f*ck`` and ``fuuuck`` without separate entries.
    "fuck*", "shit*", "dick*", "bitch*", "cock*", "cunt*", "prick*",
    "pussy*", "nigger*", "nigga*", "faggot*", "nigga*",
    # Whole-word — letter sequences too common as substrings to safely stem
    # (e.g. ``hell`` inside ``hello``, ``ass`` inside ``passive`` / ``class``).
    "hell", "damn", "crap", "piss", "ass",
    "asshole", "arsehole", "asshat", "bastard", "wanker", "twat"
)

DEFAULT_REPLACEMENT = "***"

# Common leetspeak substitutions. Each letter accepts the listed chars in
# addition to itself. The asterisk is added globally so partial-censor attempts
# like "f*ck" are still caught.
#
# Note: we deliberately add cross-letter visual swaps where the glyphs are
# nearly identical — most importantly ``i <-> l`` (vertical strokes), so
# attempts like ``5hlthole`` (l standing in for i) and ``bul1shit`` (1 already
# covered) are still caught. False-positive risk is low because the surrounding
# letters of the target word still have to align.
LEET_MAP: dict[str, str] = {
    "a": "a@4",
    "b": "b8",
    "c": "c(",
    "e": "e3",
    "g": "g69",
    "h": "h#",
    "i": "i1!|l",
    "l": "l1|i",
    "o": "o0",
    "s": "s$5z",
    "t": "t7+",
    "u": "uv",
}

# Allow up to this many non-word characters (spaces, punctuation) between
# consecutive letters of a stem. Bounded so the regex can't run away.
MAX_GAP_BETWEEN_LETTERS = 2

# When a stem matches inside a word, we extend the match to swallow the rest
# of the host word so e.g. ``motherfucker`` becomes ``***`` (not ``mother***er``).
# Letters + digits only: deliberately excludes symbols like ``! @ $`` so that
# trailing punctuation in ``oh, shit!`` is preserved instead of consumed.
# Side effect: leet symbols *outside* the stem (e.g. the ``@`` in ``br@1nfuck``)
# stop the gobbler, so we may match ``nfuck`` instead of the whole ``br@1nfuck``
# in that pathological case. The stem is still censored, just the prefix
# survives — acceptable trade-off for keeping punctuation intact.
_HOST_WORD_CHAR = r"[A-Za-z0-9]"

# Marker used in blacklist entries to flag substring stems. Any other entry is
# treated as a whole word with letter-boundary lookarounds.
STEM_MARKER = "*"


def _letter_class(letter: str) -> str:
    """Build a regex character class for one letter, including leet variants."""
    variants = LEET_MAP.get(letter, letter) + "*"
    # Preserve order, dedupe, and escape inside a character class.
    seen: dict[str, None] = {}
    for ch in variants:
        seen.setdefault(ch, None)
    escaped = "".join(re.escape(ch) for ch in seen)
    return f"[{escaped}]+"


def _build_word_pattern(word: str) -> str:
    """Inner pattern for one blacklisted word with leet + spacing tolerance."""
    letter_patterns = [_letter_class(c) for c in word.lower() if c.isalpha()]
    if not letter_patterns:
        return r"(?!)"
    gap = rf"[\W_]{{0,{MAX_GAP_BETWEEN_LETTERS}}}"
    return gap.join(letter_patterns)


def _split_blacklist(blacklist: Iterable[str]) -> tuple[list[str], list[str]]:
    """Partition entries into (stems, whole_words). Trailing ``*`` = stem."""
    stems: set[str] = set()
    whole_words: set[str] = set()
    for raw in blacklist:
        if not raw:
            continue
        entry = raw.strip().lower()
        if not entry:
            continue
        if entry.endswith(STEM_MARKER):
            stem = entry[:-1].strip()
            if stem:
                stems.add(stem)
        else:
            whole_words.add(entry)
    return (
        sorted(stems, key=len, reverse=True),
        sorted(whole_words, key=len, reverse=True),
    )


def _build_pattern(blacklist: Iterable[str]) -> re.Pattern[str]:
    """Compile one regex covering every blacklisted word + stem.

    Whole-words are anchored with letter-boundary lookarounds (Scunthorpe
    protection). Stems are unanchored and additionally swallow the surrounding
    letters of the host word, so a single match consumes ``motherfucker`` whole
    rather than leaving an ``er`` suffix behind.

    Both kinds of entries are sorted longest-first so longer matches win over
    shorter overlapping ones (e.g. ``shithead`` beats ``shit``).
    """
    stems, whole_words = _split_blacklist(blacklist)
    if not stems and not whole_words:
        return re.compile(r"(?!)")

    parts: list[str] = []
    # Whole-word arms first — strict boundary, no surrounding gobbling.
    for w in whole_words:
        inner = _build_word_pattern(w)
        parts.append(rf"(?<![A-Za-z]){inner}(?![A-Za-z])")
    # Stem arms second — surrounded by greedy host-word eaters.
    for s in stems:
        inner = _build_word_pattern(s)
        parts.append(rf"{_HOST_WORD_CHAR}*{inner}{_HOST_WORD_CHAR}*")

    return re.compile("|".join(parts), flags=re.IGNORECASE)


@lru_cache(maxsize=8)
def _cached_pattern(blacklist_key: tuple[str, ...]) -> re.Pattern[str]:
    return _build_pattern(blacklist_key)


def _resolve_settings() -> tuple[tuple[str, ...], str]:
    """Pull blacklist + replacement from Django settings if configured."""
    try:
        from django.conf import settings

        blacklist = tuple(getattr(settings, "CHAT_SANITIZER_BLACKLIST", DEFAULT_BLACKLIST))
        replacement = getattr(settings, "CHAT_SANITIZER_REPLACEMENT", DEFAULT_REPLACEMENT)
    except Exception:
        blacklist, replacement = DEFAULT_BLACKLIST, DEFAULT_REPLACEMENT
    return blacklist, replacement


def sanitize_text(
    text: str | None,
    blacklist: Iterable[str] | None = None,
    replacement: str | None = None,
) -> str:
    """Return ``text`` with blacklisted words replaced by ``replacement``.

    Pure function: deterministic, no I/O, no global state mutation. ``None`` is
    coerced to ``""`` so callers don't have to special-case missing input.
    Non-string input raises ``TypeError`` — silent passthrough was flagged in
    review as a type-hint violation.

    Parameters
    ----------
    text:
        Input string. ``None`` -> ``""``.
    blacklist:
        Optional override. Defaults to ``settings.CHAT_SANITIZER_BLACKLIST``
        (or ``DEFAULT_BLACKLIST`` outside Django).
    replacement:
        Optional override. Defaults to ``settings.CHAT_SANITIZER_REPLACEMENT``
        (or ``DEFAULT_REPLACEMENT``).
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        raise TypeError(
            f"sanitize_text expects str | None, got {type(text).__name__}"
        )
    if not text:
        return text

    if blacklist is None or replacement is None:
        default_blacklist, default_replacement = _resolve_settings()
        if blacklist is None:
            blacklist = default_blacklist
        if replacement is None:
            replacement = default_replacement

    pattern = _cached_pattern(tuple(sorted({w for w in blacklist if w})))
    return pattern.sub(replacement, text)


def reset_pattern_cache() -> None:
    """Test helper: drop the LRU-cached compiled patterns. Use this after
    ``override_settings(CHAT_SANITIZER_*=...)`` in tests so the next call to
    :func:`sanitize_text` rebuilds with the updated configuration."""
    _cached_pattern.cache_clear()
