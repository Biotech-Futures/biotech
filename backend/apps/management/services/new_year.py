"""Start new year (Management > New Year): the platform moves on to the next
challenge year in one go. Last year's students, mentors and supervisors are
signed out and deactivated (registering again brings an account back); its
groups, with their chats and submissions, its group, individual and role
tasks, its events and its announcements are archived; and Management's dates, links, releases and
email progress start again empty. Nothing is deleted: what's archived stays
on record. The marking rubrics, presentation times, Document Setup and the
Known Universities list are left as they are."""
from __future__ import annotations

from datetime import date

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import DateTimeField, F, Q, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from apps.announcements.models import Announcement
from apps.audit.services import log_audit_event
from apps.events.models import Events
from apps.grading.models import FinalistFlag
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import Resources
from apps.services.models import SystemEmailLog
from apps.submissions.models import Deadline, GroupExtension
from apps.submissions.services import current_cohort
from apps.tasks.models import RoleTask, Task
from apps.users.backends import user_cache_key
from apps.users.models import RegistrationInvitation, RegistrationWindow, SupervisorProfile, User
from apps.users.utils.sessions import terminate_sessions_for_users

from ..models import (
    CertificatesRelease,
    ChallengeStart,
    ChallengeYear,
    EmailSendRun,
    FinalistEmailSettings,
    MarksRelease,
    OutcomeAnnouncement,
    PresentationSettings,
    QueuedEmailSend,
    ResultsEmailSettings,
    SupervisorPagesSetting,
)
from .deadline import submissions_still_open
from .finalist_notify import SYMPOSIUM_TZ
from .send_guard import QUEUE_KEY, person_name

# The next year can be started from this day of the current one, on Sydney's calendar.
OPENS_ON = (9, 1)

SUBMISSIONS_OPEN = (
    "Submissions are still open. Start the new year once the deadline and every extension have passed."
)
SENDING = "An email is sending or waiting to send. Start the new year once it has finished."


class CantStart(Exception):
    """Why the next year can't be started now, as the page shows it."""


def _too_early(year: int, now) -> str:
    opens = date(year, *OPENS_ON)
    if timezone.localtime(now, SYMPOSIUM_TZ).date() >= opens:
        return ""
    return f"{year + 1} can be started from 1 September {year}."


def _sending(now) -> bool:
    """A bulk email or a job's email is sending, or waiting its turn."""
    return (
        QueuedEmailSend.objects.exists()
        or EmailSendRun.objects.filter(held_until__gte=now).exists()
    )


def _started(row: ChallengeYear | None) -> dict | None:
    if row is None:
        return None
    return {
        "year": row.year,
        "started_at": row.started_at,
        "started_by": person_name(row.started_by) if row.started_by else "",
        "counts": row.counts,
    }


def new_year_state(now=None) -> dict:
    """The year in progress, the one Start new year would begin, what stops
    it starting now (``blockers``), what's worth knowing first (``warnings``,
    which don't stop it), whether an email is sending (the page checks again
    until it has finished), and when the year in progress was started."""
    now = now or timezone.now()
    year = current_cohort()
    sending = _sending(now)
    blockers = [
        reason for reason in (
            _too_early(year, now),
            SUBMISSIONS_OPEN if submissions_still_open() else "",
            SENDING if sending else "",
        ) if reason
    ]
    warnings = []
    if MarksRelease.load().released_at is None:
        warnings.append("Marks haven't been released.")
    if CertificatesRelease.load().released_at is None:
        warnings.append("Certificates haven't been released.")
    waiting = FinalistFlag.objects.filter(group__deleted_at__isnull=True, notified=False).count()
    if waiting:
        teams = "team hasn't" if waiting == 1 else "teams haven't"
        warnings.append(f"{waiting} finalist {teams} been notified.")
    last = ChallengeYear.objects.select_related("started_by").filter(year=year).first()
    return {
        "year": year,
        "next_year": year + 1,
        "blockers": blockers,
        "warnings": warnings,
        "sending": sending,
        "started": _started(last),
    }


def _people(actor, now) -> dict:
    """Deactivate and sign out every student, mentor and supervisor who can
    still sign in. Admins stay as they are, and so does whoever pressed it.
    Chosen by profile, not role: a student's role ends weeks after they
    register."""
    people = (
        User.objects.filter(
            Q(studentprofile__isnull=False) | Q(mentorprofile__isnull=False) | Q(supervisorprofile__isnull=False)
        )
        .exclude(Q(is_staff=True) | Q(is_superuser=True) | Q(adminscope__isnull=False))
        .exclude(account_status__in=User.INACTIVE_LOGIN_STATUSES)
    )
    if getattr(actor, "pk", None):
        people = people.exclude(pk=actor.pk)
    ids = list(people.values_list("pk", flat=True).distinct())
    User.objects.filter(pk__in=ids).update(account_status=User.AccountStatus.DEACTIVATED, is_active=False)
    sessions = terminate_sessions_for_users(ids)
    # A bulk update skips the signal that clears each cached sign-in, so it's
    # cleared here, once the change is saved, or they'd stay in for a minute.
    transaction.on_commit(lambda: cache.delete_many([user_cache_key(pk) for pk in ids]))
    return {"accounts": len(ids), "sessions": sessions}


