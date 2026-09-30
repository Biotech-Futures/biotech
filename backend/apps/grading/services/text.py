"""Text for the Word documents and spreadsheets the app builds: made safe
for them, and team names put in order.

Both are XML inside, which can't hold control characters. One pasted into
an answer, title or comment (Word's Shift+Enter is a vertical tab, its page
break a form feed) would otherwise stop the whole file being made: a marks
summary, the SAQ export, a supervisor's marks sheet. So Word's two breaks
become spaces and the rest are dropped.
"""
from __future__ import annotations

import re

_WORD_BREAKS = str.maketrans({"\x0b": " ", "\x0c": " "})
_NOT_XML_RE = re.compile("[\x00-\x08\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


def xml_safe(text: str) -> str:
    return _NOT_XML_RE.sub("", text.translate(_WORD_BREAKS))


def natural_key(text: str) -> tuple:
    """Sorts "BTF2" before "BTF10": runs of digits compare as numbers."""
    # Splitting on a captured group puts the digit runs at the odd places.
    parts = re.split(r"(\d+)", text.lower())
    return tuple(int(part) if i % 2 else part for i, part in enumerate(parts))
