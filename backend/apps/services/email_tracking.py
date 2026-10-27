"""Privacy-minimal first-party tracking for outgoing HTML email.

The tracking token is random and contains no recipient data. Open and click
requests retain only the related message tracker, event type and timestamp;
request IP addresses, user agents and clicked destinations are not stored.
Database failures always fail open so analytics can never block an email send
or a recipient's link.
"""

from __future__ import annotations

import html
import logging
import re
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import DatabaseError, transaction
from django.db.models import F
from django.db.models.functions import Coalesce
from django.utils import timezone

from .email_metrics import mailbox_address
from .models import EmailEngagementEvent, EmailEngagementTracker


logger = logging.getLogger(__name__)

CLICK_SALT = "services.email-engagement.click.v1"
PRIVACY_POLICY_URL = "https://www.biotechfutures.org/s/Privacy_Policy.pdf"
LINK_RE = re.compile(
    r"(?P<prefix><a\b[^>]*?\bhref\s*=\s*)(?P<quote>['\"])(?P<url>.*?)(?P=quote)",
    flags=re.IGNORECASE | re.DOTALL,
)


def instrument_html(
    html_body: str,
    *,
    email_type: str,
    subject: str,
    recipients,
) -> str:
    """Add signed click redirects and a one-pixel open marker.

    Each call instruments one message copy. For the usual single-recipient
    copy, the tracker is associated with that account/email. Existing team
    messages with several To/CC recipients retain only their recipient count.
    """
    if not html_body or not email_type:
        return html_body

    addresses = []
    seen = set()
    for value in recipients or ():
        address = mailbox_address(value)
        if address and address not in seen:
            seen.add(address)
            addresses.append(address)
    if not addresses:
        return html_body

    recipient_email = addresses[0] if len(addresses) == 1 else None
    user_id = None
    if recipient_email:
        try:
            user_id = (
                get_user_model().objects.filter(email__iexact=recipient_email)
                .values_list("id", flat=True)
                .first()
            )
        except DatabaseError:
            logger.exception("email_tracking.user_lookup_failed type=%s", email_type)

    try:
        tracker = EmailEngagementTracker.objects.create(
            email_type=email_type[:64],
            subject=(subject or "")[:255],
            recipient_email=recipient_email,
            recipient_count=len(addresses),
            user_id=user_id,
        )
    except (DatabaseError, ValueError, TypeError):
        logger.exception("email_tracking.create_failed type=%s", email_type)
        return html_body

    base_url = settings.BACKEND_URL.rstrip("/")

    def replace_link(match: re.Match) -> str:
        raw_url = html.unescape(match.group("url")).strip()
        parsed = urlparse(raw_url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return match.group(0)
        payload = signing.dumps(
            {"token": str(tracker.token), "url": raw_url},
            salt=CLICK_SALT,
            compress=True,
        )
        tracked_url = f"{base_url}/api/v1/services/email/track/click/{payload}/"
        return (
            f"{match.group('prefix')}{match.group('quote')}"
            f"{html.escape(tracked_url, quote=True)}{match.group('quote')}"
        )

    instrumented = LINK_RE.sub(replace_link, html_body)
    pixel_url = (
        f"{base_url}/api/v1/services/email/track/open/{tracker.token}.gif"
    )
    privacy_notice = (
        '<p style="margin:24px 0 0;padding:12px 0 0;border-top:1px solid #dfe8e3;'
        'font-size:11px;line-height:1.5;color:#5f716d">'
        "Email engagement notice: To improve programme communications, BIOTech Futures "
        "may record when this email is opened and when links are clicked. These signals "
        "can be affected by email and security software. "
        f'<a href="{PRIVACY_POLICY_URL}" style="color:#007a58">Read our Privacy Policy</a>.'
        "</p>"
    )
    pixel = (
        '<img src="{}" width="1" height="1" alt="" '
        'style="display:block;width:1px;height:1px;border:0;overflow:hidden" />'
    ).format(html.escape(pixel_url, quote=True))
    if re.search(r"</body\s*>", instrumented, flags=re.IGNORECASE):
        return re.sub(
            r"</body\s*>",
            lambda match: f"{privacy_notice}{pixel}{match.group(0)}",
            instrumented,
            count=1,
            flags=re.IGNORECASE,
        )
    return f"{instrumented}{privacy_notice}{pixel}"


def record_event(token, event_type: str) -> bool:
    """Record one signal and update its tracker's first/last/count summary."""
    if event_type not in EmailEngagementEvent.EventType.values:
        return False
    now = timezone.now()
    try:
        with transaction.atomic():
            tracker = EmailEngagementTracker.objects.filter(token=token).first()
            if tracker is None:
                return False
            EmailEngagementEvent.objects.create(
                tracker=tracker,
                event_type=event_type,
            )
            if event_type == EmailEngagementEvent.EventType.OPEN:
                EmailEngagementTracker.objects.filter(pk=tracker.pk).update(
                    first_opened_at=Coalesce("first_opened_at", now),
                    last_opened_at=now,
                    open_count=F("open_count") + 1,
                )
            else:
                EmailEngagementTracker.objects.filter(pk=tracker.pk).update(
                    first_clicked_at=Coalesce("first_clicked_at", now),
                    last_clicked_at=now,
                    click_count=F("click_count") + 1,
                )
        return True
    except (DatabaseError, ValueError, TypeError):
        logger.exception("email_tracking.event_write_failed type=%s", event_type)
        return False


def decode_click(payload: str) -> tuple[str, str] | None:
    """Return ``(tracker token, destination)`` for an untampered HTTP(S) link."""
    try:
        value = signing.loads(payload, salt=CLICK_SALT, max_age=60 * 60 * 24 * 365 * 2)
    except signing.BadSignature:
        return None
    if not isinstance(value, dict):
        return None
    token = str(value.get("token") or "")
    destination = str(value.get("url") or "")
    parsed = urlparse(destination)
    if not token or parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return token, destination