def _content(now) -> dict:
    """Archive every group, ending its memberships, and with it its chats
    and submissions, which go wherever their group goes. Archive every task,
    a group's or one person's, every event and announcement, and hide every
    resource."""
    at = Value(now, output_field=DateTimeField())
    # Never before a row began, which the tables refuse.
    memberships = GroupMembership.objects.filter(left_at__isnull=True).update(left_at=Greatest(at, F("joined_at")))
    archived = Greatest(at, F("created_at"))
    groups = Groups.objects.filter(deleted_at__isnull=True).update(deleted_at=archived, archived_at=archived)
    # Group and individual tasks: a group's go with it, and someone's own
    # tasks shouldn't greet them if they register again.
    tasks = Task.objects.filter(deleted_at__isnull=True).update(deleted_at=now, archived_at=now)
    events = Events.objects.filter(deleted_at__isnull=True).update(deleted_at=now, archived_at=now)
    announcements = Announcement.objects.filter(archived_at__isnull=True).update(
        archived_at=Greatest(at, F("published_at")),
    )
    resources = (
        Resources.objects.filter(deleted_at__isnull=True)
        .filter(Q(shown=True) | Q(release_on__isnull=False))
        .update(shown=False, release_on=None)
    )
    return {
        "memberships": memberships,
        "groups": groups,
        "tasks": tasks,
        "events": events,
        "announcements": announcements,
        "resources": resources,
    }


def _management(actor, next_year: int, now) -> dict:
    """Start Management's year again: last year's role tasks put away, every
    email's sent progress, its dates and links cleared, last year's late
    links, extensions and releases put away, and each supervisor's late
    registration permission reset."""
    # The tasks given to everyone with a role, so the new year's don't see last year's.
    role_tasks = RoleTask.objects.filter(deleted_at__isnull=True).update(deleted_at=now, archived_at=now)
    emails = EmailSendRun.objects.exclude(key__startswith=QUEUE_KEY).update(
        started_at=None, started_by=None, finished_at=None, due=0, emailed=0, failed=0,
        error="", missed=[], connections=None,
    )
    OutcomeAnnouncement.objects.update(announcement=None, posted_at=None, posted_by=None)
    # So Resend on System Emails' Log can't send last year's misses again.
    SystemEmailLog.objects.update(missed=[])

    # The dates: last year's deadline is kept as a record but no longer in
    # force, and the new year's registration stays closed until it has dates.
    Deadline.objects.filter(is_active=True).update(is_active=False)
    window, _ = RegistrationWindow.objects.get_or_create(year=next_year)
    window.opens_at = window.closes_at = None
    window.closed_until_set = True
    window.save(update_fields=["opens_at", "closes_at", "closed_until_set"])
    ChallengeStart.objects.filter(year=next_year).update(starts_at=None)
    # Home, Groups, Events, Announcements and Resources stay hidden from
    # students, mentors and supervisors until Pages Visibility has a new date.
    pages = SupervisorPagesSetting.load()
    pages.shown_from = None
    pages.updated_by = actor if getattr(actor, "pk", None) else None
    pages.save()
    symposium = FinalistEmailSettings.load()
    symposium.symposium_date = symposium.confirm_by = symposium.slides_due = None
    symposium.registration_url = ""
    symposium.save()
    survey = ResultsEmailSettings.load()
    survey.survey_url = ""
    survey.survey_closes = None
    survey.save()

    late_links = RegistrationInvitation.objects.filter(
        revoked_at__isnull=True, used_at__isnull=True, expires_at__gt=now,
    ).update(revoked_at=now)
    extensions = GroupExtension.objects.filter(revoked_at__isnull=True).update(
        revoked_at=now, revoked_by=actor if getattr(actor, "pk", None) else None,
    )
    for release in (MarksRelease.load(), CertificatesRelease.load()):
        release.released_at = None
        release.released_by = None
        release.save(update_fields=["released_at", "released_by"])
    SupervisorProfile.objects.filter(register_after_close=True).update(register_after_close=False)
    # New finalists see the presentation times once an admin shows them.
    times = PresentationSettings.load()
    times.times_shown = False
    times.save(update_fields=["times_shown"])
    return {
        "role_tasks": role_tasks, "emails": emails, "late_links": late_links, "extensions": extensions,
    }


def start_new_year(actor, *, confirm_year) -> dict:
    """Move the platform on to the next year, once ``confirm_year`` (what
    the admin typed) is that year and nothing stops it. All or nothing: if
    any step fails, nothing changes. The new state, with what it changed."""
    with transaction.atomic():
        state = new_year_state()
        next_year = state["next_year"]
        if str(confirm_year).strip() != str(next_year):
            raise CantStart(f"Type {next_year} to confirm.")
        if state["blockers"]:
            raise CantStart(state["blockers"][0])
        try:
            with transaction.atomic():
                record = ChallengeYear.objects.create(
                    year=next_year, started_by=actor if getattr(actor, "pk", None) else None,
                )
        except IntegrityError:
            raise CantStart(f"{next_year} has already been started.") from None
        now = timezone.now()
        counts = {**_people(actor, now), **_content(now), **_management(actor, next_year, now)}
        record.counts = counts
        record.save(update_fields=["counts"])
        log_audit_event(
            actor=actor if getattr(actor, "pk", None) else None,
            entity_type="challenge_year",
            entity_id=record.pk,
            action="start",
            after_state={"year": next_year, **counts},
        )
    return new_year_state()
