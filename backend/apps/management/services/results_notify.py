"""Results emails: the client's emails to groups and to supervisors once
both marks and certificates are released, sent from the Release Results tab.

Same path as the finalist email: the shared system email path, so admins can
switch them off or reword them on System Emails; one email per group, its
students and mentors in To, and one per supervisor; and replies go to the
support mailbox. They carry the documents they speak of: the group's
certificates (its students' and its mentors') and marks summary, and for
each supervisor their students' and those groups' mentors' certificates and
a spreadsheet of those groups' marks. Groups and supervisors are emailed from
separate buttons, each send queued on the server (see ``send_guard``). A
group or a supervisor is recorded as emailed only once everyone it's for has
it, so a retry reaches whoever missed it, and is skipped after that.

Who gets them, for the challenge year (``current_cohort``):

* groups that submitted, minus the finalists while certificates are released
  without them (they get theirs at the Symposium). Each group's students and
  mentors get the group email, addressed to the group, so they see each
  other's certificates; someone in several groups gets one per group;
* the supervisors of those students (``StudentProfile.supervisor``, as in the
  supervisor download) get the supervisor email, once each.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from functools import partial
from typing import Callable

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string

from apps.grading.services.marks import grades_payload
from apps.grading.services.text import natural_key
from apps.grading.services.xlsx import build_team_marks_xlsx
from apps.grading.services.zip import safe_name
from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.services.email_branding import brand_context
from apps.services.email_registry import get_email_type
from apps.services.system_email import (
    RenderedEmail,
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
    certificate_context,
    marks_release_fields,
    marks_summary_context,
    open_template,
    ordinal_suffix,
    project_title,
    render_certificate_data,
    render_marks_summary_data,
    render_mentor_certificate_data,
    sample_components,
    sample_marks_summary_context,
    signature_images,
)
from .delivery import send_each, send_group, still_due
from .finalist_notify import NOT_SET, symposium_today
from .symposium_emails import reached_ids, role_counts
from .send_guard import (
    BUILDERS,
    NOT_SENT,
    Work,
    last_missed,
    missed_people,
    person_label,
    person_name,
    queue_send,
    submissions_open_reason,
    tried_teams,
)

logger = logging.getLogger(__name__)

GROUPS = "groups"
SUPERVISORS = "supervisors"
AUDIENCES = (GROUPS, SUPERVISORS)

# Which system email each audience gets.
EMAIL_KEYS = {GROUPS: "results_team", SUPERVISORS: "results_supervisor"}

RELEASE_FIRST = "Release both marks and certificates before sending the results emails."
TEMPLATES_MISSING = {
    GROUPS: (
        "Upload the marks summary, student certificate and mentor certificate templates "
        "in Document Setup before emailing groups."
    ),
    SUPERVISORS: (
        "Upload the student certificate and mentor certificate templates "
        "in Document Setup before emailing supervisors."
    ),
}
MISSING_DETAILS = "Set the feedback survey link and close date before emailing groups."
PAST_DATE = "The survey close date can't be before today. Update it before emailing groups."

_STUDENT_ROLE = GroupMembership.MembershipRoleChoices.STUDENT
_MENTOR_ROLE = GroupMembership.MembershipRoleChoices.MENTOR

# The supervisor's marks spreadsheet: one row per group, in the marks
# summary's own field names, so the two always agree. Each mark is followed
# by its comment (PM1, PosterComment1, PM2 ...; SM1,
# ShortAnswerQuestionComment1 ...), then one total: MTotal, the Poster and
# SAQ marks together (the summary's CombinedTotal).
MARKS_SHEET_MARKS = [
    *(f"PM{i}" for i in range(1, 11)),
    *(f"SM{i}" for i in range(1, 5)),
    "MTotal",
]
MARKS_SHEET_COLUMNS = [
    "TeamCode",
    "Students",
    "Mentor",
    "ProjectTitle",
    "ProjectCategory",
    "SolutionCategory",
    *(name for i in range(1, 11) for name in (f"PM{i}", f"PosterComment{i}")),
    *(name for i in range(1, 5) for name in (f"SM{i}", f"ShortAnswerQuestionComment{i}")),
    "MTotal",
]

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _closes_text(day: date | None) -> str:
    """"30th of November", as the client's email words it."""
    if day is None:
        return NOT_SET
    return f"{day.day}{ordinal_suffix(day.day)} of {day:%B}"


# --- who gets them -------------------------------------------------------------


