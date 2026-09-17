"""Shared path every system email goes through: toggle check, render, send.

Senders use three pieces:

* ``is_email_enabled(key)``: honours the per-type and global switches.
* ``render_system_email(key, context)``: the finished subject, HTML and plain text,
  using the admin's saved wording when there is some, otherwise the template file.
* ``send_system_email(key, to, context)``: all of the above for a single recipient.

Batch senders (announcements, reminders, the digest) check and render once, then
call ``build_message`` per recipient inside their existing send loops.

Admin-written text is never passed to Django's template engine: only merge tags
listed in the email registry are substituted, with their values HTML-escaped.
Bodies are expected to be sanitised when they are saved (and before previewing).
"""

import html as html_lib
import logging
import re
from datetime import date, datetime
from typing import NamedTuple, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import DatabaseError
from django.template.loader import render_to_string
from django.utils import dateformat
from django.utils.html import strip_tags

from .email_branding import attach_inline_logo, brand_context
from .email_registry import MERGE_TAG_RE, get_email_type
from .mailer import send_async
from .models import SystemEmailSettings, SystemEmailTemplate

logger = logging.getLogger(__name__)

SENT = "sent"
SKIPPED = "skipped"
FAILED = "failed"

WRAPPER_TEMPLATE = "emails/system_wrapper.html"


class RenderedEmail(NamedTuple):
    subject: str
    html: str
    text: str


# --- toggles ---------------------------------------------------------------

def is_email_enabled(key: str) -> bool:
    """Whether emails of type ``key`` may be sent right now.

    Locked types always send. With no rows saved, every type is enabled. A
    database error fails open: a missed toggle is better than silently dropping
    emails people are waiting on.
    """
    email_type = get_email_type(key)
    if email_type.locked:
        return True

    try:
        # Read without get(): checking a switch must never create the row.
        globally_enabled = (
            SystemEmailSettings.objects
            .filter(pk=SystemEmailSettings.SINGLETON_PK)
            .values_list("emails_enabled", flat=True)
            .first()
        )
        if globally_enabled is False:
            return False

        type_enabled = (
            SystemEmailTemplate.objects
            .filter(key=key)
            .values_list("is_enabled", flat=True)
            .first()
        )
        return type_enabled is not False
    except DatabaseError:
        logger.exception("system_email.toggle_check_failed key=%s", key)
        return True


# --- merge tags ------------------------------------------------------------

def _format_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return dateformat.format(value, "j M Y, H:i")
    if isinstance(value, date):
        return dateformat.format(value, "j M Y")
    return str(value)


def fill_tags(text: str, key: str, context: dict, *, escape: bool = True) -> str:
    """Replace ``{{ tag }}`` with values from ``context`` for tags ``key`` allows.

    Values are HTML-escaped unless ``escape`` is False (subjects and plain text)
    or the tag is a trusted HTML snippet built by code. Tags the type doesn't
    allow are left exactly as written and logged.
    """
    email_type = get_email_type(key)
    context = context or {}

    def replace(match):
        name = match.group(1)
        tag = email_type.tag(name)
        if tag is None:
            logger.warning("system_email.unknown_tag key=%s tag=%s", key, name)
            return match.group(0)
        value = _format_value(context.get(tag.context_key))
        if escape and not tag.html:
            value = html_lib.escape(value)
        return value

    return MERGE_TAG_RE.sub(replace, text or "")


def _clean_subject(subject: str) -> str:
    # A newline in a subject is a header-injection vector; flatten to one line.
    return " ".join((subject or "").split())


# --- plain text ------------------------------------------------------------

