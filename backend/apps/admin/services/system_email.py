"""Admin-facing read/write access to the system email registry.

These functions power the /api/v1/admin/email-template/ and
/api/v1/admin/email-settings/ endpoints. The registry
(``apps.services.email_registry``) is the single source of truth for what an
email is called, what it says by default and which merge tags it supports; the
persisted overrides live in ``apps.services.models.SystemEmailTemplate``.

Division of labour with the send path (``apps.services.system_email``):

* This module decides what admins may *store* (wording, enabled state) and
  reads it back, always re-reading the registry so the admin UI can never
  offer a merge tag an email cannot fill.
* The send path decides what admins may *send*: ``is_email_enabled`` checks the
  stored toggles, ``render_system_email`` falls back to the template file for
  any email whose stored wording has not been set, and merge tags are only
  replaced when the registry allows them.

Security notes:

* Admin-written bodies are sanitised with ``nh3`` on every save and preview so
  a stored email can never carry a <script> or handler attribute into an inbox.
* Merge tags are validated against the registry before anything is persisted,
  so a subject/body that references a tag the email cannot fill is rejected
  with a field-level error instead of arriving at the recipient literally.
* Locked types (login_code) are rejected by the store path when an admin tries
  to switch them off, so nobody can lock everyone out of their inbox.
"""

import logging
import textwrap

import nh3
from django.db import transaction
from django.template import Context, TemplateDoesNotExist
from django.template.loader import get_template
from django.template.loader_tags import ExtendsNode

from apps.services.email_branding import LOGO_CID, brand_context, logo_data_uri
from apps.services.email_registry import (
    EMAIL_TYPES,
    get_email_type,
    is_known_email_type,
    unknown_merge_tags,
)
from apps.services.models import SystemEmailSettings, SystemEmailTemplate
from apps.services.system_email import build_message, render_system_email

logger = logging.getLogger(__name__)

# Max length must match the model field so a bad row can never be persisted.
SUBJECT_MAX_LENGTH = 255


def _default_body(email_type) -> str:
    """The email's built-in wording for the editor to pre-fill, or '' if unavailable.

    Only the template's ``content`` block is rendered: the brand strip, logo and
    footer are added around every email at send time, so including them here
    would duplicate them once saved. Merge tags are left as ``{{ tag }}`` rather
    than filled with sample values, so a saved edit keeps pulling each
    recipient's real data instead of freezing sample text like "Alex" into it.
    """
    try:
        return _render_content_block(
            email_type.default_template, _placeholder_context(email_type, brand_as_tags=True),
        )
    except TemplateDoesNotExist:
        logger.warning(
            "system_email.default_template_missing key=%s template=%s",
            email_type.key,
            email_type.default_template,
        )
        return ""


def _render_content_block(template_name: str, context: dict) -> str:
    """Render just the ``{% block content %}`` of an email template.

    Falls back to the whole template if it doesn't extend a layout.
    """
    template = get_template(template_name).template
    for node in template.nodelist:
        if isinstance(node, ExtendsNode) and "content" in node.blocks:
            html = node.blocks["content"].nodelist.render(Context(context))
            return textwrap.dedent(html).strip()
    return template.render(Context(context)).strip()


def _serialize_template(email_type, row: SystemEmailTemplate) -> dict:
    """One admin-facing dict for a registry entry, merged with its saved state.

    ``subject``/``body`` are the *saved* wording; when nothing has been saved
    they are empty strings and ``usingSavedContent`` is False, which is exactly
    when the send path falls back to the template file. ``defaultSubject`` /
    ``defaultBody`` mirror that fallback content so the editor can pre-fill
    with the current wording before anyone has customised it.
    """
    return {
        "key": email_type.key,
        "name": email_type.name,
        "description": email_type.description,
        "enabled": row.is_enabled if row is not None else True,
        "locked": email_type.locked,
        "usingSavedContent": bool(row is not None and row.has_custom_content),
        "defaultSubject": email_type.default_subject,
        "defaultBody": _default_body(email_type),
        "subject": row.subject if row is not None else "",
        "body": row.body_html if row is not None else "",
        "updatedAt": row.updated_at.isoformat() if row is not None and row.updated_at else None,
        "mergeTags": [
            {
                "name": tag.name,
                "description": tag.description,
                "sample": tag.sample,
                "html": tag.html,
            }
            for tag in email_type.merge_tags
        ],
    }


def _serialize_settings(settings_row: SystemEmailSettings) -> dict:
    return {
        "emailsEnabled": settings_row.emails_enabled,
        "updatedAt": settings_row.updated_at.isoformat()
        if settings_row.updated_at
        else None,
    }


def _sample_context(email_type) -> dict:
    """One context per merge tag, built from the registry's sample values.

    Used for the test send, which lands in the admin's own inbox and should
    read like a real email. Brand tags are merged in by
    ``render_system_email`` itself.
    """
    context = {}
    for tag in email_type.merge_tags:
        context[tag.context_key] = tag.sample
    return context


