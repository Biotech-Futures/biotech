"""Results emails: the client's emails to students and to supervisors once
both marks and certificates are released, sent from the Release Results tab.

Same path as the finalist email: the shared system email path, so admins can
switch them off or reword them on System Emails; one copy per recipient; and
replies go to the support mailbox. They carry the documents they speak of:
the team's certificates and marks summary for its students, and each
supervisor's students' certificates and a spreadsheet of their marks. Students and supervisors are emailed from
separate buttons, in small batches, so each request stays short and the page
can show progress. A team (for its students) or a supervisor is recorded as
emailed only once every copy went out, so a retry reaches whoever missed it,
and is skipped after that.

Who gets them, for the challenge year (``current_cohort``):

* teams that submitted, minus the finalists while certificates are released
  without them (they get theirs at the Symposium). Each team's students get
  the team email, which is addressed to the team and speaks of "your mentor";
* the supervisors of those students (``StudentProfile.supervisor``, as in the
  supervisor download) get the supervisor email, once each.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from django.conf import settings
from django.contrib.auth import get_user_model
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
from apps.submissions.models import Submission
from apps.submissions.services import current_cohort
from apps.users.models import StudentProfile

from ..models import (
    CertificatesRelease,
    GradingSettings,
    MarksRelease,
    ResultsEmailSettings,
    ResultsSupervisorEmail,
    ResultsTeamEmail,
)
from .docx import (
    _open_template,
    _ordinal_suffix,
    certificate_context,
    marks_summary_context,
    render_certificate_data,
    render_marks_summary_data,
    signature_images,
)
from .finalist_notify import NOT_SET, symposium_today
from .xlsx import build_marks_xlsx
from .zip import _safe

logger = logging.getLogger(__name__)

STUDENTS = "students"
SUPERVISORS = "supervisors"
AUDIENCES = (STUDENTS, SUPERVISORS)

# Which system email each audience gets.
EMAIL_KEYS = {STUDENTS: "results_team", SUPERVISORS: "results_supervisor"}

# Teams or supervisors emailed per request: a few seconds of sending, so a
# request never runs long and the page can report progress between batches.
BATCH_SIZE = 5

RELEASE_FIRST = "Release both marks and certificates before sending the results emails."
TEMPLATES_MISSING = {
    STUDENTS: "Upload the certificate and marks summary templates in Document Setup before emailing students.",
    SUPERVISORS: "Upload the certificate template in Document Setup before emailing supervisors.",
}
MISSING_DETAILS = "Set the feedback survey link and close date before emailing students."
PAST_DATE = "The survey close date can't be before today. Update it before emailing students."

_STUDENT_ROLE = GroupMembership.MembershipRoleChoices.STUDENT

# The components the emails speak of, as on the marks summary.
MARKED_COMPONENTS = ("SAQ", "POSTER")

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _closes_text(day: date | None) -> str:
    """"30th of November", as the client's email words it."""
    if day is None:
        return NOT_SET
    return f"{day.day}{_ordinal_suffix(day.day)} of {day:%B}"


def _person_name(user) -> str:
    return f"{user.first_name} {user.last_name}".strip() or user.email


# --- who gets them -------------------------------------------------------------


def _team_members(teams) -> dict[int, list]:
    """Each team's active students, by name: who its certificates are for."""
    members: dict[int, list] = {}
    memberships = GroupMembership.objects.filter(
        group__in=teams, left_at__isnull=True, membership_role=_STUDENT_ROLE
    ).select_related("user")
    for m in memberships:
        if m.user and m.user.is_active:
            members.setdefault(m.group_id, []).append(m.user)
    for users in members.values():
        users.sort(key=lambda user: _person_name(user).lower())
    return members


