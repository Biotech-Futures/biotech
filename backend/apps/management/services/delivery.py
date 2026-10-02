"""Sending a bulk email's copies, one per person, for the team emails (the
finalist, non-finalist and non-submission emails, and the group results
email) and the supervisor results email.

Each copy that goes to someone on a team is recorded, so a retry emails only
the people a run missed and nobody gets a second copy. A copy that fails gets
a reason the page can show next to the person's name. A dropped connection is
opened again, so one drop doesn't fail every email after it on that
connection; the run tries the copies that failed once more at its end (see
``send_guard``).
"""
from __future__ import annotations

import logging
import smtplib

from django.conf import settings
from django.core.mail import get_connection
from django.db import IntegrityError, transaction

from apps.services.system_email import RenderedEmail, build_message

from ..models import EmailDelivery

logger = logging.getLogger(__name__)

UNREACHABLE = "couldn't reach the mail server"


def _reply(exc: Exception) -> tuple[int | None, str]:
    """The mail server's reply code and text (lower case), if it gave one."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused) and exc.recipients:
        code, text = next(iter(exc.recipients.values()))
    elif isinstance(exc, smtplib.SMTPResponseException):
        code, text = exc.smtp_code, exc.smtp_error
    else:
        return None, ""
    if isinstance(text, bytes):
        text = text.decode(errors="replace")
    return code, str(text).lower()


def failure_reason(exc: Exception) -> str:
    """Why a copy didn't go, in a few words for the page. Never the server's
    own message, which can carry the address."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "mail server login failed"
    code, text = _reply(exc)
    if code and any(word in text for word in ("limit", "quota", "too many", "exceeded")):
        return "sending limit reached"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "mail server busy" if code and code < 500 else "address refused"
    if code:
        return "mail server busy" if code < 500 else "mail server refused it"
    if isinstance(exc, OSError):
        # Disconnects, resets and timeouts (smtplib's disconnect is one too).
        return "lost the mail server connection"
    return "couldn't be sent"


def _reconnect(connection) -> None:
    if connection is None:
        return
    try:
        connection.close()
    except Exception:  # noqa: BLE001
        pass
    try:
        connection.open()
    except Exception:  # noqa: BLE001
        pass  # the second try reports it


def deliver(message) -> str:
    """Send ``message``: "" once it's gone, else why not. A lost connection
    is opened again for the emails after it."""
    try:
        message.send(fail_silently=False)
        return ""
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, OSError) and not _reply(exc)[0]:
            _reconnect(message.connection)
        return failure_reason(exc)


def already_sent(email: str, group_ids) -> dict[int, set[str]]:
    """Who on each team already has ``email``: ``{group_id: {address, ...}}``."""
    sent: dict[int, set[str]] = {}
    rows = EmailDelivery.objects.filter(email=email, group_id__in=list(group_ids)).values_list("group_id", "address")
    for group_id, address in rows:
        sent.setdefault(group_id, set()).add(address.lower())
    return sent


def still_due(email: str, group, addresses) -> list[str]:
    """``addresses`` on ``group`` that don't have ``email`` yet."""
    done = already_sent(email, [group.id]).get(group.id, set())
    return [address for address in addresses if address.lower() not in done]


def _record(email: str, group, address: str) -> None:
    try:
        with transaction.atomic():
            EmailDelivery.objects.get_or_create(email=email, group=group, address=address.lower())
    except IntegrityError:
        pass  # another run recorded it first


def send_each(
    rendered: RenderedEmail, addresses, connection=None, *, email: str, group=None, files=(), log_as: str,
) -> dict[str, str]:
    """Each address its own copy, so nobody sees the others, with replies going
    to support. With ``group``: anyone who already has ``email`` from that team
    is skipped, and each copy that goes is recorded. Without ``connection`` it
    opens one of its own. Returns ``{address: why}`` for those it couldn't
    reach."""
    own = connection is None
    if own:
        connection = get_connection(fail_silently=False)
        try:
            connection.open()
        except Exception as exc:  # noqa: BLE001
            logger.error("%s: mail server unreachable %s error=%s", email, log_as, type(exc).__name__)
            return {address: UNREACHABLE for address in addresses}
    done = already_sent(email, [group.id]).get(group.id, set()) if group is not None else set()
    failed: dict[str, str] = {}
    try:
        for address in addresses:
            if address.lower() in done:
                continue
            message = build_message(
                rendered, address, from_email=settings.DEFAULT_FROM_EMAIL, connection=connection, files=files,
            )
            message.reply_to = [settings.SUPPORT_EMAIL]
            reason = deliver(message)
            if reason:
                # The reason only: SMTP errors carry the recipient address.
                logger.error("%s: send failed %s reason=%s", email, log_as, reason)
                failed[address] = reason
            elif group is not None:
                _record(email, group, address)
    finally:
        if own:
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass
    return failed
