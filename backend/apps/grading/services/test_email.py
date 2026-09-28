"""Test sends from the email tabs: one email, exactly as a chosen person on
its list would get it (with its attachments), sent to any address an admin
types. Nothing is recorded as sent, and it goes even while the email is
switched off, as a test from System Emails does.

Each kind is one email: the finalist email, the two Symposium emails, and the
results emails to students and to supervisors. Its list is everyone that
email can go to, so the test shows a real team's or person's version.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from django.conf import settings

from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.services.system_email import RenderedEmail, build_message

from ..models import FinalistEmailSettings, ResultsEmailSettings
from . import results_notify, symposium_emails
from .finalist_notify import render_finalist_email

_ROLES = GroupMembership.MembershipRoleChoices
# Students first on each team, then mentors, then supervisors.
_ROLE_ORDER = {_ROLES.STUDENT: 0, _ROLES.MENTOR: 1, _ROLES.SUPERVISOR: 2}


class TestEmailError(ValueError):
    """Why a test can't be sent, worded for the page."""


def _member_options(teams, *, students_only: bool = False) -> list[dict]:
    """Everyone on ``teams`` who gets the team's email, as "(Team) Name"
    options, a team's members together; a mentor or supervisor has their
    role after the team: "(Team, mentor) Name"."""
    teams = {team.id: team for team in teams}
    memberships = GroupMembership.objects.filter(
        group_id__in=list(teams), left_at__isnull=True, user__is_active=True,
    ).exclude(user__email="").select_related("user")
    if students_only:
        memberships = memberships.filter(membership_role=_ROLES.STUDENT)
    rows = {}
    for m in memberships:
        name = results_notify._person_name(m.user)
        role = "" if m.membership_role == _ROLES.STUDENT else f", {m.membership_role}"
        team = teams[m.group_id]
        rows[f"{m.group_id}:{m.user_id}"] = (
            (team.group_name.lower(), _ROLE_ORDER.get(m.membership_role, 3), name.lower()),
            f"({team.group_name}{role}) {name}",
        )
    return [
        {"value": value, "label": label}
        for value, (_, label) in sorted(rows.items(), key=lambda item: item[1][0])
    ]


def _team_of(value: str) -> Groups:
    return Groups.objects.get(id=int(value.split(":")[0]))


def _with_edits(model, serializer_class, fields: dict):
    """The saved details with the page's unsaved edits on top, as the
    preview shows them. Nothing is saved."""
    details = model.load()
    serializer = serializer_class(details, data=fields, partial=True)
    serializer.is_valid(raise_exception=True)
    for name, value in serializer.validated_data.items():
        setattr(details, name, value)
    return details


# --- the kinds -------------------------------------------------------------------


def _finalist_teams():
    return Groups.objects.filter(deleted_at__isnull=True, finalist_flag__isnull=False)


def _finalist_render(value: str, fields: dict):
    from ..views.finalist import FinalistEmailSettingsSerializer  # the views import this module

    details = _with_edits(FinalistEmailSettings, FinalistEmailSettingsSerializer, fields)
    return render_finalist_email(_team_of(value).group_name, details), []


def _symposium(email):
    def options() -> list[dict]:
        return _member_options(symposium_emails.audience(email).teams)

    def render(value: str, fields: dict):
        details = FinalistEmailSettings.load()
        return symposium_emails.render_email(email, _team_of(value).group_name, details), []

    return options, render


def _results_students_options() -> list[dict]:
    return _member_options(results_notify.results_audience().teams, students_only=True)


def _results_students_render(value: str, fields: dict):
    from ..views.results import ResultsEmailSettingsSerializer

    details = _with_edits(ResultsEmailSettings, ResultsEmailSettingsSerializer, fields)
    audience = results_notify.results_audience()
    team = next((t for t in audience.teams if t.id == _team_of(value).id), None)
    if team is None:
        raise TestEmailError("That student's team isn't due the results email.")
    rendered = results_notify.render_team_email(team.group_name, details, audience.year)
    files = results_notify.team_files(results_notify.Documents(audience.year), audience, team)
    return rendered, files


def _results_supervisors_options() -> list[dict]:
    return [
        {"value": str(s.id), "label": results_notify._person_name(s)}
        for s in sorted(
            results_notify.results_audience().supervisors,
            key=lambda s: results_notify._person_name(s).lower(),
        )
    ]


def _results_supervisors_render(value: str, fields: dict):
    audience = results_notify.results_audience()
    supervisor = next((s for s in audience.supervisors if str(s.id) == value), None)
    if supervisor is None:
        raise TestEmailError("That supervisor isn't due the results email.")
    rendered = results_notify.render_supervisor_email(results_notify._person_name(supervisor), audience.year)
    files = results_notify.supervisor_files(results_notify.Documents(audience.year), audience, supervisor)
    return rendered, files


@dataclass(frozen=True)
class TestKind:
    options: Callable[[], list[dict]]
    render: Callable[[str, dict], tuple[RenderedEmail, list]]
    # The results emails carry files made from the Document Setup templates.
    audience: str | None = None


KINDS = {
    "finalist": TestKind(lambda: _member_options(_finalist_teams()), _finalist_render),
    "nonfinalists": TestKind(*_symposium(symposium_emails.NONFINALIST)),
    "nonsubmissions": TestKind(*_symposium(symposium_emails.NONSUBMISSION)),
    "results-students": TestKind(_results_students_options, _results_students_render, results_notify.STUDENTS),
    "results-supervisors": TestKind(
        _results_supervisors_options, _results_supervisors_render, results_notify.SUPERVISORS,
    ),
}


def recipient_options(kind: str) -> list[dict]:
    return KINDS[kind].options()


def send_test(kind: str, recipient: str, to: str, fields: dict) -> None:
    """Send ``kind`` as ``recipient`` would get it to ``to``. Raises
    TestEmailError when it can't be made; mail errors propagate."""
    test = KINDS[kind]
    if recipient not in {option["value"] for option in test.options()}:
        raise TestEmailError("Pick someone from the list.")
    if test.audience and not results_notify.templates_ready()[test.audience]:
        raise TestEmailError(results_notify.TEMPLATES_MISSING[test.audience])
    rendered, planned = test.render(recipient, fields)
    files = [(f.name, f.make(), f.mimetype) for f in planned]
    message = build_message(rendered, to, from_email=settings.DEFAULT_FROM_EMAIL, files=files)
    message.reply_to = [settings.SUPPORT_EMAIL]
    message.send(fail_silently=False)