def team_members(teams, role) -> dict[int, list]:
    """Each team's active members in ``role``, by name: its students or its
    mentors, who its certificates are for."""
    members: dict[int, list] = {}
    memberships = GroupMembership.objects.filter(
        group__in=teams, left_at__isnull=True, membership_role=role
    ).select_related("user")
    for m in memberships:
        if m.user and m.user.is_active:
            members.setdefault(m.group_id, []).append(m.user)
    for users in members.values():
        users.sort(key=lambda user: person_name(user).lower())
    return members


@dataclass
class ResultsAudience:
    """Everyone the results emails are for this year, and who already has it."""

    year: int
    teams: list = field(default_factory=list)
    # Each group's students and mentors, and the addresses its email goes to.
    team_students: dict = field(default_factory=dict)
    team_mentors: dict = field(default_factory=dict)
    team_recipients: dict = field(default_factory=dict)
    supervisors: list = field(default_factory=list)
    # Each supervisor's students on those teams, as (student, team).
    supervisor_students: dict = field(default_factory=dict)
    teams_emailed: set = field(default_factory=set)
    supervisors_emailed: set = field(default_factory=set)

    def counts(self) -> dict:
        """Groups and supervisors due their email and emailed, and the group
        email's students and mentors (see ``role_counts``)."""
        team_ids = [team.id for team in self.teams]
        members = {
            role: {team.id: {user.id for user in by_team.get(team.id, []) if user.email} for team in self.teams}
            for role, by_team in (("students", self.team_students), ("mentors", self.team_mentors))
        }
        people = role_counts(members, team_ids, self.teams_emailed, reached_ids(EMAIL_KEYS[GROUPS], team_ids))
        return {
            GROUPS: {"total": len(self.teams), "emailed": len(self.teams_emailed)},
            SUPERVISORS: {"total": len(self.supervisors), "emailed": len(self.supervisors_emailed)},
            "people": {role: people[role] for role in ("students", "mentors")},
            # Who Resend Email To Missed Individuals would email, for each email.
            "missed": {audience: missed_count(self, audience) for audience in AUDIENCES},
        }


def _submitted_teams(year: int):
    """This year's groups that handed something in."""
    submitted = Submission.objects.filter(submitted_at__isnull=False).values("group_id")
    return Groups.objects.filter(deleted_at__isnull=True, year=year, id__in=submitted)


