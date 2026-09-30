"""The Symposium emails to teams that won't present there, sent from the
Email Nonfinalist tab: the client's invitation for teams that submitted but
weren't picked as finalists, and their notice for teams that didn't submit.

Same path as the finalist email: the shared system email path, so admins can
switch them off or reword them on System Emails; every current member of the
team (students, mentors and supervisors) gets their own copy; and replies go
to the support mailbox. The Symposium date and registration link are the
ones set on Notify Finalists, and nothing is sent until both are set.

Neither goes out while submissions are still open, the deadline's or any
team's extension, and each is sent by one request at a time (see
``send_guard``). The non-finalist invitation also waits until the finalists
have been notified, which is when the picks are settled.

Pressing Send starts a run on the server that emails every team due (see
``send_guard``). A team is recorded as emailed only once every member got it,
so the next run reaches whoever missed it, and is skipped after that.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import partial
from typing import Callable

from django.conf import settings
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string

from apps.grading.models import FinalistFlag
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
from .send_guard import Work, member_labels, start_run, submissions_open_reason

logger = logging.getLogger(__name__)

MISSING_DETAILS = "Set the Symposium date and registration link on Notify Finalists before sending."
PAST_DATE = "The Symposium date on Notify Finalists is before today. Update it before sending."
NOT_NOTIFIED = "Notify the finalists on Notify Finalists before sending this."

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
    # Whether it waits for the finalists to be notified: until then, who
    # wasn't picked isn't settled.
    after_finalists: bool = False

    @property
    def name(self) -> str:
        return get_email_type(self.key).name


NONFINALIST = TeamEmail("nonfinalist_invitation", NonFinalistEmail, _nonfinalist_teams, after_finalists=True)
NONSUBMISSION = TeamEmail("nonsubmission_notice", NonSubmissionEmail, _nonsubmission_teams)


# --- who gets it ---------------------------------------------------------------


# The members counted on the email tabs, by the key the page shows them under.
COUNTED_ROLES = {
    "students": _STUDENT_ROLE,
    "mentors": GroupMembership.MembershipRoleChoices.MENTOR,
    "supervisors": GroupMembership.MembershipRoleChoices.SUPERVISOR,
}


def member_ids(group_ids) -> dict[str, dict[int, set[int]]]:
    """Each group's current members with an address, by role:
    ``{"students": {group_id: {user_id, ...}}, "mentors": ..., "supervisors": ...}``."""
    key_of = {role: key for key, role in COUNTED_ROLES.items()}
    members: dict[str, dict[int, set[int]]] = {key: {} for key in COUNTED_ROLES}
    rows = (
        GroupMembership.objects.filter(
            group_id__in=list(group_ids),
            left_at__isnull=True,
            membership_role__in=list(key_of),
            user__is_active=True,
        )
        .exclude(user__email="")
        .values_list("group_id", "membership_role", "user_id")
    )
    for group_id, role, user_id in rows:
        members[key_of[role]].setdefault(group_id, set()).add(user_id)
    return members


def role_counts(members: dict, team_ids, emailed_ids) -> dict:
    """For each role, how many people are due the email and how many have
    had it (at least once), and how many emails that is: someone on several
    teams gets one per team, so "times" can be more than the people.

    ``{"mentors": {"total", "emailed", "times": {"total", "emailed"}}, ...}``
    """
    team_ids = list(team_ids)
    counts = {}
    for key in COUNTED_ROLES:
        per_team = members.get(key, {})
        due = [per_team.get(team_id, set()) for team_id in team_ids]
        sent = [per_team.get(team_id, set()) for team_id in team_ids if team_id in emailed_ids]
        counts[key] = {
            "total": len(set().union(*due)),
            "emailed": len(set().union(*sent)),
            "times": {"total": sum(map(len, due)), "emailed": sum(map(len, sent))},
        }
    return counts


@dataclass
class TeamAudience:
    """Teams due an email, who on each gets it, and which teams already have
    it."""

    teams: list = field(default_factory=list)
    recipients: dict = field(default_factory=dict)
    # Members with an address, by role then team (see ``member_ids``).
    members: dict = field(default_factory=dict)
    emailed: set = field(default_factory=set)

    def counts(self) -> dict:
        """Teams, and each role's people, due the email and emailed; a team's
        members count as emailed once the team is (see ``role_counts``)."""
        return {
            "teams": {"total": len(self.teams), "emailed": len(self.emailed)},
            **role_counts(self.members, (t.id for t in self.teams), self.emailed),
        }


def audience(email: TeamEmail, year: int | None = None) -> TeamAudience:
    """Every current member of this year's teams due ``email`` gets it, each
    their own copy."""
    teams = list(email.teams(year or current_cohort()).order_by("id"))
    recipients = {team.id: recipients_for(team) for team in teams}
    # A team with nobody to email can't be emailed; it isn't counted.
    teams = [team for team in teams if recipients[team.id]]

    return TeamAudience(
        teams=teams,
        recipients={team.id: recipients[team.id] for team in teams},
        # For the page's counts of students, mentors and supervisors.
        members=member_ids(team.id for team in teams),
        emailed=set(email.record.objects.filter(group__in=teams).values_list("group_id", flat=True)),
    )


# --- sending ---------------------------------------------------------------------


def already_sending(email: TeamEmail) -> str:
    return f"{email.name} is already being sent. Wait for that to finish."


def send_blocked_reason(email: TeamEmail, details: FinalistEmailSettings) -> str:
    """Why sending ``email`` is refused, or "" when it may go ahead."""
    if not is_email_enabled(email.key):
        return f"{email.name} is switched off on System Emails."
    if not (details.symposium_date and details.registration_url):
        return MISSING_DETAILS
    if details.symposium_date < symposium_today():
        return PAST_DATE
    open_reason = submissions_open_reason()
    if open_reason:
        return open_reason
    if email.after_finalists and not FinalistFlag.objects.filter(
        group__year=current_cohort(), notified=True,
    ).exists():
        return NOT_NOTIFIED
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


def _send_each(rendered: RenderedEmail, recipients, connection, *, email: TeamEmail, group_id: int) -> list[str]:
    """One copy per member, so nobody sees the others. Returns the addresses
    it couldn't reach."""
    missed = []
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
            missed.append(address)
    return missed


def _send_team(
    email: TeamEmail, team, people: dict[str, str], details: FinalistEmailSettings, actor, connection, cache: dict,
) -> list[str]:
    """One team's copies; recorded as emailed only once every member got it.
    Returns who it didn't reach, as ``people`` labels them."""
    try:
        rendered = render_email(email, team.group_name, details)
    except Exception:  # noqa: BLE001
        logger.exception("%s: failed to render group=%s", email.key, team.id)
        return list(people.values())
    missed = _send_each(rendered, list(people), connection, email=email, group_id=team.id)
    if missed:
        return [people[address] for address in missed]
    try:
        with transaction.atomic():
            email.record.objects.create(group=team, sent_by=actor)
    except IntegrityError:
        pass  # already recorded
    return []


def start_send(email: TeamEmail, actor) -> None:
    """Start a run emailing ``email`` to every team due it and not yet
    emailed (see ``send_guard.start_run``). Raises ``AlreadySending`` while a
    run is going."""
    details = FinalistEmailSettings.load()
    due = audience(email)
    work = []
    for team in due.teams:
        if team.id not in due.emailed:
            people = member_labels(team, due.recipients[team.id])
            work.append(Work(list(people.values()), partial(_send_team, email, team, people, details, actor)))
    start_run(email.key, actor, work)
