"""Sending the bulk emails: one email per team for the team emails (the
finalist, non-finalist and non-submission emails, and the group results
email), its students in To and its mentors and supervisors in CC; and one
per supervisor for the supervisor results email.

Each address a team's email goes to is recorded, so a retry emails only the
people a run missed and nobody gets a second copy. An address the mail server
refuses while taking the rest counts as missed, not as emailed. A copy that fails gets
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

from apps.groups.models.group_members import GroupMembership
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


def _send_noting_refused(message) -> dict[str, str]:
    """Send ``message``, giving each address the mail server refused while it
    took the rest, with why. smtplib reports those, but Django's sender
    drops them, so this send's ``sendmail`` reply is kept."""
    smtp = getattr(message.connection, "connection", None)
    if smtp is None or not hasattr(smtp, "sendmail"):
        message.send(fail_silently=False)
        return {}
    refused: dict = {}
    original = smtp.sendmail

    def sendmail(*args, **kwargs):
        result = original(*args, **kwargs)
        refused.update(result or {})
        return result

    smtp.sendmail = sendmail
    try:
        message.send(fail_silently=False)
    finally:
        smtp.sendmail = original
    return {
        address: failure_reason(smtplib.SMTPRecipientsRefused({address: reply})) for address, reply in refused.items()
    }


def deliver(message) -> tuple[str, dict[str, str]]:
    """Send ``message``: ``("", refused)`` once it's gone, ``refused`` being
    each address the mail server turned away while taking the rest, with
    why; else ``(why not, {})``. A lost connection is opened again for the
    emails after it."""
    try:
        return "", _send_noting_refused(message)
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, OSError) and not _reply(exc)[0]:
            _reconnect(message.connection)
        return failure_reason(exc), {}


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


def _own_connection(email: str, log_as: str):
    """A connection opened for one send, or None when the mail server can't
    be reached."""
    connection = get_connection(fail_silently=False)
    try:
        connection.open()
    except Exception as exc:  # noqa: BLE001
        logger.error("%s: mail server unreachable %s error=%s", email, log_as, type(exc).__name__)
        return None
    return connection


def to_and_cc(group, addresses) -> tuple[list[str], list[str]]:
    """``addresses`` on ``group`` as its one email takes them: its students in
    To, its mentors and supervisors in CC."""
    students = {
        address.lower()
        for address in GroupMembership.objects.filter(
            group=group, left_at__isnull=True, membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        ).values_list("user__email", flat=True)
        if address
    }
    return (
        [address for address in addresses if address.lower() in students],
        [address for address in addresses if address.lower() not in students],
    )


def send_group(
    rendered: RenderedEmail, addresses, connection=None, *, email: str, group, files=(), log_as: str,
) -> dict[str, str]:
    """``group``'s one email to those of ``addresses`` it's still due: its
    students in To, its mentors and supervisors in CC (in To when no student
    is due it), replies going to support. Each address is recorded once it's
    gone. Without ``connection`` it opens one of its own. Returns
    ``{address: why}`` for everyone it was for when it couldn't go, or for
    those the mail server refused when it took the rest."""
    done = already_sent(email, [group.id]).get(group.id, set())
    due = [address for address in addresses if address.lower() not in done]
    if not due:
        return {}
    to, cc = to_and_cc(group, due)
    if not to:
        to, cc = cc, []
    own = connection is None
    if own:
        connection = _own_connection(email, log_as)
        if connection is None:
            return {address: UNREACHABLE for address in due}
    try:
        message = build_message(rendered, to, from_email=settings.DEFAULT_FROM_EMAIL, connection=connection, files=files)
        message.cc = cc
        message.reply_to = [settings.SUPPORT_EMAIL]
        reason, refused = deliver(message)
    finally:
        if own:
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass
    if reason:
        # The reason only: SMTP errors carry the recipient addresses.
        logger.error("%s: send failed %s reason=%s", email, log_as, reason)
        return {address: reason for address in due}
    why = {address.lower(): reason for address, reason in refused.items()}
    failed = {address: why[address.lower()] for address in due if address.lower() in why}
    if failed:
        logger.error("%s: %s of %s refused %s reasons=%s", email, len(failed), len(due), log_as, sorted(set(why.values())))
    for address in due:
        if address not in failed:
            _record(email, group, address)
    return failed


def send_each(
    rendered: RenderedEmail, addresses, connection=None, *, email: str, group=None, files=(), log_as: str,
) -> dict[str, str]:
    """Each address its own copy, so nobody sees the others, with replies going
    to support: the supervisor results email. With ``group``: anyone who
    already has ``email`` from that team is skipped, and each copy that goes is
    recorded. Without ``connection`` it opens one of its own. Returns
    ``{address: why}`` for those it couldn't reach."""
    own = connection is None
    if own:
        connection = _own_connection(email, log_as)
        if connection is None:
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
            # One address: a refusal fails the send.
            reason, _ = deliver(message)
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
