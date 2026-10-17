"""Daily reminders to finalist teams in the final week before slides are due, until they submit.

Both the slides and, once the times are released, the team's available times are needed before
the team can submit, so the reminder shows where each stands. The due date is the Slides Due day
set on Management > Notify Finalists; with none set, nobody is reminded.
"""
from __future__ import annotations

import logging

from django.apps import apps
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.services.email_branding import brand_context
from apps.services.system_email import is_email_enabled, render_system_email, sender_for

from .email_sections import GREEN, RED, section_html
from .emails import _long_day, finalist_times, finalist_url, group_message, recipients_for, send_messages
from .finalist import slides_due_at, times_shown
from .models import FinalistEntry, FinalistReminder
from .reminders import REMINDER_WINDOW
from .services import current_cohort

logger = logging.getLogger(__name__)

EMAIL_KEY = "finalist_submission_reminder"


def components_for(group_id: int, entry: FinalistEntry | None, symposium_day=None) -> list[dict]:
    """Where the team's slides and times stand; the times only once finalists can choose them."""
    slides = (entry.presentation or {}) if entry else {}
    rows = [{
        "label": "Presentation Slides",
        "submitted": bool(slides),
        "status": "Uploaded" if slides else "Not uploaded",
        "detail": slides.get("name", ""),
    }]
    if times_shown():
        # Saved with its own button on the finalist page, as the team's availability.
        times = finalist_times(group_id, symposium_day)
        rows.append({
            "label": "Availability",
            "submitted": bool(times),
            "status": "Submitted" if times else "Not submitted",
            "detail": ", ".join(times),
        })
    return rows


FINISH = "Press Submit on your finalist page to complete your submission."


def components_note(components: list[dict]) -> str:
    """What is still needed, then Submit; availability has its own button, so it is named on its own."""
    slides = components[0]["submitted"]
    if len(components) == 1:
        return f"Your slides are in. {FINISH}" if slides else "Your slides are required: upload them, then press Submit."
    times = components[1]["submitted"]
    if slides and times:
        return f"Both are in. {FINISH}"
    if not slides and not times:
        return "Both are required: upload your slides and submit your availability, then press Submit."
    missing = "submit your availability" if slides else "upload your slides"
    return f"Both are required: {missing}, then press Submit."


def components_section(components: list[dict]) -> str:
    rows = [{**item, "colour": GREEN if item["submitted"] else RED} for item in components]
    return section_html("Submission components", rows, components_note(components))


def reminder_context(group, entry: FinalistEntry | None) -> dict:
    """The values the reminder's template and merge tags read."""
    details = apps.get_model("management", "FinalistEmailSettings").load()
    components = components_for(group.id, entry, details.symposium_date)
    return {
        "GROUP_NAME": group.group_name,
        "YEAR": current_cohort(),
        "COMPONENTS": components,
        "COMPONENTS_NOTE": components_note(components),
        # Ready-made and styled, so an admin's edited email shows it as the default one does.
        "COMPONENTS_SECTION": components_section(components),
        "SLIDES_DUE": _long_day(details.slides_due),
        "FINALIST_URL": finalist_url(group),
    }


def build_reminder(group, entry: FinalistEntry | None, sender=None) -> list[EmailMultiAlternatives]:
    """One team's reminder, as one email for the team (see ``group_message``)."""
    context = {**brand_context(), **reminder_context(group, entry)}
    text = render_to_string("emails/finalist_submission_reminder.txt", context)
    rendered = render_system_email(EMAIL_KEY, context, default_text=text)
    recipients = recipients_for(group)
    sender = sender or sender_for(EMAIL_KEY)
    return [group_message(rendered, group, recipients, sender=sender)] if recipients else []


def teams_due(now=None) -> list[tuple]:
    """This year's notified finalists yet to submit, in the final week before slides are due."""
    now = now or timezone.now()
    due_at = slides_due_at()
    if due_at is None or not (due_at - REMINDER_WINDOW <= now <= due_at):
        return []
    today = timezone.localdate(now)
    FinalistFlag = apps.get_model("grading", "FinalistFlag")
    flags = (
        FinalistFlag.objects.filter(notified=True, group__deleted_at__isnull=True, group__year=current_cohort())
        .select_related("group")
        .order_by("group__group_name")
    )
    due = []
    for flag in flags:
        group = flag.group
        entry = FinalistEntry.objects.filter(group=group).first()
        if entry is not None and entry.is_submitted:
            continue
        reminder = FinalistReminder.objects.filter(group=group).first()
        if reminder is not None and reminder.last_sent_on == today:
            continue
        due.append((group, entry))
    return due


def send_due_reminders(now=None, *, dry_run: bool = False) -> dict:
    """Send today's finalist reminders and return counts of sent, skipped and failed.

    Switched off on System Emails, nothing is sent or recorded, so reminders
    resume normally once it's switched back on.
    """
    if not is_email_enabled(EMAIL_KEY):
        return {"sent": 0, "skipped": 0, "failed": 0, "disabled": True}

    now = now or timezone.now()
    today = timezone.localdate(now)
    sent = skipped = failed = 0
    sender = sender_for(EMAIL_KEY)

    for group, entry in teams_due(now):
        messages = build_reminder(group, entry, sender)
        if not messages:
            skipped += 1
            continue
        if dry_run:
            sent += 1
            continue

        delivered, refused = send_messages(messages, kind=EMAIL_KEY, sender=sender)
        if refused:
            logger.error("finalist_reminder.partial group=%s sent=%s failed=%s", group.id, delivered, refused)
        if not delivered:
            # Not recorded, so the next run tries this team again.
            failed += 1
            continue

        FinalistReminder.objects.update_or_create(group=group, defaults={"last_sent_on": today})
        sent += 1

    return {"sent": sent, "skipped": skipped, "failed": failed}


def reminder_job(actor, options) -> dict:
    """The queued run of today's finalist reminders (``send_guard.JOBS``)."""
    return send_due_reminders()
