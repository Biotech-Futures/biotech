"""Daily reminders in each team's final week, until they submit.

Each team is measured against its own deadline, extensions included, and
reminders stop at the announced time so the grace period is never revealed.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.groups.models import Groups
from apps.services.email_branding import attach_inline_logo, brand_context

from .emails import recipients_for, send_individually
from .models import Submission, SubmissionReminder
from .serializers import missing_required_answers
from .services import deadline_for_group


logger = logging.getLogger(__name__)

REMINDER_WINDOW = timedelta(days=7)

SUBMITTED = "Submitted"
NOT_SUBMITTED = "Not Submitted"


def _component(label: str, present: bool, detail: str = "") -> dict:
    return {
        "label": label,
        "submitted": present,
        "status": SUBMITTED if present else NOT_SUBMITTED,
        "detail": detail if present else "",
    }


def _saqs_complete(submission: Submission | None) -> bool:
    """Every required question answered in the draft, using the same rule as submit."""
    if submission is None:
        return False
    return not missing_required_answers(submission)


def _file_name(stored: dict | None) -> str:
    return (stored or {}).get("name") or ""


def components_for(submission: Submission | None) -> tuple[list[dict], list[dict]]:
    required = [
        _component(
            "Poster",
            bool(submission and submission.poster),
            _file_name(submission.poster if submission else None),
        ),
        _component("Short Answer Questions (SAQs)", _saqs_complete(submission)),
    ]
    optional = [
        _component(
            "Scientific Report",
            bool(submission and submission.report),
            _file_name(submission.report if submission else None),
        ),
        _component(
            "Prototype",
            bool(submission and (submission.prototype or submission.prototype_url)),
            _file_name(submission.prototype if submission else None)
            or (submission.prototype_url if submission else ""),
        ),
    ]
    return required, optional


def _format_deadline(closes_at) -> str:
    """"Friday, 18 September 2026"; built from parts because "%-d" fails on Windows."""
    local = timezone.localtime(closes_at)
    return f"{local:%A}, {local.day} {local:%B %Y}"


def _submission_of(group) -> Submission | None:
    try:
        return group.submission
    except Submission.DoesNotExist:
        return None


def build_reminders(group, submission, closes_at) -> list[EmailMultiAlternatives]:
    """One team's reminder, as one message per recipient."""
    required, optional = components_for(submission)
    context = {
        **brand_context(),
        "GROUP_NAME": group.group_name,
        "YEAR": timezone.now().year,
        "REQUIRED_COMPONENTS": required,
        "OPTIONAL_COMPONENTS": optional,
        "DEADLINE": _format_deadline(closes_at),
        "SUBMISSION_URL": (
            f"{settings.FRONTEND_BASE_URL}/#/submission/{group.id}"
            if getattr(settings, "FRONTEND_BASE_URL", "")
            else ""
        ),
    }
    subject = f"{settings.BRAND_NAME}: Submission reminder for {group.group_name}"
    text = render_to_string("emails/submission_reminder.txt", context)
    html = render_to_string("emails/submission_reminder.html", context)

    messages = []
    for address in recipients_for(group):
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[address],
        )
        message.attach_alternative(html, "text/html")
        attach_inline_logo(message)
        messages.append(message)
    return messages


def teams_due(now=None) -> list[tuple]:
    """Teams in their final week that have not submitted, including those with no entry yet."""
    now = now or timezone.now()
    today = timezone.localdate(now)
    due = []

    groups = (
        Groups.objects.filter(deleted_at__isnull=True)
        .select_related("submission", "submission_reminder")
    )
    for group in groups:
        submission = _submission_of(group)
        if submission is not None and submission.is_submitted:
            continue

        info = deadline_for_group(group.id)
        if info.closes_at is None:
            continue
        if not (info.closes_at - REMINDER_WINDOW <= now <= info.closes_at):
            continue

        reminder = getattr(group, "submission_reminder", None)
        if reminder is not None and reminder.last_sent_on == today:
            continue

        due.append((group, submission, info.closes_at))
    return due


def send_due_reminders(now=None, *, dry_run: bool = False) -> dict:
    """Send today's reminders synchronously and return counts of sent, skipped and failed."""
    now = now or timezone.now()
    today = timezone.localdate(now)
    sent = skipped = failed = 0

    for group, submission, closes_at in teams_due(now):
        messages = build_reminders(group, submission, closes_at)
        if not messages:
            skipped += 1
            continue
        if dry_run:
            sent += 1
            continue

        delivered, refused = send_individually(messages, kind="submission_reminder")
        if refused:
            logger.error(
                "submission_reminder.partial group=%s sent=%s failed=%s",
                group.id, delivered, refused,
            )
        if not delivered:
            # Not recorded, so the next run tries this team again.
            failed += 1
            continue

        SubmissionReminder.objects.update_or_create(
            group=group, defaults={"last_sent_on": today}
        )
        sent += 1

    return {"sent": sent, "skipped": skipped, "failed": failed}