@dataclass
class ResultsAudience:
    """Everyone the results emails are for this year, and who already has it."""

    year: int
    teams: list = field(default_factory=list)
    # Each team's students, and the addresses its email goes to.
    team_members: dict = field(default_factory=dict)
    team_students: dict = field(default_factory=dict)
    supervisors: list = field(default_factory=list)
    # Each supervisor's students on those teams, as (student, team).
    supervisor_students: dict = field(default_factory=dict)
    teams_emailed: set = field(default_factory=set)
    supervisors_emailed: set = field(default_factory=set)

    def counts(self) -> dict:
        students_total = sum(len(self.team_students[t.id]) for t in self.teams)
        students_emailed = sum(
            len(self.team_students[t.id]) for t in self.teams if t.id in self.teams_emailed
        )
        return {
            STUDENTS: {"total": students_total, "emailed": students_emailed},
            SUPERVISORS: {"total": len(self.supervisors), "emailed": len(self.supervisors_emailed)},
        }


def results_audience(year: int | None = None) -> ResultsAudience:
    year = year or current_cohort()
    submitted = Submission.objects.filter(submitted_at__isnull=False).values("group_id")
    teams = Groups.objects.filter(deleted_at__isnull=True, year=year, id__in=submitted)
    if CertificatesRelease.load().exclude_finalists:
        # Their certificates come at the Symposium, so this email isn't theirs yet.
        teams = teams.exclude(finalist_flag__isnull=False)
    team_list = list(teams.order_by("id"))
    members = _team_members(team_list)
    students = {
        team_id: sorted({user.email for user in users if user.email})
        for team_id, users in members.items()
    }
    # A team with no student to email can't be emailed; it isn't counted.
    team_list = [team for team in team_list if students.get(team.id)]

    student_team = {user.id: team for team in team_list for user in members[team.id]}
    supervisor_students: dict[int, list] = {}
    profiles = StudentProfile.objects.filter(
        user_id__in=list(student_team), supervisor__isnull=False
    ).select_related("user")
    for profile in profiles:
        # A supervisor profile's key is its user's id.
        supervisor_students.setdefault(profile.supervisor_id, []).append(
            (profile.user, student_team[profile.user_id])
        )
    for pairs in supervisor_students.values():
        pairs.sort(key=lambda pair: (pair[1].group_name.lower(), _person_name(pair[0]).lower()))
    supervisors = list(
        get_user_model()
        .objects.filter(id__in=list(supervisor_students), is_active=True)
        .exclude(email="")
        .order_by("id")
    )

    return ResultsAudience(
        year=year,
        teams=team_list,
        team_members={team.id: members[team.id] for team in team_list},
        team_students={team.id: students[team.id] for team in team_list},
        supervisors=supervisors,
        supervisor_students={s.id: supervisor_students[s.id] for s in supervisors},
        teams_emailed=set(
            ResultsTeamEmail.objects.filter(group__in=team_list).values_list("group_id", flat=True)
        ),
        supervisors_emailed=set(
            ResultsSupervisorEmail.objects.filter(year=year, supervisor__in=supervisors).values_list(
                "supervisor_id", flat=True
            )
        ),
    )


def templates_ready() -> dict[str, bool]:
    """Whether the documents each audience's email carries can be made:
    students get certificates and a marks summary, supervisors certificates
    and a spreadsheet, which needs no template."""
    grading = GradingSettings.load()
    certificate = bool(grading.certificate_template)
    return {
        STUDENTS: certificate and bool(grading.marks_summary_template),
        SUPERVISORS: certificate,
    }


def emails_on() -> dict[str, bool]:
    """Whether each audience's email is switched on in System Emails."""
    return {audience: is_email_enabled(key) for audience, key in EMAIL_KEYS.items()}


def send_blocked_reason(details: ResultsEmailSettings, audience: str) -> str:
    """Why emailing ``audience`` is refused, or "" when it may go ahead."""
    if MarksRelease.load().released_at is None or CertificatesRelease.load().released_at is None:
        return RELEASE_FIRST
    if not is_email_enabled(EMAIL_KEYS[audience]):
        return f"{get_email_type(EMAIL_KEYS[audience]).name} is switched off on System Emails."
    if not templates_ready()[audience]:
        return TEMPLATES_MISSING[audience]
    if audience == STUDENTS:
        # Only the students' email carries the survey.
        if not details.is_complete:
            return MISSING_DETAILS
        if details.survey_closes < symposium_today():
            return PAST_DATE
    return ""


