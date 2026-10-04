"""The in-app announcements that go with the emails telling groups their
Challenge outcome: the finalist email (Notify Finalists), the non-finalist
and non-submission emails (Notify Nonfinalist), and the results emails to
groups and to supervisors (Release Results). Each is posted from its email's
page to whoever that email has reached so far: its groups, or for the
supervisor email those supervisors. Its wording starts as its email's, with
this year's dates, its boxes and its buttons, until an admin edits it.
Posting again updates the one already posted, for everyone reached by then,
and brings it back to the top."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from django.utils import timezone

from apps.admin.services.announcement import create_announcement, update_announcement
from apps.admin.services.system_email import _render_content_block
from apps.announcements.models import Announcement
from apps.grading.models import FinalistFlag
from apps.services.email_branding import brand_context
from apps.services.email_registry import get_email_type
from apps.services.system_email import _load_override, clean_email_body, fill_tags, render_system_email
from apps.submissions.services import current_cohort

from ..models import FinalistEmailSettings, OutcomeAnnouncement, ResultsEmailSettings
from . import results_notify, symposium_emails
from .finalist_notify import EMAIL_KEY as FINALIST_EMAIL_KEY
from .finalist_notify import finalist_email_context

# Stands in for the group's or supervisor's name while the email is
# rendered, then becomes the announcement's greeting.
NAME = "[[name]]"
_GREETING = re.compile(r"(?:members of\s*)?(?:<strong>\s*)?" + re.escape(NAME) + r"(?:\s*</strong>)?")
# What the emails say about themselves, as an announcement says it.
_EMAIL_WORDS = (
    ("reply to this email", "reply to the email we sent you"),
    ("by response to this email", "by replying to the email we sent you"),
    ("Attached to this email, you will find", "In the email we sent you, you will find"),
    ("Attached, you’ll find", "In the email we sent you, you’ll find"),
)
# Its block tags, with the template's indenting around them dropped.
_BLOCK_TAG = re.compile(r"\s*(</?(?:p|div|h[1-6]|ul|ol|li)\b[^>]*>)\s*")
_LINK_TEXT = re.compile(r"(<a\b[^>]*>)\s*(.*?)\s*(</a>)", re.DOTALL)
# The template's boxes and button fill with `background:#hex`; kept as
# `background-color`, as the editor does (emailBlocks.ts cleanEmailStyle).
_FILL = re.compile(r"(?<![\w-])background\s*:\s*(#[0-9a-f]{3,8}|[a-z]+|rgba?\([\d\s.,%]+\))\s*(?=[;\"])", re.IGNORECASE)


@dataclass(frozen=True)
class Kind:
    """One outcome email's announcement."""

    email_key: str
    # Who it greets, in place of the group's or supervisor's name.
    greeting: str
    # Who it's for, as its page counts them, e.g. "finalist group".
    noun: str
    # The email's merge tags' values, for this name.
    context: Callable[[str], dict]
    # Who it goes to: the email's groups and people reached so far, as
    # (group ids, user ids).
    audience: Callable[[], tuple[list[int], list[int]]]


def _finalist_groups() -> tuple[list[int], list[int]]:
    groups = (
        FinalistFlag.objects.filter(notified=True, group__deleted_at__isnull=True)
        .order_by("group_id")
        .values_list("group_id", flat=True)
    )
    return list(groups), []


def _team_email_groups(email: symposium_emails.TeamEmail) -> Callable[[], tuple[list[int], list[int]]]:
    """The groups a non-finalist or non-submission email went to: those its
    page counts as emailed, someone on them reached."""
    def groups():
        teams = symposium_emails.audience(email)
        return sorted(teams.emailed | {group_id for group_id, ids in teams.reached.items() if ids}), []
    return groups


def _results_groups() -> tuple[list[int], list[int]]:
    result = results_notify.results_audience()
    key = results_notify.EMAIL_KEYS[results_notify.GROUPS]
    reached = symposium_emails.reached_ids(key, [team.id for team in result.teams])
    return sorted(result.teams_emailed | {group_id for group_id, ids in reached.items() if ids}), []


