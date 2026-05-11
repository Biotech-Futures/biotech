from __future__ import annotations

import html
import re
import unicodedata

from django.utils.text import slugify

from apps.common.text import sanitize_text


DEFAULT_UPLOAD_STEM = "uploaded-file"
FILENAME_PROFANITY_REPLACEMENT = "redacted"
MAX_FILENAME_LENGTH = 128
MAX_EXTENSION_LENGTH = 16
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

_CONTROL_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn"}
_HTML_TAG_RE = re.compile(r"<[^>]*>")
_WHITESPACE_RE = re.compile(r"\s+")
_EXTENSION_RE = re.compile(rf"^(?P<stem>.*?)(?P<extension>\.[A-Za-z0-9]{{1,{MAX_EXTENSION_LENGTH}}})?$")


def _strip_control_characters(value: str) -> str:
    return "".join(ch for ch in value if unicodedata.category(ch) not in _CONTROL_CATEGORIES)


def _sanitize_candidate(value: str) -> str:
    candidate = html.unescape(value or "")
    candidate = unicodedata.normalize("NFKC", candidate)
    candidate = _strip_control_characters(candidate)
    candidate = candidate.replace("\\", "/").replace("/", " ")
    while ".." in candidate:
        candidate = candidate.replace("..", " ")
    candidate = _HTML_TAG_RE.sub(" ", candidate)
    candidate = candidate.replace("<", " ").replace(">", " ")
    candidate = _WHITESPACE_RE.sub(" ", candidate)
    return candidate.strip()


def _split_extension(value: str) -> tuple[str, str]:
    match = _EXTENSION_RE.match(value)
    if not match:
        return value, ""
    stem = (match.group("stem") or "").strip(" ._-")
    extension = (match.group("extension") or "").lower()
    return stem, extension


def sanitize_upload_filename(original_filename: str | None) -> str:
    cleaned = _sanitize_candidate(str(original_filename or ""))
    stem, extension = _split_extension(cleaned)

    # Developer note: filenames reuse the existing chat profanity filter so upload
    # naming follows the same configurable moderation policy as message text.
    sanitized_stem = sanitize_text(stem, replacement=FILENAME_PROFANITY_REPLACEMENT)
    sanitized_stem = sanitized_stem.replace(".", " ")
    # Keep non-Latin chars (CJK, Cyrillic). Security relies on ext/MIME/magic checks.
    sanitized_stem = slugify(sanitized_stem, allow_unicode=True)

    max_stem_length = max(1, MAX_FILENAME_LENGTH - len(extension))
    sanitized_stem = sanitized_stem[:max_stem_length].rstrip("._-")
    if not sanitized_stem or sanitized_stem.upper() in WINDOWS_RESERVED_NAMES:
        sanitized_stem = DEFAULT_UPLOAD_STEM[:max_stem_length].rstrip("._-") or "file"

    return f"{sanitized_stem}{extension}"
