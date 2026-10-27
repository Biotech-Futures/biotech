"""Matching modes shared by the student and mentor algorithms.

Both matchers take the same three modes on the same ``mode`` parameter, so the
vocabulary lives here rather than being spelled out twice (once in each
algorithm) and coerced twice (once in each endpoint). Anything that accepts a
mode - a query string, a service signature, an algorithm entry point - calls
``resolve_match_mode``, so the four layers cannot drift apart on what counts as
a valid value.

An unrecognised mode resolves to ``balanced`` instead of raising: ``?mode=``
comes from a query string, and a typo running the default mode is friendlier
than failing a whole match run. The frontend narrows the value before sending
it, so this is a backstop rather than the primary contract.
"""

from typing import Literal, Optional, Tuple, cast

#: The three matching modes, shared by ``match_mentors`` and ``build_groups``.
MatchMode = Literal["balanced", "strict", "coverage"]

#: Accepted values for the matching ``mode`` parameter.
MATCHING_MODES: Tuple[str, ...] = ("balanced", "strict", "coverage")

#: What an unknown or missing mode falls back to.
DEFAULT_MATCH_MODE: MatchMode = "balanced"


def resolve_match_mode(mode: Optional[str]) -> MatchMode:
    """Return ``mode`` when it is known, otherwise ``balanced``."""
    return cast(MatchMode, mode if mode in MATCHING_MODES else DEFAULT_MATCH_MODE)
