"""Checking the sending mailboxes for bounce notices (``check_bounced_emails``),
so the pages show who our emails didn't reach after the mail server took them.

GitHub runs it about every 10 minutes (``.github/workflows/bounce-check.yml``)
through ``POST /api/v1/management/bounce-check/``, which starts it on a
background thread (``start_check``); ``manage.py check_bounced_emails`` runs it
by hand.

Each run reads, through Hostinger's Mail API, each sending mailbox's inbox
messages newer than the last run's (``BounceCheckpoint``), back at most
``settings.BOUNCE_LOOKBACK_DAYS``. Only messages that look like bounce notices
are opened, and each is read once (``BounceNotice``). The mailbox itself is
never changed.

Each bounce is matched to the email it was:

- a Management bulk email (Notify Finalists, Notify Nonfinalist, Release
  Results): the latest send recorded to that address (``EmailDelivery``) at or
  before the bounced email's time. That person is missed again: their record
  goes, the team is no longer counted as emailed, and the page lists them
  among who the send missed ("bounced: mailbox full"), so Resend Email To
  Missed Individuals emails them.
- another system email: the one whose subject the bounced email's has.

Each matched bounce is kept (``EmailBounce``) with when it was found, for the
System Emails Log's Bounced emails. A bounce matching neither is skipped.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.utils import timezone

from apps.common.pii import email_log_tag
from apps.services import hostinger_mail
from apps.services.bounces import Bounce, email_for_subject, looks_like_bounce, parse_bounce
from apps.services.email_log import BOUNCED, _labels
from apps.services.models import EmailBounce
from apps.services.system_email import senders

from ..models import BounceCheckpoint, BounceNotice, EmailDelivery, EmailSendRun
from .send_guard import member_labels

logger = logging.getLogger(__name__)

# A send's record is saved a little after the email's own Date header.
RECORD_LAG = timedelta(minutes=10)

# Held while a check runs, across every worker (the cache is Redis in
# production), so two never overlap; it lapses on its own if a run dies.
RUNNING = "bounce_check:running"
RUNNING_FOR = 15 * 60

# What starting a check said: started, one already going, or no key set.
STARTED, ALREADY_RUNNING, SWITCHED_OFF = "started", "already running", "off: HOSTINGER_MAIL_API_KEY isn't set"


@dataclass
class CheckResult:
    mailboxes: int = 0
    notices: int = 0
    bounces: int = 0
    matched: int = 0


def start_check() -> str:
    """Start a check on a background thread, so the trigger answers at once:
    ``STARTED``, ``ALREADY_RUNNING`` when one is going, or ``SWITCHED_OFF``
    with no Mail API key."""
    if not settings.HOSTINGER_MAIL_API_KEY:
        return SWITCHED_OFF
    if not cache.add(RUNNING, True, RUNNING_FOR):
        return ALREADY_RUNNING
    threading.Thread(target=_run_check, daemon=True, name="bounce-check").start()
    return STARTED


def _run_check() -> None:
    try:
        check_bounces()
    except Exception:  # noqa: BLE001
        # Safe to log: a Mail API error never carries its URL or key (see hostinger_mail).
        logger.exception("bounce_check.failed")
    finally:
        cache.delete(RUNNING)
        close_old_connections()


def check_bounces(now=None) -> CheckResult:
    """Read each sending mailbox's new bounce notices and note who they say
    didn't get our emails. Nothing when no Mail API key is set."""
    result = CheckResult()
    if not settings.HOSTINGER_MAIL_API_KEY:
        return result
    now = now or timezone.now()
    since = now - timedelta(days=settings.BOUNCE_LOOKBACK_DAYS)
    ours = {sender.address.lower() for sender in senders() if sender.address}
    for mailbox in hostinger_mail.mailboxes():
        if mailbox["address"] in ours:
            result.mailboxes += 1
            _check_mailbox(mailbox, since, now, result)
    logger.info(
        "bounce_check: mailboxes=%s notices=%s bounces=%s matched=%s",
        result.mailboxes, result.notices, result.bounces, result.matched,
    )
    return result


