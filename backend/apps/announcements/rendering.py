"""How an announcement reads, on the platform and in its email.

The portal renders an announcement body as written when it is HTML, and gives
a plain-text body its paragraphs and line breaks (``plainTextToHtml`` in
``frontend/src/composables/useAnnouncements.ts``). The email must read the
same way, so ``body_to_html`` mirrors that rule here.

An announcement may also greet its reader by name: a body can carry merge
tags such as ``{{ first_name }}``, filled with the reading user's own details
when the announcement is served on the platform, and with each recipient's
details when it is emailed. Unlike system emails (``apps.services.email_registry``)
these tags are not per-email-type and are not filled once for everyone.
"""

import html as html_lib
import re

from apps.services.email_registry import MERGE_TAG_RE, MergeTag

# The tags an announcement body may use. They personalise to whoever is
# reading it, so every value comes from that user.
ANNOUNCEMENT_MERGE_TAGS = (
    MergeTag("first_name", "Reader's first name", "Alex", "first_name"),
    MergeTag("last_name", "Reader's last name", "Chen", "last_name"),
    MergeTag("name", "Reader's full name", "Alex Chen", "name"),
    MergeTag("email", "Reader's email address", "alex@example.com", "email"),
)

_TAGS_BY_NAME = {tag.name: tag for tag in ANNOUNCEMENT_MERGE_TAGS}

# Whether a body is already HTML, as the portal asks it (``renderAnnouncementBody``).
_HTML_RE = re.compile(r"</?[a-z][\s\S]*>", re.IGNORECASE)
# A blank line starts a new paragraph, a single newline a line break.
_PARAGRAPH_RE = re.compile(r"\n{2,}")


def _escape(value: str) -> str:
    return html_lib.escape(value or "")


def body_to_html(body: str) -> str:
    """The body as HTML, the way the portal renders it.

    HTML is kept as written; plain text gets its paragraphs (blank lines) and
    line breaks (single newlines), escaped.
    """
    source = (body or "").strip()
    if not source:
        return ""
    if _HTML_RE.search(source):
        return source
    paragraphs = []
    for paragraph in _PARAGRAPH_RE.split(source):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        paragraphs.append(f"<p>{_escape(paragraph).replace(chr(10), '<br>')}</p>")
    return "".join(paragraphs)


def merge_tag_reference() -> list:
    """The tags an announcement may use, as the composer offers them."""
    return [
        {
            "name": tag.name,
            "description": tag.description,
            "sample": tag.sample,
            "html": tag.html,
        }
        for tag in ANNOUNCEMENT_MERGE_TAGS
    ]


def _context_for_user(user) -> dict:
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    full = f"{first} {last}".strip()
    return {
        "first_name": first,
        "last_name": last,
        "name": full or first,
        "email": (getattr(user, "email", "") or "").strip(),
    }


def fill_merge_tags(text: str, user, *, escape: bool = True) -> str:
    """Replace ``{{ tag }}`` with the reading user's own details.

    Only tags an announcement allows are filled; anything else is left exactly
    as written, so a typo stays visible instead of vanishing. Values are
    HTML-escaped unless ``escape`` is False (subjects and plain text).
    """
    if not text or user is None:
        return text or ""

    context = _context_for_user(user)

    def replace(match):
        tag = _TAGS_BY_NAME.get(match.group(1))
        if tag is None:
            return match.group(0)
        value = str(context.get(tag.context_key, "") or "")
        return _escape(value) if escape else value

    return MERGE_TAG_RE.sub(replace, text)
