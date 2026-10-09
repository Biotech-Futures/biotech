"""Confirmation email sent when a team submits, listing each component's status."""
from __future__ import annotations

import logging

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from apps.groups.models import GroupMembership
from apps.services.email_branding import brand_context
from apps.services.email_log import UNREACHABLE, note_send, reason_for
from apps.services.mailer import send_async
from apps.services.system_email import (
    build_message,
    is_email_enabled,
    render_system_email,
    sender_connection,
    sender_for,
)

from .models import Submission, SubmissionQuestion
from .services import current_cohort, deadline_for_group


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


def to_and_cc(group, addresses) -> tuple[list[str], list[str]]:
    """``addresses`` on ``group`` as its one email takes them: its students in
    To, its mentors and supervisors in CC. Shared with the Notify emails
    (``apps.management.services.delivery``)."""
    students = {
        address.lower()
        for address in GroupMembership.objects.filter(
            group=group, left_at__isnull=True, membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        ).values_list("user__email", flat=True)
        if address
    }
    return (
        [address for address in addresses if address.lower() in students],
        [address for address in addresses if address.lower() not in students],
    )


def group_message(rendered, group, addresses, *, sender):
    """The team's one email, as the Notify emails go: its students in To, its
    mentors and supervisors in CC (all in To when it has no student).
    From ``sender`` (see ``system_email.sender_for``); replies go back to it."""
    to, cc = to_and_cc(group, addresses)
    if not to:
        to, cc = cc, []
    message = build_message(rendered, to, from_email=sender.from_email)
    message.cc = cc
    return message


def send_messages(messages, *, kind: str, sender) -> tuple[int, int]:
    """Send each message over one connection, signed in as ``sender``'s
    mailbox; one failing doesn't stop the rest. Returns (sent, failed). Noted
    in the Log on System Emails as a send of ``kind``."""
    if not messages:
        return 0, 0

    sent = failed = 0
    missed = {}
    connection = sender_connection(sender)
    try:
        connection.open()
    except Exception:
        logger.error("submission_email.connection_failed kind=%s", kind)
        note_send(kind, missed={address: UNREACHABLE for message in messages for address in message.recipients()})
        return 0, len(messages)

    try:
        for message in messages:
            message.connection = connection
            try:
                message.send()
            except Exception as exc:
                failed += 1
                missed.update(dict.fromkeys(message.recipients(), reason_for(exc)))
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
    note_send(kind, missed=missed)
    return sent, failed


class _Batch:
    """A team's email as one task on the shared mail pool, so login codes are not delayed."""

    def __init__(self, messages, kind: str, sender):
        self.messages = messages
        self.kind = kind
        # Looked up before it's queued: the worker does no database work.
        self.sender = sender

    def send(self) -> int:
        sent, _ = send_messages(self.messages, kind=self.kind, sender=self.sender)
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
            "YEAR": current_cohort(),
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
        rendered = render_system_email("submission_confirmation", context, default_text=text)
        # One email for the team, as the Notify emails go, from the mailbox
        # picked on System Emails.
        sender = sender_for("submission_confirmation")
        messages = [group_message(rendered, group, to, sender=sender)]

        # Rendered here so the worker thread does no database work.
        send_async(_Batch(messages, "submission_confirmation", sender),
                   kind="submission_confirmation")
        return len(to)
    except Exception:
        logger.exception("submission_email.failed group=%s", getattr(submission, "group_id", None))
        return 0