_DROPPED_BLOCKS_RE = re.compile(r"<(style|script|head|title)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_COMMENTS_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HIDDEN_PREHEADER_RE = re.compile(r"<div[^>]*display:\s*none[^>]*>.*?</div>", re.IGNORECASE | re.DOTALL)
_LINK_RE = re.compile(r"<a\b[^>]*\bhref=\"([^\"]+)\"[^>]*>(.*?)</a\s*>", re.IGNORECASE | re.DOTALL)
_LINE_BREAK_RE = re.compile(r"<br\s*/?>|</(p|div|h[1-6]|li|tr|table|ul|ol)\s*>", re.IGNORECASE)
_LIST_ITEM_RE = re.compile(r"<li\b[^>]*>", re.IGNORECASE)


def html_to_text(html: str) -> str:
    """A readable plain-text version of an email's HTML.

    Unlike ``strip_tags`` alone, this drops <style> blocks (which would otherwise
    show as CSS at the top of the message), keeps link targets, and keeps
    paragraph breaks.
    """
    text = _DROPPED_BLOCKS_RE.sub("", html or "")
    text = _COMMENTS_RE.sub("", text)
    text = _HIDDEN_PREHEADER_RE.sub("", text)

    def link(match):
        href = match.group(1)
        label = " ".join(strip_tags(match.group(2)).split())
        if not label or label == href or href.startswith("mailto:"):
            return label or href
        return f"{label} ({href})"

    text = _LINK_RE.sub(link, text)
    text = _LIST_ITEM_RE.sub("- ", text)
    text = _LINE_BREAK_RE.sub("\n", text)
    text = html_lib.unescape(strip_tags(text))

    lines = [" ".join(line.split()) for line in text.splitlines()]
    collapsed = []
    for line in lines:
        if line or (collapsed and collapsed[-1]):
            collapsed.append(line)
    return "\n".join(collapsed).strip()


# --- rendering -------------------------------------------------------------

def _load_override(key: str) -> Optional[SystemEmailTemplate]:
    try:
        return SystemEmailTemplate.objects.filter(key=key).first()
    except DatabaseError:
        # Fall back to the template file: login emails must keep working even
        # if the overrides table is unavailable.
        logger.exception("system_email.override_load_failed key=%s", key)
        return None


def render_system_email(
    key: str,
    context: Optional[dict] = None,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    *,
    default_text: Optional[str] = None,
) -> RenderedEmail:
    """Render email ``key`` into its subject, HTML and plain text. Sends nothing.

    Wording is chosen per part, in this order:
      1. ``subject`` / ``body`` passed in (unsaved text, used by preview)
      2. the admin's saved subject / body
      3. the registry's default subject / the template file

    ``default_text`` is the sender's existing plain-text version, used when the
    body comes from the template file. Without it, plain text is derived from
    the HTML.
    """
    email_type = get_email_type(key)
    ctx = {**brand_context(), **(context or {})}

    override = None
    if subject is None or body is None:
        override = _load_override(key)

    if subject is None:
        subject = override.subject if override else ""
    if body is None:
        body = override.body_html if override else ""

    subject_source = subject if subject.strip() else email_type.default_subject
    rendered_subject = _clean_subject(fill_tags(subject_source, key, ctx, escape=False))

    if body.strip():
        body_html = fill_tags(body, key, ctx, escape=True)
        html = render_to_string(WRAPPER_TEMPLATE, {
            **ctx,
            "EMAIL_SUBJECT": rendered_subject,
            "BODY_HTML": body_html,
        })
        text = html_to_text(body_html)
    else:
        html = render_to_string(email_type.default_template, ctx)
        text = default_text if default_text is not None else html_to_text(html)

    return RenderedEmail(rendered_subject, html, text)


# --- sending ---------------------------------------------------------------

def build_message(
    rendered: RenderedEmail,
    to,
    *,
    from_email: Optional[str] = None,
    connection=None,
) -> EmailMultiAlternatives:
    """An ``EmailMultiAlternatives`` for one rendered email, with the logo attached."""
    recipients = [to] if isinstance(to, str) else list(to)
    message = EmailMultiAlternatives(
        subject=rendered.subject,
        body=rendered.text,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        connection=connection,
    )
    message.attach_alternative(rendered.html, "text/html")
    attach_inline_logo(message)
    return message


def send_system_email(
    key: str,
    to,
    context: Optional[dict] = None,
    *,
    default_text: Optional[str] = None,
    background: bool = False,
    connection=None,
    from_email: Optional[str] = None,
) -> str:
    """Check, render and send email ``key`` to one recipient.

    Returns ``SENT``, ``SKIPPED`` (type switched off) or ``FAILED``. Never raises
    for send errors. With ``background=True`` the message is handed to the mail
    pool and ``SENT`` means queued.
    """
    if not is_email_enabled(key):
        logger.info("system_email.skipped_disabled key=%s", key)
        return SKIPPED

    # Rendered here, not in the pool: the worker thread must do no ORM work.
    rendered = render_system_email(key, context, default_text=default_text)
    message = build_message(rendered, to, from_email=from_email, connection=connection)

    if background:
        send_async(message, kind=key)
        return SENT

    try:
        message.send(fail_silently=False)
    except Exception as exc:
        # Not logger.exception: SMTP errors carry recipient addresses in their args.
        logger.error("system_email.send_failed key=%s error=%s", key, type(exc).__name__)
        return FAILED
    return SENT
