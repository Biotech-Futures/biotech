"""Sending the bulk emails: one email per team for the team emails (the
finalist, non-finalist and non-submission emails, and the group results
email), its students in To and its mentors and supervisors in CC; and one
per supervisor for the supervisor results email.

Each address a team's email goes to is recorded, so a retry emails only the
people a run missed and nobody gets a second copy. An address the mail server
refuses while taking the rest counts as missed, not as emailed. A copy that fails gets
a reason the page can show next to the person's name. A dropped connection is
opened again and the copy sent once more, so one drop doesn't fail every
email after it on that connection; the run tries the copies that failed once
more at its end (see ``send_guard``). When the mail server can't be reached,
a copy is kept and sent once it can be, every 10 minutes for 3 days (see
``services.waiting_email``): each address it reaches is recorded then, so
pressing Send again emails nobody twice.
"""
from __future__ import annotations

import logging
import smtplib

from django.db import IntegrityError, transaction

from apps.groups.models.groups import Groups
from apps.services.retry import WAITING, send_noting_refused
from apps.services.system_email import RenderedEmail, build_message, sender_connection, sender_for
from apps.services.waiting_email import WAITING_REASON, send_or_wait
from apps.submissions.emails import to_and_cc

from ..models import EmailDelivery, EmailSendRun

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


def _send_noting_refused(message) -> dict[str, str]:
    """Send ``message``, giving each address the mail server refused while it
    took the rest, with why."""
    return {
        address: failure_reason(smtplib.SMTPRecipientsRefused({address: reply}))
        for address, reply in send_noting_refused(message).items()
    }


def deliver(message, *, email: str, on_sent: dict | None = None) -> tuple[str, dict[str, str]]:
    """Send ``message``, ``email``'s copy: ``("", refused)`` once it's gone,
    ``refused`` being each address the mail server turned away while taking
    the rest, with why; else ``(why not, {})``. A lost connection is opened
    again and the copy sent once more; when the server can't be reached, the
    copy is kept to send later, with ``on_sent`` its hooks, and why not is
    ``WAITING_REASON``."""
    try:
        refused = send_or_wait(message, key=email, send=lambda: _send_noting_refused(message), on_sent=on_sent)
    except Exception as exc:  # noqa: BLE001
        return failure_reason(exc), {}
    if refused is WAITING:
        return WAITING_REASON, {}
    return "", refused


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
    """A connection for one send, signed in as ``email``'s sender (see
    ``system_email.sender_for``), opened if the mail server can be reached:
    when it can't, the send tries again and keeps the copy to send later."""
    connection = sender_connection(sender_for(email), fail_silently=False)
    try:
        connection.open()
    except Exception as exc:  # noqa: BLE001
        logger.error("%s: mail server unreachable %s error=%s", email, log_as, type(exc).__name__)
    return connection


def _hooks(email: str, group=None) -> dict:
    """A kept copy's hooks (see ``services.waiting_email``): who it's still
    due, and recording who it reaches, or doesn't, once it goes."""
    return {
        "due": "apps.management.services.delivery.waiting_due",
        "sent": "apps.management.services.delivery.waiting_sent",
        "missed": "apps.management.services.delivery.waiting_missed",
        "email": email,
        "group_id": group.id if group is not None else None,
    }


def send_group(
    rendered: RenderedEmail, addresses, connection=None, *, email: str, group, files=(), log_as: str,
    cc_staff: bool = True,
) -> dict[str, str]:
    """``group``'s one email to those of ``addresses`` it's still due: its
    students in To, its mentors and supervisors in CC (in To when no student
    is due it, or without ``cc_staff``), replies going back to the sender.
    Each address is recorded once it's gone. Without ``connection`` it opens one of its own. Returns
    ``{address: why}`` for everyone it was for when it couldn't go, or for
    those the mail server refused when it took the rest."""
    done = already_sent(email, [group.id]).get(group.id, set())
    due = [address for address in addresses if address.lower() not in done]
    if not due:
        return {}
    to, cc = to_and_cc(group, due) if cc_staff else (due, [])
    if not to:
        to, cc = cc, []
    own = connection is None
    if own:
        connection = _own_connection(email, log_as)
    try:
        message = build_message(
            rendered, to, from_email=sender_for(email).from_email, connection=connection, files=files,
        )
        message.cc = cc
        reason, refused = deliver(message, email=email, on_sent=_hooks(email, group))
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
    on_sent: dict | None = None,
) -> dict[str, str]:
    """Each address its own copy, so nobody sees the others, with replies going
    back to the sender: the supervisor results email. With ``group``: anyone who
    already has ``email`` from that team is skipped, and each copy that goes is
    recorded. Without ``connection`` it opens one of its own. ``on_sent`` adds
    to a kept copy's hooks (see ``_hooks``). Returns ``{address: why}`` for
    those it couldn't reach."""
    own = connection is None
    if own:
        connection = _own_connection(email, log_as)
    done = already_sent(email, [group.id]).get(group.id, set()) if group is not None else set()
    failed: dict[str, str] = {}
    try:
        for address in addresses:
            if address.lower() in done:
                continue
            message = build_message(
                rendered, address, from_email=sender_for(email).from_email, connection=connection, files=files,
            )
            # One address: a refusal fails the send.
            reason, _ = deliver(message, email=email, on_sent={**_hooks(email, group), **(on_sent or {})})
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


# --- kept copies (see ``services.waiting_email``) ---------------------------


def waiting_due(details: dict, addresses: list[str]) -> list[str]:
    """Who a kept team copy is still due: anyone who has the email since
    (Resend Email To Missed Individuals, say) isn't sent it again."""
    group_id = details.get("group_id")
    if group_id is None:
        return addresses
    done = already_sent(details["email"], [group_id]).get(group_id, set())
    return [address for address in addresses if address.lower() not in done]


def waiting_sent(details: dict, addresses: list[str]) -> None:
    """A kept copy went: each address recorded, as a copy that goes at once
    is, and taken off its run's missed list."""
    group_id = details.get("group_id")
    group = Groups.objects.filter(pk=group_id).first() if group_id else None
    if group is not None:
        for address in addresses:
            _record(details["email"], group, address)
    _settle_run(details["email"], addresses, None)


def waiting_missed(details: dict, missed: dict[str, str]) -> None:
    """A kept copy was given up on, or turned away: its run lists them with why."""
    _settle_run(details["email"], list(missed), missed)


def _settle_run(email: str, addresses, missed: dict[str, str] | None) -> None:
    """``email``'s run's missed list, for those whose kept copy went (off the
    list, and counted as emailed) or didn't (``missed``: listed with why)."""
    lowered = {address.lower() for address in addresses}
    reasons = {address.lower(): reason for address, reason in (missed or {}).items()}
    with transaction.atomic():
        run = EmailSendRun.objects.select_for_update().filter(key=email).first()
        if run is None:
            return
        entries, emailed = [], 0
        for entry in run.missed:
            # "amy@x.com (BTF07, Amy Chen)": the address comes first.
            who = entry.get("who", "") if isinstance(entry, dict) else ""
            address = who.split(" (", 1)[0].strip().lower()
            if address in lowered and entry.get("reason") == WAITING_REASON:
                if missed is None:
                    emailed += 1
                    continue
                entry = {**entry, "reason": reasons[address]}
            entries.append(entry)
        run.missed = entries
        run.emailed += emailed
        run.save(update_fields=["missed", "emailed"])
