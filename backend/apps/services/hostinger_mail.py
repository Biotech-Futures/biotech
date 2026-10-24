"""Reading the sending mailboxes through Hostinger's Mail API, for
``check_bounced_emails``. Read-only: nothing here flags, moves or deletes a
message.

- ``mailboxes()``: the mailboxes the key reaches, ``{"id", "address"}`` each.
- ``newest_messages(mailbox_id)``: its inbox's messages, newest first, page by
  page, as ``MailMessage`` (sender, subject, time, no content).
- ``source(mailbox_id, uid)``: one message in full, as sent (RFC 822).

Signs in with ``settings.HOSTINGER_MAIL_API_KEY``, made in hPanel under the
email domain's Agentic Mail > API access. The key and the request URLs are
never logged; a failure raises ``MailApiError`` with its status code only.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

import requests
from django.conf import settings
from django.utils.dateparse import parse_datetime

INBOX = "INBOX"
PER_PAGE = 100
# Who's asking, by name: Cloudflare, in front of the Mail API, turns away
# requests' own "python-requests/..." with a 403 page before the API sees the
# key, so every check failed as if the key were refused.
USER_AGENT = "BIOTechFutures-BounceCheck/1.0 (+https://biotechfutures.org)"


class MailApiError(Exception):
    """The Mail API couldn't be read: no answer, or an error status
    (``status``, None when it didn't answer)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class MailMessage:
    uid: int
    sender: str
    subject: str
    received_at: datetime | None
    message_id: str


def _get(path: str, params: dict | None = None) -> requests.Response:
    url = f"{settings.HOSTINGER_MAIL_API_URL.rstrip('/')}{path}"
    try:
        response = requests.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {settings.HOSTINGER_MAIL_API_KEY}", "User-Agent": USER_AGENT},
            timeout=settings.HOSTINGER_MAIL_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        # Not the exception's text: it carries the URL.
        raise MailApiError(f"Couldn't reach the Mail API ({type(exc).__name__}).") from None
    if response.status_code != 200:
        raise MailApiError(f"The Mail API answered {response.status_code}.", status=response.status_code)
    return response


def _data(body):
    """The answer without its envelope: ``{"data": ...}`` or as it is."""
    return body.get("data", body) if isinstance(body, dict) else body


def mailboxes() -> list[dict]:
    """The mailboxes the key reaches: ``{"id", "address"}`` each."""
    me = _data(_get("/api/v1/me").json())
    boxes = me if isinstance(me, list) else (me or {}).get("mailboxes", [])
    return [
        {"id": str(box.get("resourceId") or box.get("id")), "address": str(box.get("address", "")).lower()}
        for box in boxes
        if isinstance(box, dict) and (box.get("resourceId") or box.get("id")) and box.get("address")
    ]


def newest_messages(mailbox_id: str, max_pages: int = 20) -> Iterator[MailMessage]:
    """The inbox's messages, newest first, up to ``max_pages`` pages; the
    caller stops reading when it's seen enough."""
    path = f"/api/v1/mailboxes/{quote(mailbox_id, safe='')}/folders/{INBOX}/messages"
    for page in range(1, max_pages + 1):
        items = _data(_get(path, {"page": page, "perPage": PER_PAGE, "sort": "-uid"}).json()) or []
        for item in items:
            if isinstance(item, dict) and item.get("uid") is not None:
                yield MailMessage(
                    uid=int(item["uid"]),
                    sender=_sender(item.get("from")),
                    subject=str(item.get("subject") or ""),
                    received_at=parse_datetime(str(item.get("date") or "")),
                    message_id=str(item.get("messageId") or ""),
                )
        if len(items) < PER_PAGE:
            return


def source(mailbox_id: str, uid: int) -> bytes:
    """One message in full, as sent."""
    path = f"/api/v1/mailboxes/{quote(mailbox_id, safe='')}/folders/{INBOX}/messages/{int(uid)}/source"
    return _get(path).content


def _sender(value) -> str:
    """The From field, as text: "Mail Delivery System <MAILER-DAEMON@x>"."""
    if isinstance(value, list):
        return ", ".join(_sender(item) for item in value)
    if isinstance(value, dict):
        address = value.get("address") or value.get("email") or ""
        return f"{value.get('name') or ''} <{address}>".strip()
    return str(value or "")
