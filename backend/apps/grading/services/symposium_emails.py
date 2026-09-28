"""The Symposium emails to teams that won't present there, sent from the
Email Nonfinalist tab: the client's invitation for teams that submitted but
weren't picked as finalists, and their notice for teams that didn't submit.

Same path as the finalist email: the shared system email path, so admins can
switch them off or reword them on System Emails; every current member of the
team (students, mentors and supervisors) gets their own copy; and replies go
to the support mailbox. The Symposium date and registration link are the
ones set on Notify Finalists, and nothing is sent until both are set.

Teams are emailed in small batches, so each request stays short and the page
can show progress. A team is recorded as emailed only once every member got
it, so a retry reaches whoever missed it, and is skipped after that.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from django.conf import settings
from django.core.mail import get_connection
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string

from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.services.email_branding import brand_context
from apps.services.email_registry import get_email_type
from apps.services.system_email import (
    RenderedEmail,
    build_message,
    is_email_enabled,
    render_system_email,
)
from apps.submissions.emails import recipients_for
from apps.submissions.models import Submission
from apps.submissions.services import current_cohort

from ..models import FinalistEmailSettings, NonFinalistEmail, NonSubmissionEmail
from .finalist_notify import NOT_SET, _long_date, symposium_today

logger = logging.getLogger(__name__)

# Teams emailed per request: a few seconds of sending, so a request never
# runs long and the page can report progress between batches.
BATCH_SIZE = 5

MISSING_DETAILS = "Set the Symposium date and registration link on Notify Finalists before sending."
PAST_DATE = "The Symposium date on Notify Finalists is before today. Update it before sending."

_STUDENT_ROLE = GroupMembership.MembershipRoleChoices.STUDENT


def _submitted():
    return Submission.objects.filter(submitted_at__isnull=False).values("group_id")


def _nonfinalist_teams(year: int):
    """Teams that submitted but weren't picked."""
    return Groups.objects.filter(
        deleted_at__isnull=True, year=year, id__in=_submitted(), finalist_flag__isnull=True,
    )


def _nonsubmission_teams(year: int):
    """Teams that didn't submit (a saved draft doesn't count). Only teams
    with a current student: a group of just a mentor or supervisor isn't a
    team that entered."""
    with_students = GroupMembership.objects.filter(
        left_at__isnull=True, membership_role=_STUDENT_ROLE, user__is_active=True,
    ).values("group_id")
    return Groups.objects.filter(
        deleted_at__isnull=True, year=year, id__in=with_students,
    ).exclude(id__in=_submitted())


@dataclass(frozen=True)
class TeamEmail:
    """One of the two emails: its system email, template, the record of the
    teams emailed, and which of this year's teams are due it."""

    key: str
    record: type
    teams: Callable[[int], object]

    @property
    def name(self) -> str:
        return get_email_type(self.key).name


NONFINALIST = TeamEmail("nonfinalist_invitation", NonFinalistEmail, _nonfinalist_teams)
NONSUBMISSION = TeamEmail("nonsubmission_notice", NonSubmissionEmail, _nonsubmission_teams)


# --- who gets it ---------------------------------------------------------------


@dataclass
class TeamAudience:
    """Teams due an email, who on each gets it, and which teams already have
    it."""

    teams: list = field(default_factory=list)
    recipients: dict = field(default_factory=dict)
    students: dict = field(default_factory=dict)
    emailed: set = field(default_factory=set)

    def counts(self) -> dict:
        return {
            "teams": {"total": len(self.teams), "emailed": len(self.emailed)},
            "students": {
                "total": sum(self.students.get(t.id, 0) for t in self.teams),
                "emailed": sum(self.students.get(t.id, 0) for t in self.teams if t.id in self.emailed),
            },
        }


