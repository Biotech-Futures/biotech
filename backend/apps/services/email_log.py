"""The Log on System Emails: when each email last went out, who sent it, and
who its latest sends couldn't reach, and why.

Each send of a system email notes itself here (``note_send``), except the
bulk emails sent from Management, whose runs keep the same details
(``management.EmailSendRun``) and are read from there. Test sends aren't
noted. A note that can't be written never stops the email.
"""
import logging
from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from .email_registry import EMAIL_TYPES
from .models import SystemEmailLog, SystemEmailSettings

logger = logging.getLogger(__name__)

# How many of an email's sends that missed someone the Log keeps.
MISSED_KEPT = 20

# Why someone was missed when there's nothing more specific to say.
NOT_SENT = "couldn't be sent"
# Why everyone was missed when the mail server couldn't be reached at all.
UNREACHABLE = "couldn't reach the mail server"


def reason_for(exc: Exception) -> str:
    """Why a send failed, in the words Notify Finalists uses, e.g. "address
    refused" or "couldn't reach the mail server"."""
    from apps.management.services.delivery import failure_reason

    return failure_reason(exc)


def note_send(key: str, *, missed=None, by=None) -> None:
    """Note a send of ``key`` now: ``missed`` ({address: reason}) for those it
    didn't reach, ``by`` the signed-in person who sent it, if anyone."""
    by_id = by.pk if getattr(by, "is_authenticated", False) else None
    now = timezone.now()
    try:
        # Its own savepoint: a note that fails leaves the caller's work be.
        with transaction.atomic():
            log, _ = SystemEmailLog.objects.select_for_update().get_or_create(key=key)
            log.last_sent_at = now
            log.last_sent_by_id = by_id
            if missed:
                entry = {
                    "at": now.isoformat(),
                    "missed": [{"address": address, "reason": reason} for address, reason in missed.items()],
                }
                log.missed = [entry, *log.missed][:MISSED_KEPT]
            log.save()
    except Exception:  # noqa: BLE001
        logger.exception("email_log.note_failed key=%s", key)


def unseen_failures() -> int:
    """How many people sends couldn't reach since an admin last looked at
    Failed Sending Emails (every one listed, if nobody has yet)."""
    from apps.management.models import EmailSendRun

    seen = SystemEmailSettings.get().failures_seen_at
    count = 0
    for log in SystemEmailLog.objects.exclude(missed=[]):
        for entry in log.missed:
            if seen is None or datetime.fromisoformat(entry["at"]) > seen:
                count += len(entry["missed"])
    runs = EmailSendRun.objects.filter(started_at__isnull=False).exclude(missed=[])
    if seen is not None:
        runs = runs.filter(started_at__gt=seen)
    return count + sum(len(run.missed) for run in runs)


def mark_failures_seen() -> int:
    """An admin has looked at Failed Sending Emails: none are unseen now."""
    SystemEmailSettings.get()
    # update(), so the switch's own updated_at stays put.
    SystemEmailSettings.objects.filter(pk=SystemEmailSettings.SINGLETON_PK).update(failures_seen_at=timezone.now())
    return unseen_failures()


def _who(address: str, groups: list[str], name: str = "") -> str:
    """"amy@x.com (BTF07, Amy Chen)", as Notify Finalists lists someone."""
    parts = [*groups, name] if name and name != address else list(groups)
    return f"{address} ({', '.join(parts)})" if parts else address


def _labels(addresses) -> dict[str, str]:
    """Each address as the Log lists it: a person with this year's groups,
    "pat@x.com (BTF07, guardian of Pat Lee)" for a guardian, else the
    address alone."""
    from apps.groups.models.group_members import GroupMembership
    from apps.submissions.services import current_cohort
    from apps.users.models import StudentProfile, User

    lowered = {address.strip().lower() for address in addresses}
    if not lowered:
        return {}
    groups: dict[int, list[str]] = {}
    for user_id, group in (
        GroupMembership.objects.filter(
            left_at__isnull=True, group__deleted_at__isnull=True, group__year=current_cohort(),
        )
        .order_by("group__group_name")
        .values_list("user_id", "group__group_name")
    ):
        groups.setdefault(user_id, []).append(group)

    people = {}
    for user in User.objects.annotate(lowered=Lower("email")).filter(lowered__in=lowered):
        people[user.lowered] = (groups.get(user.id, []), user.get_full_name())
    guardians = (
        StudentProfile.objects.annotate(pg=Lower("pg_email"), pending=Lower("pending_pg_email"))
        .filter(Q(pg__in=lowered) | Q(pending__in=lowered))
        .select_related("user")
    )
    for profile in guardians:
        label = (groups.get(profile.user_id, []), f"guardian of {profile.user.get_full_name() or profile.user.email}")
        for address in (profile.pg, profile.pending):
            if address in lowered:
                people.setdefault(address, label)

    shown = {}
    for address in addresses:
        found = people.get(address.strip().lower())
        shown[address] = _who(address, *found) if found else address
    return shown


def _person(user) -> str:
    return (user.get_full_name() or user.email) if user else ""


def email_log() -> list[dict]:
    """Every system email, in the order System Emails lists them: when it
    last went out and who sent it, where mail it couldn't deliver comes back
    to, and who its latest sends couldn't reach, newest first, as
    ``{"at", "people": [{"who", "reason"}]}``."""
    from apps.management.models import EmailSendRun
    from apps.management.services.send_guard import _missed_entry, _with_addresses

    from .system_email import sender_for

    logs = {log.key: log for log in SystemEmailLog.objects.select_related("last_sent_by")}
    runs = {
        run.key: run
        for run in EmailSendRun.objects.filter(started_at__isnull=False).select_related("started_by")
    }
    labels = _labels({
        missed["address"] for log in logs.values() for entry in log.missed for missed in entry["missed"]
    })

    emails = []
    for email_type in EMAIL_TYPES:
        key = email_type.key
        run, log = runs.get(key), logs.get(key)
        if run:
            # A Management bulk email: its last run, and who that still missed.
            last_at, last_by = run.started_at, _person(run.started_by)
            people = _with_addresses([_missed_entry(entry) for entry in run.missed])
            missed = [{"at": run.started_at.isoformat(), "people": people}] if people else []
        elif log:
            last_at, last_by = log.last_sent_at, _person(log.last_sent_by)
            missed = [
                {
                    "at": entry["at"],
                    "people": [
                        {"who": labels.get(person["address"], person["address"]), "reason": person["reason"]}
                        for person in entry["missed"]
                    ],
                }
                for entry in log.missed
            ]
        else:
            last_at, last_by, missed = None, "", []
        emails.append({
            "key": key,
            "name": email_type.name,
            "lastSentAt": last_at.isoformat() if last_at else None,
            "lastSentBy": last_by,
            # Where mail it can't deliver comes back to.
            "sentFrom": sender_for(key).address,
            # One email per group, so the rest of a group still gets it.
            "toGroups": bool(email_type.delivery),
            "missed": missed,
        })
    return emails
