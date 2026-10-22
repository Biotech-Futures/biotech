"""Resend on System Emails' Log: each email's own button, sending it again to
the people the Log lists as having missed it.

* Management's bulk emails (Notify Finalists, the symposium emails, the
  results emails): their own Resend Email To Missed Individuals, refused for
  the same reasons it is on their pages.
* Announcements: each announcement's email built again for the people its
  send missed (``announcement.resend_missed``).
* Every other email: the copies kept when it failed
  (``waiting_email.resend_missed``), from now on.

Any email waiting for the mail server is tried again at once too, rather
than at the next 10-minute run (``waiting_email.send_waiting``).

Login codes and password reset links have no Resend: they expire within
minutes. A Resend sends in its mailbox's turn (``send_guard``), so the page
answers at once.
"""
from __future__ import annotations

from apps.management.models import EmailSendRun

from .email_registry import get_email_type, is_known_email_type
from .models import WaitingEmail
from .system_email import is_email_enabled, sender_for
from .waiting_email import NEVER_WAIT, kept_for_resend, waiting_keys

# The runs that send them, one per mailbox: "resend:info".
JOB = "resend"

# Management's bulk emails, which resend through their own Resend.
FINALIST = "finalist_notification"
SYMPOSIUM = ("nonfinalist_invitation", "nonsubmission_notice")
RESULTS = ("results_team", "results_supervisor")
MANAGEMENT = frozenset({FINALIST, *SYMPOSIUM, *RESULTS})

QUEUED = "Resending. It can take a few minutes: open the log again to see who it reached."
NOBODY = "Nobody it missed can be emailed again."


def job_key(mailbox: str) -> str:
    """The run that resends from ``mailbox``, e.g. "resend:info"."""
    return f"{JOB}:{mailbox}"


def resendable(key: str, *, run=None, announcements=None, kept=None, waiting=None) -> bool:
    """Whether ``key``'s Resend has anyone to email: it has emails waiting for
    the mail server (``waiting``, from ``waiting_email.waiting_keys``); a
    Management email's last run missed someone; an announcement's send missed
    someone (``announcements``, from ``announcement.missed_by_announcement``);
    any other email has copies kept (``kept``, from
    ``waiting_email.kept_for_resend``)."""
    from apps.services.email_log import _waiting

    if key in NEVER_WAIT:
        return False
    if key in (waiting_keys() if waiting is None else waiting):
        return True
    if key in MANAGEMENT:
        return bool(run and any(not _waiting(entry) for entry in run.missed))
    if key == "announcement":
        if announcements is None:
            from apps.admin.services.announcement import missed_by_announcement

            announcements = missed_by_announcement()
        return bool(announcements)
    return key in (kept_for_resend() if kept is None else kept)


def _management_blocked(key: str) -> str:
    if key == FINALIST:
        from apps.management.views.finalist import send_blocked_reason

        return send_blocked_reason()
    if key in SYMPOSIUM:
        from apps.management.models import FinalistEmailSettings
        from apps.management.services.symposium_emails import NONFINALIST, NONSUBMISSION, send_blocked_reason

        email = NONFINALIST if key == NONFINALIST.key else NONSUBMISSION
        return send_blocked_reason(email, FinalistEmailSettings.load())
    from apps.management.models import ResultsEmailSettings
    from apps.management.services.results_notify import EMAIL_KEYS, send_blocked_reason

    audience = next(audience for audience, email in EMAIL_KEYS.items() if email == key)
    return send_blocked_reason(ResultsEmailSettings.load(), audience)


def _management_start(key: str, actor) -> None:
    if key == FINALIST:
        from apps.management.services.send_guard import FINALIST_SEND, queue_send

        queue_send(FINALIST_SEND, actor, {"which": "missed", "group_ids": []})
    elif key in SYMPOSIUM:
        from apps.management.services.symposium_emails import NONFINALIST, NONSUBMISSION, start_send

        start_send(NONFINALIST if key == NONFINALIST.key else NONSUBMISSION, actor, which="missed")
    else:
        from apps.management.services.results_notify import EMAIL_KEYS, start_send

        audience = next(audience for audience, email in EMAIL_KEYS.items() if email == key)
        start_send(actor, audience, which="missed")


def start_resend(key: str, actor) -> str:
    """Start ``key``'s Resend, as ``actor``: "" once it's queued, else why it
    can't go."""
    if not is_known_email_type(key) or key in NEVER_WAIT:
        return "This email can't be resent."
    if not is_email_enabled(key):
        return f"{get_email_type(key).name} is switched off on System Emails."
    from apps.management.services.send_guard import queue_job

    waiting = key in waiting_keys()
    if key in MANAGEMENT:
        run = EmailSendRun.objects.filter(key=key, started_at__isnull=False).first()
        if resendable(key, run=run, waiting=set()):
            blocked = _management_blocked(key)
            if blocked and not waiting:
                return blocked
            if not blocked:
                _management_start(key, actor)
        elif not waiting:
            return NOBODY
    elif not resendable(key):
        return NOBODY
    # Its own Resend, and any of its emails waiting for the mail server.
    if waiting or key not in MANAGEMENT:
        queue_job(job_key(sender_for(key).key), actor, {"key": key})
    return ""


def resend_job(actor, options: dict) -> dict:
    """The queued Resend of one email (``send_guard.JOBS``)."""
    from .waiting_email import resend_missed, send_waiting

    key = options.get("key", "")
    # Those waiting for the mail server first, tried again at once.
    sent = failed = 0
    for mailbox in WaitingEmail.objects.filter(key=key, state=WaitingEmail.State.WAITING).values_list(
        "mailbox", flat=True,
    ).distinct():
        result = send_waiting(mailbox, key=key)
        sent, failed = sent + result["sent"], failed + result["failed"]
    if key in MANAGEMENT:
        result = {"sent": 0, "failed": 0}
    elif key == "announcement":
        from apps.admin.services.announcement import resend_missed as resend_announcements

        result = resend_announcements(actor)
    else:
        result = resend_missed(key, actor)
    return {"sent": sent + result["sent"], "failed": failed + result["failed"]}
