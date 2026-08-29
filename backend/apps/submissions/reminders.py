"""Daily reminders to teams whose entry is not yet in.

The programme writes to a team every day for the last week before their
deadline, for as long as their entry is still outstanding. Two rules shape
everything here:

* **A team that has submitted is never written to.** The reminder exists to
  prompt an unfinished entry; sending it to a team who has finished would read
  as though something had gone wrong with what they sent.
* **Each team is measured against their own deadline.** A team granted an
  extension gets their week counted from the date they were given, and the date
  named in the email is theirs — not the one on the programme's website. That
  is why the copy interpolates the deadline instead of stating it.

Reminders stop at the announced closing time rather than at the moment writes
are actually refused. The grace period after it is deliberately not published,
and an email arriving inside it would announce it.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.groups.models import Groups
from apps.services.email_branding import brand_context

from .emails import LOGO_CID, attach_green_logo, recipients_for, send_individually
from .models import Submission, SubmissionReminder
from .serializers import missing_required_answers
from .services import deadline_for_group


logger = logging.getLogger(__name__)

# How long before the deadline the daily reminders begin.
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
    """Every required question answered.

    Deliberately the same call the submit endpoint makes, so "the SAQs are
    done" cannot come to mean one thing in an email and another on the form.
    It reads the working draft, which is the right copy here: a team being
    reminded has not submitted, so the frozen copy is empty or stale.
    """
    if submission is None:
        return False
    return not missing_required_answers(submission)


def _file_name(stored: dict | None) -> str:
    return (stored or {}).get("name") or ""


def components_for(submission: Submission | None) -> tuple[list[dict], list[dict]]:
    """Required and optional components, as the reminder lists them.

    The poster and the short answers are what a complete entry needs; the
    report and the prototype are welcome but do not decide completeness. The
    client's reminder copy had the report and the SAQs the other way around,
    which contradicted both their own confirmation email and the question set
    marked required in the database — corrected here to match those.
    """
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
    """"Friday, 18 September 2026" — the programme's own wording.

    Built from parts rather than with a "%-d" directive: that strips the leading
    zero on Linux but is not a valid format on Windows, so a developer machine
    would raise where the server would not.
    """
    local = timezone.localtime(closes_at)
    return f"{local:%A}, {local.day} {local:%B %Y}"


def _submission_of(group) -> Submission | None:
    try:
        return group.submission
    except Submission.DoesNotExist:
        return None


def build_reminders(group, submission, closes_at) -> list[EmailMultiAlternatives]:
    """Render one team's reminder, as one message per student.

    Rendered once and reused, so everyone on the team reads the same email —
    only the address it is addressed to differs. See ``send_individually`` for
    why they are not simply listed together in one ``To``.
    """
    required, optional = components_for(submission)
    context = {
        **brand_context(),
        "LOGO_URL": f"cid:{LOGO_CID}",
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
        attach_green_logo(message)
        messages.append(message)
    return messages


def teams_due(now=None) -> list[tuple]:
    """Teams inside their final week with an entry still outstanding.

    Iterates teams rather than submissions. A team that has never opened the
    form has no submission row, and those are exactly the teams a reminder is
    for — querying submissions would skip every one of them.
    """
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
            # Finished. Nothing to chase.
            continue

        info = deadline_for_group(group.id)
        if info.closes_at is None:
            # No deadline configured for this team, so there is no week to
            # count back from and nothing honest to tell them.
            continue
        if not (info.closes_at - REMINDER_WINDOW <= now <= info.closes_at):
            continue

        reminder = getattr(group, "submission_reminder", None)
        if reminder is not None and reminder.last_sent_on == today:
            continue

        due.append((group, submission, info.closes_at))
    return due


def send_due_reminders(now=None, *, dry_run: bool = False) -> dict:
    """Send today's reminders. Returns a small summary for the caller to log.

    Sent inline rather than through the shared mail pool: that pool exists to
    keep SMTP out of a web request, and there is no request here. A batch job
    that has reported success should mean the mail has gone, not that it has
    been queued behind a process that may be about to exit.

    One team's failure is caught and counted rather than raised, so a single bad
    address cannot stop the rest of the run.
    """
    now = now or timezone.now()
    today = timezone.localdate(now)
    sent = skipped = failed = 0

    for group, submission, closes_at in teams_due(now):
        messages = build_reminders(group, submission, closes_at)
        if not messages:
            # No active students on the team; nobody to remind.
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
            # Nobody on the team received it, so today is not recorded and the
            # next run will try them again rather than skipping them as done.
            failed += 1
            continue

        SubmissionReminder.objects.update_or_create(
            group=group, defaults={"last_sent_on": today}
        )
        sent += 1

    return {"sent": sent, "skipped": skipped, "failed": failed}
