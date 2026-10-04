"""The in-app announcement to the finalist groups that have been emailed,
posted from Notify Finalists. Its wording starts as the finalist email's,
with this year's dates and link, until an admin edits it. Posting again
updates the one already posted, for every group emailed by then, and brings
it back to the top."""
from __future__ import annotations

import re
from html import escape

from django.utils import timezone

from apps.admin.services.announcement import create_announcement, update_announcement
from apps.announcements.models import Announcement
from apps.grading.models import FinalistFlag

from ..models import FinalistAnnouncement, FinalistEmailSettings
from .finalist_notify import render_finalist_email

# Who the email's greeting is to, in an announcement every finalist group sees.
GROUP_NAME = "our finalist teams"

_URL = re.compile(r"https?://[^\s<>]+")


def _inline(text: str) -> str:
    """A line of the email as HTML, its web addresses as links."""
    out, last = [], 0
    for match in _URL.finditer(text):
        url = match.group(0).rstrip(".,;)")
        out.append(escape(text[last:match.start()]))
        out.append(f'<a href="{escape(url)}">{escape(url)}</a>')
        last = match.start() + len(url)
    out.append(escape(text[last:]))
    return "".join(out)


def text_to_html(text: str, title: str = "") -> str:
    """The email's plain text as an announcement's HTML: its paragraphs and
    "- " lists, with links, and without its title line or footer."""
    text = text.split("\n--\n")[0].strip()
    html = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or (not html and title and " ".join(lines) == title):
            continue
        lead, items = [], []
        for line in lines:
            if line.startswith("- "):
                items.append(line[2:])
            elif items:
                items[-1] += " " + line
            else:
                lead.append(line)
        if lead:
            html.append(f"<p>{_inline(' '.join(lead))}</p>")
        if items:
            html.append("<ul>" + "".join(f"<li>{_inline(item)}</li>" for item in items) + "</ul>")
    return "".join(html)


def default_wording() -> tuple[str, str]:
    """The finalist email's subject and text, as an announcement."""
    rendered = render_finalist_email(GROUP_NAME, FinalistEmailSettings.load())
    return rendered.subject, text_to_html(rendered.text, rendered.subject)


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