def results_audience(year: int | None = None) -> ResultsAudience:
    year = year or current_cohort()
    teams = _submitted_teams(year)
    if CertificatesRelease.load().exclude_finalists:
        # Their certificates come at the Symposium, so this email isn't theirs yet.
        teams = teams.exclude(finalist_flag__isnull=False)
    team_list = list(teams.order_by("id"))
    students = team_members(team_list, _STUDENT_ROLE)
    mentors = team_members(team_list, _MENTOR_ROLE)
    recipients = {
        team.id: sorted({
            user.email
            for user in students.get(team.id, []) + mentors.get(team.id, [])
            if user.email
        })
        for team in team_list
    }
    # A group with nobody to email can't be emailed; it isn't counted.
    team_list = [team for team in team_list if recipients[team.id]]

    student_team = {user.id: team for team in team_list for user in students.get(team.id, [])}
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
        pairs.sort(key=lambda pair: (natural_key(pair[1].group_name), person_name(pair[0]).lower()))
    supervisors = list(
        get_user_model()
        .objects.filter(id__in=list(supervisor_students), is_active=True)
        .exclude(email="")
        .order_by("id")
    )

    return ResultsAudience(
        year=year,
        teams=team_list,
        team_students={team.id: students.get(team.id, []) for team in team_list},
        team_mentors={team.id: mentors.get(team.id, []) for team in team_list},
        team_recipients={team.id: recipients[team.id] for team in team_list},
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
    groups and supervisors both get students' and mentors' certificates;
    groups a marks summary too, supervisors a spreadsheet, which needs no
    template."""
    grading = GradingSettings.load()
    certificates = bool(grading.certificate_template) and bool(grading.mentor_certificate_template)
    return {
        GROUPS: certificates and bool(grading.marks_summary_template),
        SUPERVISORS: certificates,
    }


def emails_on() -> dict[str, bool]:
    """Whether each audience's email is switched on in System Emails."""
    return {audience: is_email_enabled(key) for audience, key in EMAIL_KEYS.items()}


def send_blocked_reason(details: ResultsEmailSettings, audience: str) -> str:
    """Why emailing ``audience`` is refused, or "" when it may go ahead."""
    if MarksRelease.load().released_at is None or CertificatesRelease.load().released_at is None:
        return RELEASE_FIRST
    # Releasing already waits for this, but an extension granted since would not.
    open_reason = submissions_open_reason()
    if open_reason:
        return open_reason
    if not is_email_enabled(EMAIL_KEYS[audience]):
        return f"{get_email_type(EMAIL_KEYS[audience]).name} is switched off on System Emails."
    if not templates_ready()[audience]:
        return TEMPLATES_MISSING[audience]
    if audience == GROUPS:
        # Only the group email carries the survey.
        if not details.is_complete:
            return MISSING_DETAILS
        if details.survey_closes < symposium_today():
            return PAST_DATE
    return ""


# --- the emails ------------------------------------------------------------------


def team_email_context(group_name: str, details: ResultsEmailSettings, year: int) -> dict:
    """The values the group email's merge tags and template read."""
    return {
        "GROUP_NAME": group_name,
        "YEAR": str(year),
        "SURVEY_URL": details.survey_url or NOT_SET,
        "SURVEY_CLOSES": _closes_text(details.survey_closes),
    }


def supervisor_email_context(supervisor_name: str, year: int) -> dict:
    """The values the supervisor email's merge tags and template read."""
    return {"SUPERVISOR_NAME": supervisor_name, "YEAR": str(year)}


def render_team_email(group_name: str, details: ResultsEmailSettings, year: int) -> RenderedEmail:
    """The group email: an admin's saved wording if there is some,
    otherwise the client's template, with its plain-text twin."""
    context = team_email_context(group_name, details, year)
    default_text = render_to_string("emails/results_team.txt", {**brand_context(), **context})
    return render_system_email(EMAIL_KEYS[GROUPS], context, default_text=default_text)


def render_supervisor_email(supervisor_name: str, year: int) -> RenderedEmail:
    context = supervisor_email_context(supervisor_name, year)
    default_text = render_to_string("emails/results_supervisor.txt", {**brand_context(), **context})
    return render_system_email(EMAIL_KEYS[SUPERVISORS], context, default_text=default_text)


# --- the attachments ----------------------------------------------------------


@dataclass
class ResultsFile:
    """One attachment: its name, and how to make it when the email is sent."""

    name: str
    mimetype: str
    make: Callable[[], bytes]


def file_name(year: int, kind: str, name: str, extension: str) -> str:
    """As the downloads name them: "2026_BTF_Student_Certificate_Amy_Chen.docx"."""
    return f"{year}_BTF_{kind}_{safe_name(name)}.{extension}"


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

    def __init__(self, year: int, templates: dict[str, bytes] | None = None):
        self.year = year
        self._grading = GradingSettings.load()
        # ``templates`` stand in for saved ones, by settings field: a file
        # Document Setup is testing before it's saved.
        self._templates: dict[str, bytes] = dict(templates or {})
        self._images: dict | None = None

    def _template(self, field_name: str) -> bytes:
        if field_name not in self._templates:
            with open_template(getattr(self._grading, field_name)) as fh:
                self._templates[field_name] = fh.read()
        return self._templates[field_name]

    def _signatures(self) -> dict:
        if self._images is None:
            self._images = signature_images(self._grading)
        return self._images

    def certificate(self, student, team) -> bytes:
        context = certificate_context(
            person_name(student), team.group_name, self.year,
            first_name=student.first_name, last_name=student.last_name,
            project_title=project_title(team),
        )
        return render_certificate_data(self._template("certificate_template"), context, self._signatures())

    def mentor_certificate(self, mentor, team) -> bytes:
        context = certificate_context(
            person_name(mentor), team.group_name, self.year,
            first_name=mentor.first_name, last_name=mentor.last_name,
            project_title=project_title(team),
        )
        return render_mentor_certificate_data(
            self._template("mentor_certificate_template"), context, self._signatures()
        )

    def marks_summary(self, team) -> bytes:
        context = marks_summary_context(team, self.year, grades_payload(team, self.year))
        return render_marks_summary_data(self._template("marks_summary_template"), context, self._signatures())

    def marks_sheet(self, teams) -> bytes:
        """One row per group, filled exactly as its marks summary is."""
        return _marks_sheet([
            _sheet_row(marks_release_fields(
                marks_summary_context(team, self.year, grades_payload(team, self.year))
            ))
            for team in teams
        ])


def _certificates(docs: Documents, students) -> list[ResultsFile]:
    return [
        ResultsFile(
            file_name(docs.year, "Student_Certificate", person_name(student), "docx"),
            DOCX,
            lambda student=student, team=team: docs.certificate(student, team),
        )
        for student, team in students
    ]


# Made-up groups for the sample spreadsheet on Release Results.
_SAMPLE_GROUPS = (
    ("Jane Doe, John Roe, Ann Lee", "Dr Sample Mentor", "Sample Soil Sensor"),
    ("Mia Park, Noah Diaz", "Dr Second Mentor", "Sample Water Filter"),
    ("Liam Ross, Emma Hart, Jack Wong, Zoe Kim", "Ms Third Mentor", "Sample Smart Bandage"),
)


def _sheet_row(fields: dict) -> dict:
    """A group's marks summary fields as a spreadsheet row."""
    return {**fields, "MTotal": fields["CombinedTotal"]}


def _marks_sheet(rows: list[dict]) -> bytes:
    """The spreadsheet, highest MTotal first; a group not marked at all goes
    last, and groups on the same total by team code."""
    def order(row):
        total = row.get("MTotal")
        return (total in (None, ""), -Decimal(total or 0), natural_key(row.get("TeamCode", "")))

    return build_team_marks_xlsx(sorted(rows, key=order), MARKS_SHEET_COLUMNS, set(MARKS_SHEET_MARKS))


def sample_marks_sheet(year: int) -> bytes:
    """The supervisor's marks spreadsheet as it will look: made-up groups,
    marked against the real rubric's criteria and maximums, as Document
    Setup's test render fills the marks summary."""
    rows = []
    for n, (students, mentors, title) in enumerate(_SAMPLE_GROUPS, start=1):
        context = sample_marks_summary_context()
        context.update(
            # Short, like a real team code, to fit its column.
            group_name=f"SAMPLE{n}",
            project_title=title,
            students=students,
            mentors=mentors,
            components=sample_components(year, shift=n - 1),
        )
        rows.append(_sheet_row(marks_release_fields(context)))
    return _marks_sheet(rows)


def _mentor_certificates(docs: Documents, audience: ResultsAudience, teams) -> list[ResultsFile]:
    return [
        ResultsFile(
            file_name(docs.year, "Mentor_Certificate", person_name(mentor), "docx"),
            DOCX,
            lambda mentor=mentor, team=team: docs.mentor_certificate(mentor, team),
        )
        for team in teams
        for mentor in audience.team_mentors.get(team.id, [])
    ]


def team_files(docs: Documents, audience: ResultsAudience, team) -> list[ResultsFile]:
    """What the group email carries: each student's certificate, each
    mentor's certificate, then the group's marks summary. Everyone it goes to
    gets the lot, so they see each other's."""
    students = [(student, team) for student in audience.team_students.get(team.id, [])]
    return _numbered([
        *_certificates(docs, students),
        *_mentor_certificates(docs, audience, [team]),
        ResultsFile(
            file_name(docs.year, "Marks", team.group_name, "docx"),
            DOCX,
            lambda: docs.marks_summary(team),
        ),
    ])


def _supervisor_teams(audience: ResultsAudience, supervisor) -> list:
    """The groups a supervisor's students are in, once each, by name."""
    students = audience.supervisor_students.get(supervisor.id, [])
    return sorted({team.id: team for _, team in students}.values(), key=lambda t: natural_key(t.group_name))


def supervisor_sheet_name(year: int, supervisor) -> str:
    """"2026_BTF_Student_Marks_Sam_Lee.xlsx": whose spreadsheet it is."""
    return file_name(year, "Student_Marks", person_name(supervisor), "xlsx")


def supervisor_marks_sheet(audience: ResultsAudience, supervisor) -> bytes:
    """The marks spreadsheet a supervisor's email carries, on its own: for
    checking it before the emails go."""
    return Documents(audience.year).marks_sheet(_supervisor_teams(audience, supervisor))


def supervisor_files(docs: Documents, audience: ResultsAudience, supervisor) -> list[ResultsFile]:
    """What a supervisor's email carries: each of their students'
    certificates, the certificates of those groups' mentors, then one
    spreadsheet of those groups' marks, a row per group."""
    students = audience.supervisor_students.get(supervisor.id, [])
    by_name = sorted(students, key=lambda pair: person_name(pair[0]).lower())
    teams = _supervisor_teams(audience, supervisor)
    return _numbered([
        *_certificates(docs, by_name),
        *_mentor_certificates(docs, audience, teams),
        ResultsFile(supervisor_sheet_name(docs.year, supervisor), XLSX, lambda: docs.marks_sheet(teams)),
    ])


# --- Document Setup's tests with a real person --------------------------------------

_TEMPLATE_FIELDS = {
    "marks-summary": "marks_summary_template",
    "certificate": "certificate_template",
    "mentor-certificate": "mentor_certificate_template",
}


def _test_role(kind: str):
    return _MENTOR_ROLE if kind == "mentor-certificate" else _STUDENT_ROLE


def document_people(kind: str) -> list[dict]:
    """Who Document Setup can test a template with: this year's groups that
    submitted for the marks summary (it's the group's), by name; their
    students for the certificate, or their mentors for the mentor
    certificate, as "(Team) Name" options, by team."""
    teams = list(_submitted_teams(current_cohort()))
    if kind == "marks-summary":
        return [
            {"value": str(team.id), "label": team.group_name}
            for team in sorted(teams, key=lambda team: natural_key(team.group_name))
        ]
    members = team_members(teams, _test_role(kind))
    rows = sorted(
        (natural_key(team.group_name), person_name(user).lower(), f"{team.id}:{user.id}",
         f"({team.group_name}) {person_name(user)}")
        for team in teams
        for user in members.get(team.id, [])
    )
    return [{"value": value, "label": label} for *_, value, label in rows]


def document_for(kind: str, value: str, template: bytes | None = None) -> tuple[str, bytes]:
    """The document that group's or person's results email carries, from the
    saved template or ``template`` (a file picked but not saved), with its
    file name. ValueError when they aren't on ``document_people``."""
    year = current_cohort()
    field_name = _TEMPLATE_FIELDS[kind]
    docs = Documents(year, {field_name: template} if template else None)
    if kind == "marks-summary":
        team = _submitted_teams(year).filter(id=int(value)).first() if value.isdigit() else None
        if team is None:
            raise ValueError("Pick a group from the list.")
        return file_name(year, "Marks", team.group_name, "docx"), docs.marks_summary(team)
    try:
        team_id, user_id = (int(part) for part in value.split(":"))
    except ValueError:
        raise ValueError("Pick someone from the list.") from None
    team = _submitted_teams(year).filter(id=team_id).first()
    members = team_members([team], _test_role(kind)).get(team_id, []) if team else []
    person = next((user for user in members if user.id == user_id), None)
    if person is None:
        raise ValueError("That person isn't on this year's list.")
    if kind == "mentor-certificate":
        return (
            file_name(year, "Mentor_Certificate", person_name(person), "docx"),
            docs.mentor_certificate(person, team),
        )
    return (
        file_name(year, "Student_Certificate", person_name(person), "docx"),
        docs.certificate(person, team),
    )


def example_file_names(audience: str, year: int) -> list[str]:
    """The attachments' names for a preview while nobody is due the email."""
    student = file_name(year, "Student_Certificate", "Name", "docx")
    mentor = file_name(year, "Mentor_Certificate", "Name", "docx")
    if audience == GROUPS:
        return [student, mentor, file_name(year, "Marks", "Team name", "docx")]
    return [student, mentor, file_name(year, "Student_Marks", "Supervisor name", "xlsx")]


def _record(model, **fields) -> None:
    """Mark as emailed; a second sender racing this one already did it."""
    try:
        with transaction.atomic():
            model.objects.create(**fields)
    except IntegrityError:
        pass


def _send_item(
    audience: str, item, people: dict[str, str], result: ResultsAudience, details: ResultsEmailSettings, actor,
    connection, cache: dict,
) -> list[str]:
    """One group's or supervisor's email with its files, to everyone still due
    it; recorded as emailed only once everyone it goes to has it. Returns who
    it didn't reach and why, as ``people`` labels them. ``cache`` keeps the
    templates read once per worker."""
    if "docs" not in cache:
        cache["docs"] = Documents(result.year)
    docs = cache["docs"]
    recipients = list(people)
    who = f"group={item.id}" if audience == GROUPS else f"supervisor={item.id}"
    try:
        if audience == GROUPS:
            rendered = render_team_email(item.group_name, details, result.year)
            planned = team_files(docs, result, item)
        else:
            rendered = render_supervisor_email(person_name(item), result.year)
            planned = supervisor_files(docs, result, item)
        # Made once, for the one email.
        files = [(f.name, f.make(), f.mimetype) for f in planned]
    except Exception:  # noqa: BLE001
        logger.exception("results email: failed to render %s", who)
        return [{"who": label, "reason": NOT_SENT} for label in people.values()]
    # A group's one email is recorded per person, so a retry skips who has
    # it; a supervisor's email has the one address.
    if audience == GROUPS:
        # Its students and mentors alike in To.
        failed = send_group(
            rendered, recipients, connection, email=EMAIL_KEYS[GROUPS], group=item, files=files, log_as=who,
            cc_staff=False,
        )
    else:
        failed = send_each(rendered, recipients, connection, email=EMAIL_KEYS[SUPERVISORS], files=files, log_as=who)
    if failed:
        return missed_people(people, failed)
    if audience == GROUPS:
        _record(ResultsTeamEmail, group=item, sent_by=actor)
    else:
        _record(ResultsSupervisorEmail, supervisor=item, year=result.year, sent_by=actor)
    return []


def _group_people(result: ResultsAudience, team) -> dict[str, str]:
    """The group email's students and mentors: "(BTF07) Amy Chen
    (amy@example.com)"."""
    users = {u.email: u for u in result.team_students.get(team.id, []) + result.team_mentors.get(team.id, [])}
    return {
        address: person_label(team.group_name, person_name(users[address]) if address in users else None, address)
        for address in result.team_recipients.get(team.id, [])
    }


def _supervisor_people(result: ResultsAudience, supervisor) -> dict[str, str]:
    """The supervisor with their students' groups: "(BTF07, BTF12) Sam Lee
    (sam@example.com)"."""
    groups = []
    for _student, team in result.supervisor_students.get(supervisor.id, []):
        if team.group_name not in groups:
            groups.append(team.group_name)
    return {supervisor.email: person_label(", ".join(groups), person_name(supervisor), supervisor.email)}


def _named(supervisor, who: str) -> bool:
    """Whether a missed entry is ``supervisor``: "sam@x (BTF07, Sam Lee)", or
    an older run's "(BTF07) Sam Lee"."""
    return who.startswith(f"{supervisor.email} (") or (
        who.startswith("(") and who.endswith(f") {person_name(supervisor)}")
    )


def missed_items(result: ResultsAudience, audience: str) -> list:
    """The groups or supervisors not yet emailed that an earlier send missed
    someone on: what Resend Email To Missed Individuals emails."""
    if audience == GROUPS:
        pending = [t for t in result.teams if t.id not in result.teams_emailed]
        tried = tried_teams(EMAIL_KEYS[GROUPS], pending)
        return [t for t in pending if t.id in tried]
    named = last_missed(EMAIL_KEYS[SUPERVISORS])
    return [
        s for s in result.supervisors
        if s.id not in result.supervisors_emailed and any(_named(s, who) for who in named)
    ]


def missed_count(result: ResultsAudience, audience: str) -> dict:
    """How many groups or supervisors Resend Email To Missed Individuals would email,
    and the people that is."""
    items = missed_items(result, audience)
    if audience == SUPERVISORS:
        return {"count": len(items), "people": len(items)}
    people = sum(len(still_due(EMAIL_KEYS[GROUPS], t, result.team_recipients.get(t.id, []))) for t in items)
    return {"count": len(items), "people": people}


def start_send(actor, audience: str, which: str = "") -> None:
    """Queue a run emailing ``audience`` ("groups" or "supervisors") to every
    group or supervisor not yet emailed, or with ``which="missed"`` only those
    an earlier send missed (see ``send_guard.queue_send``)."""
    queue_send(EMAIL_KEYS[audience], actor, {"which": which})


def _work(audience: str, actor, options: dict) -> list[Work]:
    """A queued send of ``audience``'s email, when its turn comes: the groups
    or supervisors due then, or only those an earlier send missed."""
    details = ResultsEmailSettings.load()
    result = results_audience()
    if options.get("which") == "missed":
        pending = missed_items(result, audience)
    elif audience == GROUPS:
        pending = [t for t in result.teams if t.id not in result.teams_emailed]
    else:
        pending = [s for s in result.supervisors if s.id not in result.supervisors_emailed]
    labels = _group_people if audience == GROUPS else _supervisor_people
    work = []
    for item in pending:
        people = labels(result, item)
        if audience == GROUPS:
            # Anyone a run already reached isn't emailed again.
            due = set(still_due(EMAIL_KEYS[GROUPS], item, list(people)))
            people = {address: label for address, label in people.items() if address in due}
        work.append(Work(list(people.values()), partial(_send_item, audience, item, people, result, details, actor)))
    return work


for _audience in AUDIENCES:
    BUILDERS[EMAIL_KEYS[_audience]] = partial(_work, _audience)