def _placeholder_context(email_type, *, brand_as_tags: bool = False) -> dict:
    """Each merge tag shown as its own ``{{ tag }}``, for the editor and preview.

    With ``brand_as_tags`` False (the preview), brand tags keep their real
    values, since they're the same in every email, so only the
    recipient-specific parts show as tags. The editor pre-fill passes True so
    saved wording keeps following the brand settings too. Values come back out
    of rendering as literal ``{{ tag }}`` text, never re-evaluated.
    """
    brand = brand_context()
    # Templates that build a list with {% for %} (components, unread groups)
    # show that list's tag instead, so the list isn't lost from saved wording.
    context = {**brand, "SHOW_MERGE_TAGS": True}
    for tag in email_type.merge_tags:
        if brand_as_tags or tag.context_key not in brand:
            context[tag.context_key] = "{{ %s }}" % tag.name
    return context


def _with_visible_logo(html: str) -> str:
    """Swap the email-only ``cid:`` logo reference for an embedded image.

    Email clients resolve ``cid:`` against the attached logo; a browser preview
    can't, so the logo would show as broken without this.
    """
    data_uri = logo_data_uri()
    if not data_uri:
        return html
    return html.replace(f"cid:{LOGO_CID}", data_uri)


def _validate_editable_text(key: str, field: str, value: str):
    """Reject text whose merge tags the email type cannot fill.

    Returns an error string or None. Applied on save *and* preview so a
    preview never shows a literal {{ tag }} that a save would then refuse.
    """
    unknown = unknown_merge_tags(key, value or "")
    if unknown:
        names = "', '".join(sorted(unknown))
        return f"Unsupported merge tag(s) in {field}: '{names}'"
    return None


# ---------------------------------------------------------------------------
# Template listing / detail
# ---------------------------------------------------------------------------

def list_email_templates() -> dict:
    """Every registry entry with its current enabled/locked state and tags."""
    rows = {
        row.key: row for row in SystemEmailTemplate.objects.all()
    }
    items = [
        _serialize_template(email_type, rows.get(email_type.key))
        for email_type in EMAIL_TYPES
    ]
    return {
        "msg": "System email templates retrieved successfully",
        "data": {"items": items},
    }


def get_email_template(key: str) -> dict:
    """One registry entry; ``data`` is None for an unknown key."""
    if not is_known_email_type(key):
        return {"msg": f"Unknown email type '{key}'", "data": None}
    email_type = get_email_type(key)
    row = SystemEmailTemplate.objects.filter(key=key).first()
    return {
        "msg": "System email template retrieved successfully",
        "data": _serialize_template(email_type, row),
    }


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

@transaction.atomic
def update_email_template(
    key: str,
    fields: dict,
    *,
    requested_by,
) -> dict:
    """Apply the provided ``subject`` / ``body`` / ``enabled`` edits.

    ``fields`` only contains keys the client actually sent (PATCH semantics),
    so toggling an email does not disturb its wording and vice versa. A blank
    subject/body means "use the built-in template file again" while keeping
    the enabled state, which is how restore-default behaves. Returns an
    envelope; ``data`` is None when the key is unknown or an edit is rejected.
    """
    if not is_known_email_type(key):
        return {"msg": f"Unknown email type '{key}'", "data": None}
    email_type = get_email_type(key)

    if fields.get("enabled") is False and email_type.locked:
        return {
            "msg": f"The '{email_type.name}' email is required for signing in "
            + "and cannot be switched off.",
            "data": None,
        }

    row = SystemEmailTemplate.objects.filter(key=key).first()
    if row is None:
        row = SystemEmailTemplate(key=key, is_enabled=True)

    if "enabled" in fields:
        row.is_enabled = bool(fields["enabled"])

    if "subject" in fields:
        error = _validate_editable_text(key, "subject", fields.get("subject"))
        if error:
            return {"msg": error, "data": None}
        row.subject = _flatten_subject(fields.get("subject"))

    if "body" in fields:
        error = _validate_editable_text(key, "body", fields.get("body"))
        if error:
            return {"msg": error, "data": None}
        row.body_html = nh3.clean(fields.get("body") or "")
        # Derived at render time by the send path; no need to keep in lockstep.
        row.body_text = ""

    row.updated_by = requested_by
    row.save()

    return {
        "msg": "System email template updated successfully",
        "data": _serialize_template(email_type, row),
    }


def _flatten_subject(subject: str) -> str:
    """Collapse a subject onto one line, guarding against header injection."""
    return " ".join((subject or "").split())