def _results_supervisors() -> tuple[list[int], list[int]]:
    return [], sorted(results_notify.results_audience().supervisors_emailed)


KINDS = {
    "finalists": Kind(
        FINALIST_EMAIL_KEY, "finalists", "finalist group",
        lambda name: finalist_email_context(name, FinalistEmailSettings.load()),
        _finalist_groups,
    ),
    "nonfinalists": Kind(
        symposium_emails.NONFINALIST.key, "participants", "nonfinalist group",
        lambda name: symposium_emails.email_context(name, FinalistEmailSettings.load()),
        _team_email_groups(symposium_emails.NONFINALIST),
    ),
    "nonsubmissions": Kind(
        symposium_emails.NONSUBMISSION.key, "participants", "nonsubmission group",
        lambda name: symposium_emails.email_context(name, FinalistEmailSettings.load()),
        _team_email_groups(symposium_emails.NONSUBMISSION),
    ),
    "results-groups": Kind(
        results_notify.EMAIL_KEYS[results_notify.GROUPS], "participants", "group",
        lambda name: results_notify.team_email_context(name, ResultsEmailSettings.load(), current_cohort()),
        _results_groups,
    ),
    "results-supervisors": Kind(
        results_notify.EMAIL_KEYS[results_notify.SUPERVISORS], "supervisors", "supervisor",
        lambda name: results_notify.supervisor_email_context(name, current_cohort()),
        _results_supervisors,
    ),
}


def _email_body(key: str, context: dict) -> str:
    """The email's body, filled in: an admin's saved wording (from System
    Emails) if there is some, else the template's."""
    override = _load_override(key)
    if override and override.body_html.strip():
        return fill_tags(override.body_html, key, context, escape=True)
    return _render_content_block(get_email_type(key).default_template, context)


def as_announcement(html: str, greeting: str) -> str:
    """An email's body as an announcement: its boxes, headings, lists and
    buttons kept, its first heading (the title) gone, its greeting to
    everyone it's for, and what it says about itself ("reply to this email",
    "Attached") pointing at the email."""
    html = re.sub(r"^\s*<h1\b[^>]*>.*?</h1>", "", html, count=1, flags=re.DOTALL | re.IGNORECASE)
    html = _BLOCK_TAG.sub(r"\1", re.sub(r"\s+", " ", html)).strip()
    html = _LINK_TEXT.sub(r"\1\2\3", _FILL.sub(r"background-color:\1", html))
    # Only the boxes' and buttons' own styles are kept, so the rest reads in
    # the site's own look.
    html = _GREETING.sub(greeting, clean_email_body(html))
    for email_words, ours in _EMAIL_WORDS:
        html = html.replace(email_words, ours)
    return html


def default_wording(key: str) -> tuple[str, str]:
    """The email's subject and body, as an announcement."""
    kind = KINDS[key]
    context = kind.context(NAME)
    subject = render_system_email(kind.email_key, context).subject.replace(NAME, kind.greeting)
    return subject, as_announcement(_email_body(kind.email_key, {**brand_context(), **context}), kind.greeting)


def load(key: str) -> OutcomeAnnouncement:
    return OutcomeAnnouncement.objects.get_or_create(key=key)[0]


def wording(row: OutcomeAnnouncement) -> tuple[str, str]:
    """The title and body it posts: the edited ones, else the email's."""
    return (row.title, row.body) if row.edited_at else default_wording(row.key)


def post(key: str, actor) -> OutcomeAnnouncement:
    """Post it to whoever its email reached so far: a new announcement the
    first time (or once the last was archived or deleted), else the same one
    updated and back at the top. Raises ValueError with nobody to post to."""
    kind = KINDS[key]
    group_ids, user_ids = kind.audience()
    if not group_ids and not user_ids:
        raise ValueError(f"No {kind.noun} has been emailed yet.")
    row = load(key)
    title, body = wording(row)
    fields = {"title": title, "body": body, "group_ids": group_ids, "user_ids": user_ids, "send_email": False}
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
