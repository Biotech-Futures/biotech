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
so the next run reaches whoever missed it, and is skipped after that. Resend
Email Those Missed emails only the people earlier runs missed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import partial
from typing import Callable

from django.db import IntegrityError, transaction
from django.template.loader import render_to_string

from apps.grading.models import FinalistFlag
from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.services.email_branding import brand_context
from apps.services.email_registry import get_email_type
from apps.services.system_email import (
    RenderedEmail,
    is_email_enabled,
    render_system_email,
)
from apps.submissions.emails import recipients_for
from apps.submissions.models import Submission
from apps.submissions.services import current_cohort

from ..models import FinalistEmailSettings, NonFinalistEmail, NonSubmissionEmail
from .delivery import already_sent, send_each, still_due
from .finalist_notify import NOT_SET, _long_date, symposium_today
from .send_guard import (
    NOT_SENT,
    Work,
    member_labels,
    missed_people,
    start_run,
    submissions_open_reason,
    tried_teams,
)

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


def reached_ids(email: str, group_ids) -> dict[int, set[int]]:
    """Each team's current members ``email`` has reached, by the address it
    went to (see ``delivery.already_sent``): ``{group_id: {user_id, ...}}``."""
    sent = already_sent(email, group_ids)
    reached: dict[int, set[int]] = {}
    rows = GroupMembership.objects.filter(group_id__in=list(sent), left_at__isnull=True).values_list(
        "group_id", "user_id", "user__email",
    )
    for group_id, user_id, address in rows:
        if address and address.lower() in sent[group_id]:
            reached.setdefault(group_id, set()).add(user_id)
    return reached


def role_counts(members: dict, team_ids, emailed_ids, reached: dict | None = None) -> dict:
    """For each role, how many people are due the email and how many have
    had it (at least once), and how many emails that is: someone on several
    teams gets one per team, so "times" can be more than the people. A
    team's members count as emailed once the team is, and before that those
    a run reached (``reached``, see ``reached_ids``).

    ``{"mentors": {"total", "emailed", "times": {"total", "emailed"}}, ...}``
    """
    team_ids = list(team_ids)
    reached = reached or {}
    counts = {}
    for key in COUNTED_ROLES:
        per_team = members.get(key, {})
        due = [per_team.get(team_id, set()) for team_id in team_ids]
        sent = [
            per_team.get(team_id, set()) if team_id in emailed_ids
            else per_team.get(team_id, set()) & reached.get(team_id, set())
            for team_id in team_ids
        ]
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
    # Members of teams not yet emailed whom a run reached (see ``reached_ids``).
    reached: dict = field(default_factory=dict)
    # Teams not yet emailed that a run missed someone on, with the addresses
    # on each still due it (see ``send_guard.tried_teams``).
    missed: dict = field(default_factory=dict)

    def counts(self) -> dict:
        """Teams, and each role's people, due the email and emailed (see
        ``role_counts``), and who Resend Email Those Missed would email."""
        return {
            "teams": {"total": len(self.teams), "emailed": len(self.emailed)},
            **role_counts(self.members, (t.id for t in self.teams), self.emailed, self.reached),
            "waiting": {"missed": {
                "teams": len(self.missed), "people": sum(len(addresses) for addresses in self.missed.values()),
            }},
        }


def audience(email: TeamEmail, year: int | None = None) -> TeamAudience:
    """Every current member of this year's teams due ``email`` gets it, each
    their own copy."""
    teams = list(email.teams(year or current_cohort()).order_by("id"))
    recipients = {team.id: recipients_for(team) for team in teams}
    # A team with nobody to email can't be emailed; it isn't counted.
    teams = [team for team in teams if recipients[team.id]]
    emailed = set(email.record.objects.filter(group__in=teams).values_list("group_id", flat=True))
    pending = [team for team in teams if team.id not in emailed]
    tried = tried_teams(email.key, pending)
    sent = already_sent(email.key, tried)

    return TeamAudience(
        teams=teams,
        recipients={team.id: recipients[team.id] for team in teams},
        # For the page's counts of students, mentors and supervisors.
        members=member_ids(team.id for team in teams),
        emailed=emailed,
        reached=reached_ids(email.key, (team.id for team in teams)),
        missed={
            team.id: [a for a in recipients[team.id] if a.lower() not in sent.get(team.id, set())]
            for team in pending
            if team.id in tried
        },
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


def _send_team(
    email: TeamEmail, team, people: dict[str, str], details: FinalistEmailSettings, actor, connection, cache: dict,
) -> list[str]:
    """One team's copies, to the members still due them; recorded as emailed
    only once every member has it. Returns who it didn't reach and why, as
    ``people`` labels them."""
    try:
        rendered = render_email(email, team.group_name, details)
    except Exception:  # noqa: BLE001
        logger.exception("%s: failed to render group=%s", email.key, team.id)
        return [{"who": who, "reason": NOT_SENT} for who in people.values()]
    failed = send_each(rendered, list(people), connection, email=email.key, group=team, log_as=f"group={team.id}")
    if failed:
        return missed_people(people, failed)
    try:
        with transaction.atomic():
            email.record.objects.create(group=team, sent_by=actor)
    except IntegrityError:
        pass  # already recorded
    return []


def start_send(email: TeamEmail, actor, *, only_missed: bool = False) -> None:
    """Start a run emailing ``email`` to every team due it and not yet
    emailed (see ``send_guard.start_run``), or with ``only_missed``, only the
    people earlier runs missed (see ``TeamAudience.missed``). Raises
    ``AlreadySending`` while a run is going."""
    details = FinalistEmailSettings.load()
    due = audience(email)
    work = []
    for team in due.teams:
        if team.id not in due.emailed and (not only_missed or team.id in due.missed):
            # Anyone a run already reached isn't emailed again.
            people = member_labels(team, still_due(email.key, team, due.recipients[team.id]))
            work.append(Work(list(people.values()), partial(_send_team, email, team, people, details, actor)))
    start_run(email.key, actor, work)
