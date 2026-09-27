"""Waitlist-promotion email dispatch.

Kept in its own module so a slow SMTP call doesn't sit inside the
``set_user_rsvp`` transaction. ``notify_waitlist_promoted`` is invoked
after the txn commits.
"""

import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings

from apps.services.system_email import FAILED, send_system_email
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

    # Hybrid: show both join URL and physical location. Virtual/in-person: one or the other.
    join_link = ""
    where = ""
    fmt = event.event_format
    if fmt == Events.EventFormat.HYBRID:
        join_link = event.location_link or ""
        where = event.location or ""
    elif fmt == Events.EventFormat.VIRTUAL and event.location_link:
        join_link = event.location_link
    elif event.location:
        where = event.location

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
    if join_link:
        lines.append(f"Join:   {join_link}")
    if where:
        lines.append(f"Where:  {where}")
    lines += ["", "See you there!", "", f"The {settings.BRAND_NAME} Team"]
    plain_body = "\n".join(lines)

    try:
        # Sent inline (this already runs after the RSVP transaction commits).
        # Skipped when an admin has switched this email off.
        result = send_system_email(
            "event_promotion",
            email,
            {
                "First_Name": first_name,
                "EVENT_NAME": event.event_name,
                "EVENT_WHEN_TEXT": when_full,
                "EVENT_JOIN_LINK": join_link,
                "EVENT_LOCATION_TEXT": where,
            },
            default_text=plain_body,
        )
    except Exception:
        logger.exception(
            "Failed to send waitlist-promotion email for event %s user %s",
            event_id,
            user_id,
        )
        return

    if result == FAILED:
        logger.error(
            "Failed to send waitlist-promotion email for event %s user %s",
            event_id,
            user_id,
        )
