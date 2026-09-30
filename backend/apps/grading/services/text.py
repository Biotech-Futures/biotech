"""Text made safe for the Word documents and spreadsheets the app builds.

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
