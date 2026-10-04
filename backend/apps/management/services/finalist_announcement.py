"""The in-app announcement to the finalist groups that have been emailed,
posted from Notify Finalists. Its wording starts as the finalist email's,
with this year's dates, its box and its Register button, until an admin
edits it. Posting again updates the one already posted, for every group
emailed by then, and brings it back to the top."""
from __future__ import annotations

import re

from django.utils import timezone

from apps.admin.services.announcement import create_announcement, update_announcement
from apps.admin.services.system_email import _render_content_block
from apps.announcements.models import Announcement
from apps.grading.models import FinalistFlag
from apps.services.email_branding import brand_context
from apps.services.email_registry import get_email_type
from apps.services.system_email import _load_override, clean_email_body, fill_tags

from ..models import FinalistAnnouncement, FinalistEmailSettings
from .finalist_notify import EMAIL_KEY, finalist_email_context, render_finalist_email

# The email's greeting is to one group by name; the announcement greets them all.
GROUP_NAME = "finalists"
_GREETING = re.compile(r"members of\s*(?:<strong>)?\s*finalists\s*(?:</strong>)?")
# Its block tags, with the template's indenting around them dropped.
_BLOCK_TAG = re.compile(r"\s*(</?(?:p|div|h[1-6]|ul|ol|li)\b[^>]*>)\s*")
_LINK_TEXT = re.compile(r"(<a\b[^>]*>)\s*(.*?)\s*(</a>)", re.DOTALL)
# The template's boxes and button fill with `background:#hex`; kept as
# `background-color`, as the editor does (emailBlocks.ts cleanEmailStyle).
_FILL = re.compile(r"(?<![\w-])background\s*:\s*(#[0-9a-f]{3,8}|[a-z]+|rgba?\([\d\s.,%]+\))\s*(?=[;\"])", re.IGNORECASE)


def _email_body(context: dict) -> str:
    """The finalist email's body, filled in: an admin's saved wording (from
    System Emails) if there is some, else the template's."""
    override = _load_override(EMAIL_KEY)
    if override and override.body_html.strip():
        return fill_tags(override.body_html, EMAIL_KEY, context, escape=True)
    return _render_content_block(get_email_type(EMAIL_KEY).default_template, context)


def as_announcement(html: str) -> str:
    """The email's body as an announcement: its boxes, headings, lists and
    button kept, its first heading (the title) gone, its greeting to all the
    finalists, and "reply to this email" pointing at the email."""
    html = re.sub(r"^\s*<h1\b[^>]*>.*?</h1>", "", html, count=1, flags=re.DOTALL | re.IGNORECASE)
    html = _GREETING.sub("finalists", html)
    html = html.replace("reply to this email", "reply to the finalist email we sent you")
    html = _BLOCK_TAG.sub(r"\1", re.sub(r"\s+", " ", html)).strip()
    html = _LINK_TEXT.sub(r"\1\2\3", _FILL.sub(r"background-color:\1", html))
    # Only the boxes' and button's own styles are kept, so the rest reads in
    # the site's own look.
    return clean_email_body(html)


def default_wording() -> tuple[str, str]:
    """The finalist email's subject and body, as an announcement."""
    details = FinalistEmailSettings.load()
    rendered = render_finalist_email(GROUP_NAME, details)
    context = {**brand_context(), **finalist_email_context(GROUP_NAME, details)}
    return rendered.subject, as_announcement(_email_body(context))


def wording(row: FinalistAnnouncement) -> tuple[str, str]:
    """The title and body it posts: the edited ones, else the email's."""
    return (row.title, row.body) if row.edited_at else default_wording()


def notified_group_ids() -> list[int]:
    """The finalist groups that have been emailed: the ones that see it."""
    return list(
        FinalistFlag.objects.filter(notified=True, group__deleted_at__isnull=True)
        .order_by("group_id")
        .values_list("group_id", flat=True)
    )


def post(actor) -> FinalistAnnouncement:
    """Post it to the groups emailed so far: a new announcement the first
    time (or once the last was archived or deleted), else the same one
    updated and back at the top. Raises ValueError with none to post to."""
    group_ids = notified_group_ids()
    if not group_ids:
        raise ValueError("No finalist group has been emailed yet.")
    row = FinalistAnnouncement.load()
    title, body = wording(row)
    fields = {"title": title, "body": body, "group_ids": group_ids, "send_email": False}
    existing = row.announcement if row.announcement and row.announcement.archived_at is None else None
    now = timezone.now()
    if existing is None:
        created = create_announcement(fields, initiated_by=actor)["data"]
        row.announcement_id = created["id"]
    else:
        update_announcement(existing.id, fields, initiated_by=actor)
        Announcement.objects.filter(id=existing.id).update(published_at=now)
    row.posted_at = now
    row.posted_by = actor
    row.save()
    return row
