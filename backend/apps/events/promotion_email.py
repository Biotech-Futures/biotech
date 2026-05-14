"""Waitlist-promotion email dispatch.

Kept in its own module so a slow SMTP call doesn't sit inside the
``set_user_rsvp`` transaction. ``notify_waitlist_promoted`` is invoked
after the txn commits.
"""

import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from apps.users.models import User

from .models import Events

logger = logging.getLogger(__name__)


def notify_waitlist_promoted(*, event_id, user_id):
    """Send a one-shot "you're off the waitlist" email.

    Failures are logged and swallowed — a missed email is annoying but
    must not roll back the promotion, which has already happened.
    """
    event = Events.objects.filter(pk=event_id, deleted_at__isnull=True).first()
    user = User.objects.filter(pk=user_id).first()
    if event is None or user is None:
        return

    email = (getattr(user, "email", "") or "").strip()
    if not email:
        return

    first_name = (getattr(user, "first_name", "") or "").strip() or "there"
    user_tz_name = getattr(user, "timezone", "UTC") or "UTC"
    try:
        tz = ZoneInfo(user_tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")

    local_start = event.start_datetime.astimezone(tz)
    when_full = local_start.strftime(
        f"%A, %d %B %Y at %I:%M %p {local_start.tzname() or user_tz_name}"
    )

    from_email = settings.DEFAULT_FROM_EMAIL or "noreply@biotechfutures.com"
    subject = f"You're in: {event.event_name}"
    intro = (
        "A spot just opened up and you've been moved from the waitlist "
        f"to confirmed for {event.event_name}."
    )

    lines = [
        f"Hi {first_name},",
        "",
        intro,
        "",
        f"Event:  {event.event_name}",
        f"When:   {when_full}",
    ]
    if event.is_virtual and event.location_link:
        lines.append(f"Join:   {event.location_link}")
    elif event.location:
        lines.append(f"Where:  {event.location}")
    lines += ["", "See you there!", "", "The BIOTech Futures Team"]
    plain_body = "\n".join(lines)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_body,
            from_email=from_email,
            to=[email],
        )
        msg.send(fail_silently=False)
    except Exception:
        logger.exception(
            "Failed to send waitlist-promotion email for event %s user %s",
            event_id,
            user_id,
        )
