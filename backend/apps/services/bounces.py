"""Reading bounce notices: the emails a mail server sends back when one of
ours couldn't be delivered ("Undelivered Mail Returned to Sender").

- ``looks_like_bounce(sender, subject)``: whether a message in a sending
  mailbox is one, from its sender and subject alone, so no other message's
  content is ever fetched.
- ``parse_bounce(raw)``: who a notice says didn't get the email, and why, in
  the plain words the pages use ("no such mailbox", "mailbox full"), with the
  bounced email's subject and send time when the notice quotes them.
- ``email_for_subject(subject)``: which system email a quoted subject is, from
  System Emails' subjects (an admin's edit, else the default).

Most notices follow the standard delivery report format (RFC 3464): a
``message/delivery-status`` part with a block per recipient. Some servers send
a plain notice instead, naming who failed in an ``X-Failed-Recipients``
header; anything else isn't read.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes, policy
from email.message import Message
from email.parser import HeaderParser
from email.utils import parsedate_to_datetime

# Who sends notices, and what they're called.
_BOUNCE_SENDERS = ("mailer-daemon", "postmaster", "mail delivery")
_BOUNCE_SUBJECTS = re.compile(
    r"undeliver|delivery status notification|delivery (has )?failed|delivery failure|"
    r"returned mail|failure notice|could not be delivered|couldn't be delivered|non-?delivery",
    re.IGNORECASE,
)
_ADDRESS = re.compile(r"[^\s<>;,\"']+@[^\s<>;,\"']+")

# Why it bounced, from the report's status code (RFC 3463) or the server's words.
NO_MAILBOX = "no such mailbox"
NO_DOMAIN = "domain doesn't exist"
MAILBOX_FULL = "mailbox full"
MAILBOX_DISABLED = "mailbox disabled"
BLOCKED = "blocked by their mail server"
TEMPORARY = "temporarily undeliverable"
UNDELIVERED = "couldn't be delivered"

_REASONS = (
    (("5.1.1", "5.1.0", "5.1.10"), r"no such (user|mailbox|recipient)|user unknown|unknown user|"
     r"does not exist|doesn't exist|recipient not found|invalid recipient|address rejected|"
     r"mailbox unavailable|unknown recipient", NO_MAILBOX),
    (("5.1.2", "4.1.2"), r"domain not found|host not found|no mx|unrout(e)?able|name or service not known",
     NO_DOMAIN),
    (("5.2.2", "4.2.2"), r"mailbox (is )?full|over ?quota|quota exceeded|insufficient storage", MAILBOX_FULL),
    (("5.2.1",), r"mailbox (is )?disabled|account (is )?(disabled|inactive|suspended)", MAILBOX_DISABLED),
    (("5.7",), r"blocked|spam|blacklist|blocklist|policy|not authori[sz]ed|access denied", BLOCKED),
)


@dataclass(frozen=True)
class Bounce:
    """Someone a notice says didn't get our email."""

    address: str  # lower case
    reason: str
    # A permanent failure (5.x.x), not a temporary one (4.x.x).
    permanent: bool
    # The bounced email's subject and send time, when the notice quotes them.
    subject: str = ""
    sent_at: datetime | None = None


def looks_like_bounce(sender: str, subject: str) -> bool:
    """Whether a message is a bounce notice, from its sender and subject."""
    sender = (sender or "").lower()
    return any(word in sender for word in _BOUNCE_SENDERS) or bool(_BOUNCE_SUBJECTS.search(subject or ""))


def reason_for(status: str, words: str) -> str:
    """Why it bounced, in a few plain words: from the status code (e.g.
    "5.1.1"), else the server's own words."""
    status, words = (status or "").strip(), (words or "").lower()
    for codes, pattern, reason in _REASONS:
        if status.startswith(codes) or re.search(pattern, words):
            return reason
    return TEMPORARY if status.startswith("4") else UNDELIVERED


