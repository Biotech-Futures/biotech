"""Results on a supervisor's portal: once marks or certificates are released,
a supervisor sees what their results email carries. That's their own
students' groups' marks, as the marks spreadsheet, and the certificates of
their students and of those groups' mentors. Only for supervisors; while
certificates are released without the finalists, a finalist group's
certificates are released separately (at the Symposium).

The same people and documents as the supervisor email (``results_notify``),
except that a finalist group still shows, its marks too: only its
certificates wait.

Admins see the same for every group that made a submission, on Management's
Results tab (the ``AllResults`` views): released or not, and nothing held
back, so they can check them before releasing.
"""
from __future__ import annotations

import io
import zipfile
from decimal import Decimal

from django.http import HttpResponse
from django.utils.http import content_disposition_header
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.filenames import safe_name
from apps.common.rbac import IsStaffOrAdmin
from apps.grading.models import FinalistFlag
from apps.grading.services.marks import grades_payload
from apps.grading.services.text import natural_key
from apps.groups.models.group_members import GroupMembership
from apps.submissions.services import current_cohort
from apps.users.models import StudentProfile, SupervisorProfile

from ..models import CertificatesRelease, MarksRelease
from ..services import results_notify
from ..services.docx import TemplateNotConfigured, marks_release_fields, marks_summary_context
from ..services.send_guard import person_name

_ROLES = GroupMembership.MembershipRoleChoices
NOT_SET_UP = "The document template has not been set up yet."
NOT_A_SUPERVISOR = "Only supervisors see their students' results."
MARKS_NOT_RELEASED = "Marks haven't been released yet."
CERTIFICATES_NOT_RELEASED = "Certificates haven't been released yet."
RELEASED_SEPARATELY = "This group's certificates will be released separately."


def _refused(request):
    """The response refusing anyone but a supervisor; None for a supervisor."""
    if SupervisorProfile.objects.filter(user_id=request.user.id).exists():
        return None
    return Response({"detail": NOT_A_SUPERVISOR}, status=status.HTTP_403_FORBIDDEN)


def release_state() -> dict:
    """What's released: marks, certificates, and whether finalists'
    certificates are held back."""
    certificates = CertificatesRelease.load()
    return {
        "marks_released": MarksRelease.load().released_at is not None,
        "certificates_released": certificates.released_at is not None,
        "exclude_finalists": certificates.exclude_finalists,
    }


class _Scope:
    """A supervisor's results this year: their students on groups that made
    a submission, those groups, by name, and each group's mentors. With no
    supervisor, every group that made a submission and all its students and
    mentors, for admins."""

    def __init__(self, year: int, exclude_finalists: bool, supervisor=None):
        self.year = year
        teams = results_notify._submitted_teams(year)
        memberships = GroupMembership.objects.filter(
            group__in=teams,
            left_at__isnull=True,
            membership_role=_ROLES.STUDENT,
        ).select_related("user", "group")
        if supervisor is not None:
            memberships = memberships.filter(
                user_id__in=StudentProfile.objects.filter(supervisor_id=supervisor.id).values("user_id")
            )
        # (student, group), by group, then name.
        self.students = sorted(
            ((m.user, m.group) for m in memberships if m.user and m.user.is_active),
            key=lambda pair: (natural_key(pair[1].group_name), person_name(pair[0]).lower()),
        )
        groups = {group.id: group for _, group in self.students}
        if supervisor is None:
            # Every group that made a submission, even one with no student now.
            groups.update({group.id: group for group in teams})
        self.groups = sorted(groups.values(), key=lambda group: natural_key(group.group_name))
        self.mentors = results_notify.team_members(self.groups, _ROLES.MENTOR)
        # Finalists' certificates come separately while certificates go out without them.
        self.withheld = (
            set(FinalistFlag.objects.filter(group__in=self.groups).values_list("group_id", flat=True))
            if exclude_finalists
            else set()
        )

    def holders(self) -> list[tuple[str, object, object]]:
        """Everyone with a certificate here, as (kind, person, group): the
        supervisor's students, then those groups' mentors, each group's by name."""
        return [
            *(("student", student, group) for student, group in self.students),
            *(("mentor", mentor, group) for group in self.groups for mentor in self.mentors.get(group.id, [])),
        ]


def _scope(request) -> _Scope:
    return _Scope(current_cohort(), CertificatesRelease.load().exclude_finalists, request.user)


def _all_scope() -> _Scope:
    """Every group's results, for admins: no certificates held back."""
    return _Scope(current_cohort(), exclude_finalists=False)


def _certificate_name(year: int, kind: str, person) -> str:
    label = "Student_Certificate" if kind == "student" else "Mentor_Certificate"
    return results_notify.file_name(year, label, person_name(person), "docx")


def _certificate(docs, kind: str, person, group) -> bytes:
    return docs.certificate(person, group) if kind == "student" else docs.mentor_certificate(person, group)