def audience(email: TeamEmail, year: int | None = None) -> TeamAudience:
    """Every current member of this year's teams due ``email`` gets it, each
    their own copy."""
    teams = list(email.teams(year or current_cohort()).order_by("id"))
    recipients = {team.id: recipients_for(team) for team in teams}
    # A team with nobody to email can't be emailed; it isn't counted.
    teams = [team for team in teams if recipients[team.id]]

    # Students with an address, for the page's count; mentors and supervisors
    # get the email too.
    students: dict[int, set] = {}
    for group_id, user_id in GroupMembership.objects.filter(
        group__in=teams,
        left_at__isnull=True,
        membership_role=_STUDENT_ROLE,
        user__is_active=True,
    ).exclude(user__email="").values_list("group_id", "user_id"):
        students.setdefault(group_id, set()).add(user_id)

    return TeamAudience(
        teams=teams,
        recipients={team.id: recipients[team.id] for team in teams},
        students={group_id: len(ids) for group_id, ids in students.items()},
        emailed=set(email.record.objects.filter(group__in=teams).values_list("group_id", flat=True)),
    )


# --- sending ---------------------------------------------------------------------


def send_blocked_reason(email: TeamEmail, details: FinalistEmailSettings) -> str:
    """Why sending ``email`` is refused, or "" when it may go ahead."""
    if not is_email_enabled(email.key):
        return f"{email.name} is switched off on System Emails."
    if not (details.symposium_date and details.registration_url):
        return MISSING_DETAILS
    if details.symposium_date < symposium_today():
        return PAST_DATE
    return ""


def render_email(email: TeamEmail, group_name: str, details: FinalistEmailSettings) -> RenderedEmail:
    """The email for one team: an admin's saved wording if there is some,
    otherwise the client's template, with its plain-text twin."""
    context = {
        "GROUP_NAME": group_name,
        "SYMPOSIUM_DATE": _long_date(details.symposium_date),
        "REGISTER_URL": details.registration_url or NOT_SET,
    }
    default_text = render_to_string(f"emails/{email.key}.txt", {**brand_context(), **context})
    return render_system_email(email.key, context, default_text=default_text)


def _send_each(rendered: RenderedEmail, recipients, connection, *, email: TeamEmail, group_id: int) -> int:
    """One copy per member, so nobody sees the others. Returns how many went."""
    sent = 0
    for address in recipients:
        message = build_message(
            rendered, address, from_email=settings.DEFAULT_FROM_EMAIL, connection=connection,
        )
        # Replies reach support, as for the finalist email.
        message.reply_to = [settings.SUPPORT_EMAIL]
        try:
            message.send(fail_silently=False)
        except Exception as exc:  # noqa: BLE001
            # Error type only: SMTP errors carry the recipient address.
            logger.error("%s: send failed group=%s error=%s", email.key, group_id, type(exc).__name__)
        else:
            sent += 1
    return sent


def send_batch(email: TeamEmail, actor, cursor: int | None = None, *, limit: int = BATCH_SIZE) -> dict:
    """Email ``email`` to the next ``limit`` teams not yet emailed.

    ``cursor`` is the last team this run already tried, so one that fails is
    left for the next press rather than retried in a loop. Returns how many
    people were emailed, how many teams failed, the new cursor, whether this
    run is ``done``, and the counts.
    """
    after = int(cursor or 0)
    details = FinalistEmailSettings.load()
    due = audience(email)
    pending = [t for t in due.teams if t.id > after and t.id not in due.emailed]
    batch = pending[:limit]

    emailed = failed = 0
    if batch:
        connection = get_connection(fail_silently=False)
        connection.open()
        try:
            for team in batch:
                recipients = due.recipients[team.id]
                try:
                    rendered = render_email(email, team.group_name, details)
                except Exception:  # noqa: BLE001
                    logger.exception("%s: failed to render group=%s", email.key, team.id)
                    failed += 1
                    continue
                sent = _send_each(rendered, recipients, connection, email=email, group_id=team.id)
                if sent == len(recipients):
                    try:
                        with transaction.atomic():
                            email.record.objects.create(group=team, sent_by=actor)
                    except IntegrityError:
                        pass  # a second sender racing this one already recorded it
                    emailed += sent
                else:
                    failed += 1
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass

    return {
        "emailed": emailed,
        "failed": failed,
        "cursor": batch[-1].id if batch else after,
        "done": len(pending) <= len(batch),
        **audience(email).counts(),
    }