# --- the emails ------------------------------------------------------------------


def render_team_email(group_name: str, details: ResultsEmailSettings, year: int) -> RenderedEmail:
    """The students' email: an admin's saved wording if there is some,
    otherwise the client's template, with its plain-text twin."""
    context = {
        "GROUP_NAME": group_name,
        "YEAR": str(year),
        "SURVEY_URL": details.survey_url or NOT_SET,
        "SURVEY_CLOSES": _closes_text(details.survey_closes),
    }
    default_text = render_to_string("emails/results_team.txt", {**brand_context(), **context})
    return render_system_email(EMAIL_KEYS[STUDENTS], context, default_text=default_text)


def render_supervisor_email(supervisor_name: str, year: int) -> RenderedEmail:
    context = {"SUPERVISOR_NAME": supervisor_name, "YEAR": str(year)}
    default_text = render_to_string("emails/results_supervisor.txt", {**brand_context(), **context})
    return render_system_email(EMAIL_KEYS[SUPERVISORS], context, default_text=default_text)


# --- the attachments ----------------------------------------------------------


@dataclass
class ResultsFile:
    """One attachment: its name, and how to make it when the email is sent."""

    name: str
    mimetype: str
    make: Callable[[], bytes]


def _file_name(year: int, kind: str, name: str, extension: str) -> str:
    """As the downloads name them: "2026_BTF_Certificate_Amy_Chen.docx"."""
    return f"{year}_BTF_{kind}_{_safe(name)}.{extension}"


def _numbered(files: list[ResultsFile]) -> list[ResultsFile]:
    """Two students with one name still get a certificate each: the second
    is "..._Amy_Chen_2.docx"."""
    seen: dict[str, int] = {}
    for file in files:
        count = seen[file.name] = seen.get(file.name, 0) + 1
        if count > 1:
            stem, _, extension = file.name.rpartition(".")
            file.name = f"{stem}_{count}.{extension}"
    return files


class Documents:
    """Makes the attachments for one batch, reading each template and the
    signatures from storage once rather than once per document."""

    def __init__(self, year: int):
        self.year = year
        self._grading = GradingSettings.load()
        self._templates: dict[str, bytes] = {}
        self._images: dict | None = None

    def _template(self, field_name: str) -> bytes:
        if field_name not in self._templates:
            with _open_template(getattr(self._grading, field_name)) as fh:
                self._templates[field_name] = fh.read()
        return self._templates[field_name]

    def _signatures(self) -> dict:
        if self._images is None:
            self._images = signature_images(self._grading)
        return self._images

    def certificate(self, student, team) -> bytes:
        context = certificate_context(
            _person_name(student), team.group_name, self.year,
            first_name=student.first_name, last_name=student.last_name,
        )
        return render_certificate_data(self._template("certificate_template"), context, self._signatures())

    def marks_summary(self, team) -> bytes:
        from ..views.student import _grades_payload  # the views import this module

        context = marks_summary_context(team, self.year, _grades_payload(team, self.year))
        return render_marks_summary_data(self._template("marks_summary_template"), context, self._signatures())

    def marks_sheet(self, students) -> bytes:
        from ..views.student import _grades_payload

        return build_marks_xlsx(
            (
                _person_name(student),
                team.group_name,
                [c for c in _grades_payload(team, self.year) if c["code"] in MARKED_COMPONENTS],
            )
            for student, team in students
        )


def _certificates(docs: Documents, students) -> list[ResultsFile]:
    return [
        ResultsFile(
            _file_name(docs.year, "Certificate", _person_name(student), "docx"),
            DOCX,
            lambda student=student, team=team: docs.certificate(student, team),
        )
        for student, team in students
    ]


def team_files(docs: Documents, audience: ResultsAudience, team) -> list[ResultsFile]:
    """What the students' email carries: every team member's certificate,
    then the team's marks summary."""
    students = [(student, team) for student in audience.team_members.get(team.id, [])]
    return _numbered([
        *_certificates(docs, students),
        ResultsFile(
            _file_name(docs.year, "Marks", team.group_name, "docx"),
            DOCX,
            lambda: docs.marks_summary(team),
        ),
    ])