def _file(payload: bytes, filename: str, content_type: str) -> HttpResponse:
    response = HttpResponse(payload, content_type=content_type)
    response["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=filename)
    return response


def _folder(year: int, group) -> str:
    """"2026_BTF01": a group's folder in the zip, as Grading's downloads name it."""
    return f"{year}_{safe_name(group.group_name)}"


def _certificate_files(scope: "_Scope", docs) -> list:
    """Every certificate the zip holds, each in its group's folder: the
    group's students, then its mentors. Two people with one name in a group
    get "..._2.docx"; a mentor of two groups gets one in each folder."""
    files, folders = [], {}
    for group in scope.groups:
        if group.id in scope.withheld:
            continue
        folder = _folder(scope.year, group)
        # Two groups whose names make the same folder: the second is "..._2".
        count = folders[folder] = folders.get(folder, 0) + 1
        if count > 1:
            folder = f"{folder}_{count}"
        for file in results_notify._numbered([
            results_notify.ResultsFile(
                _certificate_name(scope.year, kind, person),
                results_notify.DOCX,
                lambda kind=kind, person=person, group=group: _certificate(docs, kind, person, group),
            )
            for kind, person, holder_group in scope.holders()
            if holder_group.id == group.id
        ]):
            file.name = f"{folder}/{file.name}"
            files.append(file)
    return files


def _zip_name(year: int, supervisor) -> str:
    """"2026_BTF_Certificates_Sam_Lee.zip"."""
    return results_notify.file_name(year, "Certificates", person_name(supervisor), "zip")


def _all_sheet_name(year: int) -> str:
    """"2026_BTF_Student_Marks_All_Groups.xlsx": every group's, on Management."""
    return results_notify.file_name(year, "Student_Marks", "All_Groups", "xlsx")


def _all_zip_name(year: int) -> str:
    """"2026_BTF_Certificates_All_Groups.zip"."""
    return results_notify.file_name(year, "Certificates", "All_Groups", "zip")


# The spreadsheet's mark columns: each named after its rubric criterion on hover.
_CRITERION_NAMES = {
    **{f"PM{i}": f"PosterRubric{i}" for i in range(1, 11)},
    **{f"SM{i}": f"ShortAnswerQuestionRubric{i}" for i in range(1, 5)},
}


def _columns(fields: list[dict]) -> list[dict]:
    """The spreadsheet's columns, as the page shows them: every one, empty or
    not, headed as the spreadsheet heads them, each mark with its criterion's
    name to show on hover."""
    columns = []
    for key in results_notify.MARKS_SHEET_COLUMNS:
        criterion = _CRITERION_NAMES.get(key)
        columns.append({
            "key": key,
            "label": results_notify.MARKS_SHEET_HEADINGS[key],
            "title": next((row.get(criterion) for row in fields if criterion and row.get(criterion)), "") or "",
            "mark": key in results_notify.MARKS_SHEET_MARKS,
        })
    return columns


class SupervisorResultsStateView(APIView):
    """GET /api/v1/management/supervisor-results/state/ — whether marks or
    certificates are out, so a supervisor's menu shows Results only then."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        refused = _refused(request)
        if refused:
            return refused
        state = release_state()
        return Response({
            "marks_released": state["marks_released"],
            "certificates_released": state["certificates_released"],
        })


def _mark_rows(scope: _Scope) -> list[dict]:
    """A row per group, as the spreadsheet orders them: highest total first,
    a group not marked at all last, and groups on the same total by team code."""
    rows = []
    for group in scope.groups:
        fields = marks_release_fields(marks_summary_context(group, scope.year, grades_payload(group)))
        rows.append({**results_notify._sheet_row(fields), "group_id": group.id})
    rows.sort(key=lambda row: (
        row.get("MTotal") in (None, ""),
        -Decimal(row.get("MTotal") or 0),
        natural_key(row.get("TeamCode", "")),
    ))
    return rows


def _results(scope: _Scope, *, marks: bool, certificates: bool, sheet_file_name: str, zip_file_name: str) -> dict:
    """What a Results page shows: the marks when ``marks``, the certificates
    when ``certificates``."""
    state = release_state()
    rows = _mark_rows(scope) if marks else []
    people = [
        {
            "user_id": person.id,
            "name": person_name(person),
            "kind": kind,
            "group_id": group.id,
            "group_name": group.group_name,
            "withheld": group.id in scope.withheld,
            "file_name": _certificate_name(scope.year, kind, person),
        }
        for kind, person, group in (scope.holders() if certificates else [])
    ]
    return {
        "year": scope.year,
        "marks_released": state["marks_released"],
        "certificates_released": state["certificates_released"],
        "columns": _columns(rows) if marks else [],
        "groups": [
            {key: row.get(key) for key in ("group_id", *results_notify.MARKS_SHEET_COLUMNS)} for row in rows
        ],
        "sheet_file_name": sheet_file_name if marks else "",
        "people": people,
        "zip_file_name": zip_file_name if certificates else "",
    }


def _certificate_response(scope: _Scope, group_id: int, user_id: int):
    """One person's certificate for one group in ``scope``."""
    holder = next(
        ((kind, person, group) for kind, person, group in scope.holders()
         if person.id == user_id and group.id == group_id),
        None,
    )
    if holder is None:
        return Response({"detail": "No certificate for that person here."}, status=status.HTTP_404_NOT_FOUND)
    kind, person, group = holder
    if group.id in scope.withheld:
        return Response({"detail": RELEASED_SEPARATELY}, status=status.HTTP_403_FORBIDDEN)
    try:
        payload = _certificate(results_notify.Documents(scope.year), kind, person, group)
    except TemplateNotConfigured:
        return Response({"detail": NOT_SET_UP}, status=status.HTTP_404_NOT_FOUND)
    return _file(payload, _certificate_name(scope.year, kind, person), results_notify.DOCX)


def _zip_response(scope: _Scope, filename: str):
    """Every certificate in ``scope`` in one zip, a folder per group, but
    those held back."""
    files = _certificate_files(scope, results_notify.Documents(scope.year))
    buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                archive.writestr(file.name, file.make())
    except TemplateNotConfigured:
        return Response({"detail": NOT_SET_UP}, status=status.HTTP_404_NOT_FOUND)
    return _file(buffer.getvalue(), filename, "application/zip")


class SupervisorResultsView(APIView):
    """GET /api/v1/management/supervisor-results/ — what the supervisor's
    Results page shows.

    Shape:
        {"year", "marks_released", "certificates_released",
         "columns": [{"key", "label", "title", "mark"}],   # once marks are out
         "groups": [{<the spreadsheet's fields>, "group_id"}],
         "sheet_file_name",
         "people": [{"user_id", "name", "kind": "student"|"mentor",
                     "group_id", "group_name", "withheld", "file_name"}],
                                                   # once certificates are out
         "zip_file_name"}
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        refused = _refused(request)
        if refused:
            return refused
        state = release_state()
        scope = _scope(request)
        return Response(_results(
            scope,
            marks=state["marks_released"],
            certificates=state["certificates_released"],
            sheet_file_name=results_notify.supervisor_sheet_name(scope.year, request.user),
            zip_file_name=_zip_name(scope.year, request.user),
        ))


class SupervisorResultsSheetView(APIView):
    """GET /api/v1/management/supervisor-results/marks-sheet/ — the marks
    spreadsheet, as the supervisor's results email carries it."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        refused = _refused(request)
        if refused:
            return refused
        if not release_state()["marks_released"]:
            return Response({"detail": MARKS_NOT_RELEASED}, status=status.HTTP_403_FORBIDDEN)
        scope = _scope(request)
        payload = results_notify.Documents(scope.year).marks_sheet(scope.groups)
        return _file(payload, results_notify.supervisor_sheet_name(scope.year, request.user), results_notify.XLSX)


class SupervisorResultsCertificateView(APIView):
    """GET /api/v1/management/supervisor-results/certificates/<group_id>/<user_id>/
    — one certificate: of the supervisor's student, or of a mentor of a group
    one of them is in, once certificates are released."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id: int, user_id: int):
        refused = _refused(request)
        if refused:
            return refused
        if not release_state()["certificates_released"]:
            return Response({"detail": CERTIFICATES_NOT_RELEASED}, status=status.HTTP_403_FORBIDDEN)
        return _certificate_response(_scope(request), group_id, user_id)


class SupervisorResultsCertificatesZipView(APIView):
    """GET /api/v1/management/supervisor-results/certificates/ — every
    certificate on the page in one zip, a folder per group ("2026_BTF01/"),
    but those released separately."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        refused = _refused(request)
        if refused:
            return refused
        if not release_state()["certificates_released"]:
            return Response({"detail": CERTIFICATES_NOT_RELEASED}, status=status.HTTP_403_FORBIDDEN)
        scope = _scope(request)
        return _zip_response(scope, _zip_name(scope.year, request.user))


# --- Management's Results tab: every group's, for admins ----------------------


class AllResultsView(APIView):
    """GET /api/v1/management/all-results/ — Management's Results tab: every
    group that made a submission, its marks, and its students' and mentors'
    certificates, released or not. Shaped as ``SupervisorResultsView``, with
    nothing held back (``withheld`` is always false)."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        scope = _all_scope()
        return Response(_results(
            scope,
            marks=True,
            certificates=True,
            sheet_file_name=_all_sheet_name(scope.year),
            zip_file_name=_all_zip_name(scope.year),
        ))


class AllResultsSheetView(APIView):
    """GET /api/v1/management/all-results/marks-sheet/ — every group's marks
    in one spreadsheet, laid out as a supervisor's is."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        scope = _all_scope()
        payload = results_notify.Documents(scope.year).marks_sheet(scope.groups)
        return _file(payload, _all_sheet_name(scope.year), results_notify.XLSX)


class AllResultsCertificateView(APIView):
    """GET /api/v1/management/all-results/certificates/<group_id>/<user_id>/
    — one student's or mentor's certificate for a group."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, group_id: int, user_id: int):
        return _certificate_response(_all_scope(), group_id, user_id)


class AllResultsCertificatesZipView(APIView):
    """GET /api/v1/management/all-results/certificates/ — every group's
    certificates in one zip, a folder per group ("2026_BTF01/")."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        scope = _all_scope()
        return _zip_response(scope, _all_zip_name(scope.year))
