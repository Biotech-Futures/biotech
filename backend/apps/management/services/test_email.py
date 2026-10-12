"""Test sends from the email tabs: one email, exactly as a chosen group or
supervisor on its list would get it (with its attachments), sent to any
address an admin types. Nothing is recorded as sent, and it goes even while
the email is switched off, as a test from System Emails does.

Each kind is one email: the finalist email, the two Symposium emails, and the
results emails to groups and to supervisors. Its list is every group (each
gets one email) or supervisor it can go to, so the test shows a real one's
version.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from django.contrib.auth import get_user_model

from apps.groups.models.groups import Groups
from apps.services.system_email import RenderedEmail, build_message, sender_connection, sender_for

from ..models import FinalistEmailSettings, ResultsEmailSettings
from . import results_notify, symposium_emails
from .finalist_notify import EMAIL_KEY as FINALIST_EMAIL_KEY
from .finalist_notify import render_finalist_email
from .send_guard import person_name

class TestEmailError(ValueError):
    """Why a test can't be sent, worded for the page."""


def _team_options(teams) -> list[dict]:
    """Each of ``teams`` by its name, in name order: each gets one email."""
    return [
        {"value": str(team.id), "label": team.group_name}
        for team in sorted(teams, key=lambda team: results_notify.natural_key(team.group_name))
    ]


def _team_of(value: str) -> Groups:
    return Groups.objects.get(id=int(value.split(":")[0]))


def _team_name(value: str) -> str:
    return _team_of(value).group_name


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
        return _team_options(symposium_emails.audience(email).teams)

    def render(value: str, fields: dict):
        details = FinalistEmailSettings.load()
        return symposium_emails.render_email(email, _team_of(value).group_name, details), []

    return options, render


def _results_groups_options() -> list[dict]:
    return _team_options(results_notify.results_audience().teams)


def _results_groups_render(value: str, fields: dict):
    from ..views.results import ResultsEmailSettingsSerializer

    details = _with_edits(ResultsEmailSettings, ResultsEmailSettingsSerializer, fields)
    audience = results_notify.results_audience()
    team = next((t for t in audience.teams if t.id == _team_of(value).id), None)
    if team is None:
        raise TestEmailError("That group isn't due the results email.")
    rendered = results_notify.render_team_email(team.group_name, details, audience.year)
    files = results_notify.team_files(results_notify.Documents(audience.year), audience, team)
    return rendered, files


def _results_supervisors_options() -> list[dict]:
    return [
        {"value": str(s.id), "label": person_name(s)}
        for s in sorted(
            results_notify.results_audience().supervisors,
            key=lambda s: person_name(s).lower(),
        )
    ]


def _supervisor_name(value: str) -> str:
    return person_name(get_user_model().objects.get(id=int(value)))


def _results_supervisors_render(value: str, fields: dict):
    audience = results_notify.results_audience()
    supervisor = next((s for s in audience.supervisors if str(s.id) == value), None)
    if supervisor is None:
        raise TestEmailError("That supervisor isn't due the results email.")
    rendered = results_notify.render_supervisor_email(person_name(supervisor), audience.year)
    files = results_notify.supervisor_files(results_notify.Documents(audience.year), audience, supervisor)
    return rendered, files


@dataclass(frozen=True)
class TestKind:
    options: Callable[[], list[dict]]
    render: Callable[[str, dict], tuple[RenderedEmail, list]]
    # The results emails carry files made from the Document Setup templates.
    audience: str | None = None
    # Who the email is addressed to, as its preview names them.
    addressee: Callable[[str], str] = _team_name
    # Its System Emails key: the test goes from that email's sender.
    email: str = ""


KINDS = {
    "finalist": TestKind(
        lambda: _team_options(_finalist_teams()), _finalist_render, email=FINALIST_EMAIL_KEY,
    ),
    "nonfinalists": TestKind(
        *_symposium(symposium_emails.NONFINALIST), email=symposium_emails.NONFINALIST.key,
    ),
    "nonsubmissions": TestKind(
        *_symposium(symposium_emails.NONSUBMISSION), email=symposium_emails.NONSUBMISSION.key,
    ),
    "results-groups": TestKind(
        _results_groups_options, _results_groups_render, results_notify.GROUPS,
        email=results_notify.EMAIL_KEYS[results_notify.GROUPS],
    ),
    "results-supervisors": TestKind(
        _results_supervisors_options, _results_supervisors_render, results_notify.SUPERVISORS,
        _supervisor_name, email=results_notify.EMAIL_KEYS[results_notify.SUPERVISORS],
    ),
}


def recipient_options(kind: str) -> list[dict]:
    return KINDS[kind].options()


def preview(kind: str, recipient: str, fields: dict) -> tuple[RenderedEmail, str, list[str]]:
    """``kind`` as ``recipient`` would get it, for the page's preview: the
    email, who it's addressed to, and its files' names (the files aren't
    made). Raises TestEmailError when they aren't on the list."""
    test = KINDS[kind]
    if recipient not in {option["value"] for option in test.options()}:
        raise TestEmailError("Pick one from the list.")
    rendered, planned = test.render(recipient, fields)
    return rendered, test.addressee(recipient), [f.name for f in planned]


def send_test(kind: str, recipient: str, to: str, fields: dict) -> None:
    """Send ``kind`` as ``recipient`` would get it to ``to``. Raises
    TestEmailError when it can't be made; mail errors propagate."""
    test = KINDS[kind]
    if recipient not in {option["value"] for option in test.options()}:
        raise TestEmailError("Pick one from the list.")
    if test.audience and not results_notify.templates_ready()[test.audience]:
        raise TestEmailError(results_notify.TEMPLATES_MISSING[test.audience])
    rendered, planned = test.render(recipient, fields)
    files = [(f.name, f.make(), f.mimetype) for f in planned]
    # From the email's sender, as the real one goes.
    sender = sender_for(test.email)
    message = build_message(
        rendered, to, from_email=sender.from_email, connection=sender_connection(sender), files=files,
    )
    message.send(fail_silently=False)