def _check_mailbox(mailbox: dict, since, now, result: CheckResult) -> None:
    address = mailbox["address"]
    checkpoint, _ = BounceCheckpoint.objects.get_or_create(mailbox=address)
    newest = checkpoint.last_uid
    for message in hostinger_mail.newest_messages(mailbox["id"]):
        if message.uid <= checkpoint.last_uid or (message.received_at and message.received_at < since):
            break
        newest = max(newest, message.uid)
        if not looks_like_bounce(message.sender, message.subject):
            continue
        key = (message.message_id or f"uid:{message.uid}")[:255]
        if BounceNotice.objects.filter(mailbox=address, message_key=key).exists():
            continue
        bounces = parse_bounce(hostinger_mail.source(mailbox["id"], message.uid))
        matched = sum(1 for bounce in bounces if record_bounce(bounce, message.received_at or now, now))
        BounceNotice.objects.get_or_create(mailbox=address, message_key=key, defaults={"matched": matched})
        result.notices += 1
        result.bounces += len(bounces)
        result.matched += matched
    if newest > checkpoint.last_uid:
        checkpoint.last_uid = newest
        checkpoint.save(update_fields=["last_uid", "checked_at"])


def record_bounce(bounce: Bounce, notice_at, found_at=None) -> bool:
    """Note ``bounce`` against the email it was; whether it matched one.
    ``found_at``: when the check found it (now, if not given)."""
    found_at = found_at or timezone.now()
    reason = f"{BOUNCED}{bounce.reason}"
    sent_by = (bounce.sent_at or notice_at) + RECORD_LAG
    delivery = (
        EmailDelivery.objects.select_related("group")
        .filter(
            address=bounce.address,
            sent_at__lte=sent_by,
            sent_at__gte=notice_at - timedelta(days=settings.BOUNCE_LOOKBACK_DAYS),
        )
        .order_by("-sent_at")
        .first()
    )
    if delivery is not None:
        _missed_again(delivery, bounce, reason, found_at)
        return True
    key = email_for_subject(bounce.subject)
    if key is None:
        logger.info("bounce_check: unmatched bounce to=%s", email_log_tag(bounce.address))
        return False
    who = _labels([bounce.address]).get(bounce.address, bounce.address)
    with transaction.atomic():
        if EmailSendRun.objects.filter(key=key).exists():
            # A Management email with no per-person record (e.g. supervisors'
            # results): listed on its page, under who the last send missed.
            _list_missed(key, who, reason)
        EmailBounce.objects.create(
            key=key, address=bounce.address, who=who, reason=bounce.reason, detected_at=found_at,
        )
    return True


def _missed_again(delivery: EmailDelivery, bounce: Bounce, reason: str, found_at) -> None:
    """A Management email that bounced: its person is due it again, and its
    page lists them as missed."""
    key, group, address = delivery.email, delivery.group, delivery.address
    who = member_labels(group, [address])[address]
    with transaction.atomic():
        delivery.delete()
        _not_emailed(key, group)
        _list_missed(key, who, reason)
        EmailBounce.objects.create(key=key, address=address, who=who, reason=bounce.reason, detected_at=found_at)


def _not_emailed(key: str, group) -> None:
    """``group`` no longer counts as emailed ``key``'s email, so the next send
    (and Resend Email To Missed Individuals) includes it again."""
    from apps.grading.models import FinalistFlag

    from ..models import NonFinalistEmail, NonSubmissionEmail, ResultsTeamEmail
    from .finalist_notify import EMAIL_KEY as FINALIST
    from .results_notify import EMAIL_KEYS, GROUPS
    from .symposium_emails import NONFINALIST, NONSUBMISSION

    if key == FINALIST:
        FinalistFlag.objects.filter(group=group).update(notified=False)
        return
    record = {
        NONFINALIST.key: NonFinalistEmail,
        NONSUBMISSION.key: NonSubmissionEmail,
        EMAIL_KEYS[GROUPS]: ResultsTeamEmail,
    }.get(key)
    if record is not None:
        record.objects.filter(group=group).delete()


def _list_missed(key: str, who: str, reason: str) -> None:
    """Add someone to who ``key``'s last send missed, once."""
    entry = {"who": who, "reason": reason}
    with transaction.atomic():
        run, _ = EmailSendRun.objects.select_for_update().get_or_create(key=key)
        if entry not in run.missed:
            run.missed = [*run.missed, entry]
            run.save(update_fields=["missed"])
