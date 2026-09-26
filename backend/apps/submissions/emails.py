"""Confirmation email sent when a team submits, listing each component's status."""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import get_connection
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from apps.groups.models import GroupMembership
from apps.services.email_branding import brand_context
from apps.services.mailer import send_async
from apps.services.system_email import build_message, is_email_enabled, render_system_email

from .models import Submission, SubmissionQuestion
from .services import deadline_for_group


logger = logging.getLogger(__name__)

SUBMITTED = "Submitted"
NOT_SUBMITTED = "Not Submitted"


def _format_deadline(closes_at) -> str:
    """"Friday, 18 September 2026"; built from parts because "%-d" fails on Windows."""
    if not closes_at:
        return "the published deadline"
    local = timezone.localtime(closes_at)
    return f"{local:%A}, {local.day} {local:%B %Y}"


def _component(label: str, present: bool, detail: str = "") -> dict:
    return {
        "label": label,
        "submitted": present,
        "status": SUBMITTED if present else NOT_SUBMITTED,
        "detail": detail if present else "",
    }


def _saqs_present(submission: Submission) -> bool:
    """Every required question answered in the submitted copy."""
    answers = submission.submitted_answers or {}
    required = SubmissionQuestion.active().filter(is_required=True)
    if not required.exists():
        return bool(answers)
    return all(str(answers.get(q.key, "")).strip() for q in required)


def _file_detail(stored: dict | None) -> str:
    if not stored:
        return ""
    return stored.get("name") or ""


def build_components(submission: Submission) -> tuple[list[dict], list[dict]]:
    required = [
        _component("Poster", bool(submission.submitted_poster),
                   _file_detail(submission.submitted_poster)),
        _component("Short Answer Questions (SAQs)", _saqs_present(submission)),
    ]
    optional = [
        _component("Scientific Report", bool(submission.submitted_report),
                   _file_detail(submission.submitted_report)),
        _component(
            "Prototype",
            bool(submission.submitted_prototype) or bool(submission.submitted_prototype_url),
            _file_detail(submission.submitted_prototype)
            or submission.submitted_prototype_url,
        ),
    ]
    return required, optional


def components_list_html(components: list[dict]) -> str:
    """Components as an HTML list, for the merge tags an admin can use in an
    edited email, e.g. "<li><strong>Poster</strong>: Submitted (poster.pdf)</li>".
    Every value is escaped.
    """
    if not components:
        return ""
    items = format_html_join(
        "",
        "<li><strong>{}</strong>: {}{}</li>",
        (
            (
                item["label"],
                item["status"],
                format_html(" ({})", item["detail"]) if item.get("detail") else "",
            )
            for item in components
        ),
    )
    return format_html("<ul>{}</ul>", items)


def recipients_for(group) -> list[str]:
    """Active members of the team: students, mentors and supervisors."""
    memberships = (
        GroupMembership.objects.filter(group=group, left_at__isnull=True)
        .select_related("user")
    )
    emails = [
        membership.user.email
        for membership in memberships
        if membership.user and membership.user.email and membership.user.is_active
    ]
    return sorted(set(emails))


def send_individually(messages, *, kind: str) -> tuple[int, int]:
    """One message per recipient, so addresses stay private and one bad address fails alone. Returns (sent, failed)."""
    if not messages:
        return 0, 0

    sent = failed = 0
    connection = get_connection()
    try:
        connection.open()
    except Exception:
        logger.error("submission_email.connection_failed kind=%s", kind)
        return 0, len(messages)

    try:
        for message in messages:
            message.connection = connection
            try:
                message.send()
            except Exception as exc:
                failed += 1
                # Not logger.exception, which would log the recipient address.
                logger.error(
                    "submission_email.recipient_failed kind=%s error=%s",
                    kind, type(exc).__name__,
                )
            else:
                sent += 1
    finally:
        try:
            connection.close()
        except Exception:
            pass
    return sent, failed


class _Batch:
    """A team's messages as one task on the shared mail pool, so login codes are not delayed."""

    def __init__(self, messages, kind: str):
        self.messages = messages
        self.kind = kind

    def send(self) -> int:
        sent, _ = send_individually(self.messages, kind=self.kind)
        return sent


def send_submission_confirmation(submission: Submission) -> int:
    """Email the team a summary of what was received. Returns recipient count; never raises."""
    try:
        if not is_email_enabled("submission_confirmation"):
            logger.info("submission_email.skipped_disabled group=%s", getattr(submission, "group_id", None))
            return 0

        group = submission.group
        to = recipients_for(group)
        if not to:
            logger.warning("submission_email.no_recipients group=%s", group.id)
            return 0

        required, optional = build_components(submission)
        deadline = deadline_for_group(group.id)

        context = {
            **brand_context(),
            "GROUP_NAME": group.group_name,
            "YEAR": timezone.now().year,
            "REQUIRED_COMPONENTS": required,
            "OPTIONAL_COMPONENTS": optional,
            "REQUIRED_COMPONENTS_LIST": components_list_html(required),
            "OPTIONAL_COMPONENTS_LIST": components_list_html(optional),
            "INCOMPLETE": any(not item["submitted"] for item in required),
            "DEADLINE": _format_deadline(deadline.closes_at),
            "SUBMITTED_BY": submission.submitted_by,
            # Blank when no frontend URL is configured; the template then omits the button.
            "SUBMISSION_URL": (
                f"{settings.FRONTEND_BASE_URL}/#/submission/{group.id}"
                if getattr(settings, "FRONTEND_BASE_URL", "")
                else ""
            ),
        }

        # The existing plain-text template, used unless an admin rewrote the email.
        text = render_to_string("emails/submission_confirmation.txt", context)
        # Rendered once, so every member reads the same email; only the address differs.
        rendered = render_system_email("submission_confirmation", context, default_text=text)
        messages = [build_message(rendered, address) for address in to]

        # Rendered here so the worker thread does no database work.
        send_async(_Batch(messages, "submission_confirmation"),
                   kind="submission_confirmation")
        return len(to)
    except Exception:
        logger.exception("submission_email.failed group=%s", getattr(submission, "group_id", None))
        return 0