@transaction.atomic
def restore_email_template(key: str, *, requested_by) -> dict:
    """Drop the stored wording so the template file is used again.

    The enabled toggle is preserved — restoring wording is not permission to
    silently switch an email back on.
    """
    if not is_known_email_type(key):
        return {"msg": f"Unknown email type '{key}'", "data": None}
    email_type = get_email_type(key)

    row = SystemEmailTemplate.objects.filter(key=key).first()
    if row is None:
        return {
            "msg": "System email template restored successfully",
            "data": _serialize_template(email_type, None),
        }

    row.subject = ""
    row.body_html = ""
    row.body_text = ""
    row.updated_by = requested_by
    row.save(update_fields=["subject", "body_html", "body_text", "updated_by"])

    return {
        "msg": "System email template restored successfully",
        "data": _serialize_template(email_type, row),
    }


# ---------------------------------------------------------------------------
# Preview / test send
# ---------------------------------------------------------------------------

def _preview_fields(key: str, subject, body) -> tuple:
    """Validate unsaved wording and return the cleaned, render-ready values.

    ``None`` means "not provided" and tells ``render_system_email`` to use the
    stored/default wording; an explicit empty string means "clear it".
    """
    error = None
    if subject is not None:
        error = _validate_editable_text(key, "subject", subject)
        if error:
            return None, None, error
        subject = _flatten_subject(subject)
    if body is not None:
        error = _validate_editable_text(key, "body", body)
        if error:
            return None, None, error
        body = nh3.clean(body or "")
    return subject, body, None


def preview_email_template(
    key: str,
    subject=None,
    body=None,
) -> dict:
    """Render email ``key`` for the editor's preview, honouring unsaved edits.

    Returns the finished subject and the full branded HTML + plain text.
    Recipient-specific merge tags stay visible as ``{{ tag }}`` so the admin
    can see exactly where each person's data will go, and the logo is
    embedded so it displays in the browser.
    """
    if not is_known_email_type(key):
        return {"msg": f"Unknown email type '{key}'", "data": None}

    cleaned_subject, cleaned_body, error = _preview_fields(key, subject, body)
    if error:
        return {"msg": error, "data": None}

    email_type = get_email_type(key)
    try:
        rendered = render_system_email(
            key,
            _placeholder_context(email_type),
            subject=cleaned_subject,
            body=cleaned_body,
        )
    except TemplateDoesNotExist:
        # The key has no built-in template file yet and no body was supplied,
        # so there is nothing to render — ask for a body instead of crashing.
        return {
            "msg": f"The built-in template for '{email_type.name}' does not exist yet. "
            + "Write some body content and try again.",
            "data": None,
        }
    return {
        "msg": "System email template preview rendered successfully",
        "data": {
            "key": key,
            "subject": rendered.subject,
            "html": _with_visible_logo(rendered.html),
            "text": rendered.text,
        },
    }


def send_test_email(
    key: str,
    *,
    requested_by,
    subject=None,
    body=None,
) -> dict:
    """Send email ``key`` to the requesting admin's address.

    Deliberately bypasses the enabled toggle: an admin must be able to test a
    disabled email before re-arming it. Unsaved edits are sent when provided.
    """
    if not is_known_email_type(key):
        return {"msg": f"Unknown email type '{key}'", "data": None}

    cleaned_subject, cleaned_body, error = _preview_fields(key, subject, body)
    if error:
        return {"msg": error, "data": None}

    email_type = get_email_type(key)
    try:
        rendered = render_system_email(
            key,
            _sample_context(email_type),
            subject=cleaned_subject,
            body=cleaned_body,
        )
    except TemplateDoesNotExist:
        return {
            "msg": f"The built-in template for '{email_type.name}' does not exist yet. "
            + "Write some body content and try again.",
            "data": None,
        }
    message = build_message(rendered, requested_by.email)

    try:
        message.send(fail_silently=False)
    except Exception as exc:
        # Not logger.exception: SMTP errors can carry the address in their args.
        logger.error(
            "admin.system_email.test_send_failed key=%s error=%s",
            key,
            type(exc).__name__,
        )
        return {
            "msg": "The test email could not be sent. Check the mail backend and try again.",
            "data": None,
        }

    return {
        "msg": f"Test email sent to {requested_by.email}",
        "data": {"key": key, "sentTo": requested_by.email},
    }


# ---------------------------------------------------------------------------
# Global settings
# ---------------------------------------------------------------------------

def get_email_settings() -> dict:
    """The global on/off switch, created with defaults on first read."""
    return {
        "msg": "System email settings retrieved successfully",
        "data": _serialize_settings(SystemEmailSettings.get()),
    }


@transaction.atomic
def update_email_settings(enabled: bool, *, requested_by) -> dict:
    """Flip the global switch. Locked types are unaffected (always send)."""
    settings_row = SystemEmailSettings.get()
    settings_row.emails_enabled = bool(enabled)
    settings_row.updated_by = requested_by
    settings_row.save()
    return {
        "msg": "System email settings updated successfully",
        "data": _serialize_settings(settings_row),
    }