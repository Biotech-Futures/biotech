import logging

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from apps.events.models.events import Events
from apps.events.models.event_invite import EventRsvp

logger = logging.getLogger(__name__)


@shared_task(name="events.send_event_rsvp_reminders")
def send_event_rsvp_reminders():
    """
    Runs every hour via Celery Beat.

    Finds events starting in the next 24-25 hours that have not had a
    reminder sent yet and dispatches a templated email to all confirmed
    (going) attendees.

    The 1-hour window accounts for the hourly schedule — any event
    starting between 24h and 25h from now will be caught exactly once.

    Idempotency is guaranteed by the ``reminder_sent`` boolean flag on
    the Events model — a crash loop cannot spam users multiple times.
    """
    now = timezone.now()
    window_start = now + timedelta(hours=24)
    window_end = now + timedelta(hours=25)

    events = Events.objects.filter(
        start_datetime__gte=window_start,
        start_datetime__lt=window_end,
        deleted_at__isnull=True,
        reminder_sent=False,
    )

    for event in events:
        _send_reminders_for_event(event)


def _send_reminders_for_event(event):
    """
    Sends reminder emails to all confirmed attendees of a single event
    and marks the event as reminder_sent=True.

    Uses iterator() with chunk_size to avoid loading hundreds of RSVP
    rows into memory at once.
    """
    rsvps = (
        EventRsvp.objects.filter(
            event=event,
            rsvp_status=EventRsvp.RsvpStatus.GOING,
        )
        .select_related("user")
        .iterator(chunk_size=100)
    )

    sent_count = 0
    failed_count = 0

    for rsvp in rsvps:
        user = rsvp.user
        email = getattr(user, "email", None)
        if not email:
            continue

        if event.is_virtual:
            location_info = (
                f"Join online: {event.location_link}"
                if event.location_link
                else "This is a virtual event. Check your calendar invite for the link."
            )
        else:
            location_info = (
                f"Location: {event.location}"
                + (f"\nMap: {event.location_link}" if event.location_link else "")
            )

        try:
            send_mail(
                subject=f"Reminder: {event.event_name} is tomorrow",
                message=(
                    f"Hi {user.first_name or 'there'},\n\n"
                    f"This is a friendly reminder that you have an upcoming event:\n\n"
                    f"Event:  {event.event_name}\n"
                    f"Date:   {event.start_datetime.strftime('%A, %d %B %Y at %I:%M %p')}\n"
                    f"{location_info}\n\n"
                    f"We look forward to seeing you there!\n\n"
                    f"The BIOTech Futures Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL or "noreply@biotechfutures.com",
                recipient_list=[email],
                fail_silently=False,
            )
            sent_count += 1
        except Exception as exc:
            failed_count += 1
            logger.error(
                "Failed to send RSVP reminder for event %s to user %s: %s",
                event.id,
                user.id,
                exc,
            )

    # Mark reminder as sent regardless of individual email failures.
    # This prevents a crash loop from spamming users who did receive it.
    Events.objects.filter(pk=event.pk).update(reminder_sent=True)

    logger.info(
        "RSVP reminders for event %s (%s): sent=%s failed=%s",
        event.id,
        event.event_name,
        sent_count,
        failed_count,
    )