def parse_bounce(raw: bytes) -> list[Bounce]:
    """Who a notice says didn't get the email, each once. Only failures count:
    a "delayed" report means the server is still trying."""
    message = message_from_bytes(raw, policy=policy.default)
    original = _original_headers(message)
    subject = " ".join(str(original.get("Subject", "")).split()) if original else ""
    sent_at = _date(original.get("Date")) if original else None
    found: dict[str, Bounce] = {}
    report = _part(message, "message/delivery-status")
    if report is not None:
        for fields in _recipient_blocks(report):
            if fields.get("action", "").lower() != "failed":
                continue
            address = _address(fields.get("final-recipient") or fields.get("original-recipient") or "")
            if address:
                status = fields.get("status", "")
                found.setdefault(address, Bounce(
                    address, reason_for(status, fields.get("diagnostic-code", "")),
                    not status.startswith("4"), subject, sent_at,
                ))
    else:
        failed = ",".join(str(value) for value in message.get_all("X-Failed-Recipients", []))
        words = _text(message)
        for match in _ADDRESS.findall(failed):
            address = match.lower()
            found.setdefault(address, Bounce(address, reason_for("", words), True, subject, sent_at))
    return list(found.values())


def email_for_subject(subject: str) -> str | None:
    """Which system email a bounced email's subject is: the key of the one
    whose subject (an admin's edit on System Emails, else the default) it
    matches, its merge tags matching anything. Subjects that are mostly merge
    tags, e.g. "{{ reminder_subject }}", would match anything, so are left out."""
    from .email_registry import EMAIL_TYPES
    from .models import SystemEmailTemplate

    subject = _plain(subject)
    if not subject:
        return None
    edited = dict(SystemEmailTemplate.objects.exclude(subject="").values_list("key", "subject"))
    for email_type in EMAIL_TYPES:
        pattern = _subject_pattern(edited.get(email_type.key) or email_type.default_subject)
        if pattern and pattern.fullmatch(subject):
            return email_type.key
    return None


_TAG = re.compile(r"\{\{\s*\w+\s*\}\}")


def _subject_pattern(template: str):
    parts = _TAG.split(template or "")
    if len(re.sub(r"\W", "", "".join(parts))) < 6:
        return None
    return re.compile(".+?".join(re.escape(_plain(part)) for part in parts), re.IGNORECASE | re.DOTALL)


def _plain(text: str) -> str:
    return " ".join((text or "").split())


def _part(message: Message, content_type: str) -> Message | None:
    for part in message.walk():
        if part.get_content_type() == content_type:
            return part
    return None


def _original_headers(message: Message):
    """The bounced email's headers, when the notice quotes it (in full, or
    its headers only)."""
    quoted = _part(message, "message/rfc822")
    if quoted is not None:
        payload = quoted.get_payload()
        if isinstance(payload, list) and payload:
            return payload[0]
    headers = _part(message, "text/rfc822-headers")
    if headers is not None:
        return HeaderParser(policy=policy.default).parsestr(_body(headers))
    return None


def _recipient_blocks(report: Message) -> list[dict[str, str]]:
    """The report's blocks of fields, lower-cased names to values: one for the
    message, then one per recipient."""
    payload = report.get_payload()
    if isinstance(payload, list):
        return [{name.lower(): str(value) for name, value in block.items()} for block in payload]
    blocks, fields = [], {}
    for line in [*str(payload).splitlines(), ""]:
        if not line.strip():
            if fields:
                blocks.append(fields)
                fields = {}
        elif ":" in line and not line[:1].isspace():
            name, value = line.split(":", 1)
            fields[name.strip().lower()] = value.strip()
    return blocks


def _address(value: str) -> str:
    """"rfc822; Amy@X.com" as "amy@x.com"."""
    match = _ADDRESS.search(value.split(";", 1)[-1])
    return match.group(0).lower() if match else ""


def _date(value) -> datetime | None:
    try:
        return parsedate_to_datetime(str(value)) if value else None
    except (TypeError, ValueError):
        return None


def _body(part: Message) -> str:
    """A text part's words: in its own charset, else UTF-8 (notices often
    quote 8-bit headers without saying)."""
    raw = part.get_payload(decode=True)
    if not isinstance(raw, bytes):
        return str(part.get_payload() or "")
    try:
        return raw.decode(part.get_content_charset() or "utf-8", errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _text(message: Message) -> str:
    return "\n".join(_body(part) for part in message.walk() if part.get_content_type() == "text/plain")