def supervisor_files(docs: Documents, audience: ResultsAudience, supervisor) -> list[ResultsFile]:
    """What a supervisor's email carries: each of their students'
    certificates, then one spreadsheet of those students' Poster and SAQ
    marks."""
    students = audience.supervisor_students.get(supervisor.id, [])
    by_name = sorted(students, key=lambda pair: _person_name(pair[0]).lower())
    return _numbered([
        *_certificates(docs, by_name),
        ResultsFile(f"{docs.year}_BTF_Student_Marks.xlsx", XLSX, lambda: docs.marks_sheet(students)),
    ])


def example_file_names(audience: str, year: int) -> list[str]:
    """The attachments' names for a preview while nobody is due the email."""
    certificate = _file_name(year, "Certificate", "Student name", "docx")
    if audience == STUDENTS:
        return [certificate, _file_name(year, "Marks", "Team name", "docx")]
    return [certificate, f"{year}_BTF_Student_Marks.xlsx"]


def _send_each(rendered: RenderedEmail, recipients, connection, *, who: str, files=()) -> int:
    """One copy per address, so nobody sees the others. Returns how many went."""
    sent = 0
    for address in recipients:
        message = build_message(
            rendered, address, from_email=settings.DEFAULT_FROM_EMAIL, connection=connection,
            files=files,
        )
        # The supervisor email asks for feedback by reply: replies reach support.
        message.reply_to = [settings.SUPPORT_EMAIL]
        try:
            message.send(fail_silently=False)
        except Exception as exc:  # noqa: BLE001
            # Error type only: SMTP errors carry the recipient address.
            logger.error("results email: send failed %s error=%s", who, type(exc).__name__)
        else:
            sent += 1
    return sent


def _record(model, **fields) -> None:
    """Mark as emailed; a second sender racing this one already did it."""
    try:
        with transaction.atomic():
            model.objects.create(**fields)
    except IntegrityError:
        pass


def send_results_batch(actor, audience: str, cursor: int | None = None, *, limit: int = BATCH_SIZE) -> dict:
    """Email ``audience`` for the next ``limit`` teams (students) or
    supervisors not yet emailed.

    ``cursor`` is the last team or supervisor this run already tried, so one
    that fails is left for the next press rather than retried in a loop.
    Returns how many people were emailed, how many teams or supervisors
    failed, the new cursor, whether this run is ``done``, and the counts.
    """
    after = int(cursor or 0)
    details = ResultsEmailSettings.load()
    result = results_audience()

    if audience == STUDENTS:
        pending = [t for t in result.teams if t.id > after and t.id not in result.teams_emailed]
    else:
        pending = [s for s in result.supervisors if s.id > after and s.id not in result.supervisors_emailed]
    batch = pending[:limit]

    emailed = failed = 0
    docs = Documents(result.year)
    if batch:
        connection = get_connection(fail_silently=False)
        connection.open()
        try:
            for item in batch:
                if audience == STUDENTS:
                    recipients = result.team_students.get(item.id, [])
                    who = f"group={item.id}"
                else:
                    recipients = [item.email]
                    who = f"supervisor={item.id}"
                try:
                    if audience == STUDENTS:
                        rendered = render_team_email(item.group_name, details, result.year)
                        planned = team_files(docs, result, item)
                    else:
                        rendered = render_supervisor_email(_person_name(item), result.year)
                        planned = supervisor_files(docs, result, item)
                    # Made once: every copy carries the same files.
                    files = [(f.name, f.make(), f.mimetype) for f in planned]
                except Exception:  # noqa: BLE001
                    logger.exception("results email: failed to render %s", who)
                    failed += 1
                    continue
                sent = _send_each(rendered, recipients, connection, who=who, files=files)
                if recipients and sent == len(recipients):
                    if audience == STUDENTS:
                        _record(ResultsTeamEmail, group=item, sent_by=actor)
                    else:
                        _record(ResultsSupervisorEmail, supervisor=item, year=result.year, sent_by=actor)
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
        **results_audience(result.year).counts(),
    }
