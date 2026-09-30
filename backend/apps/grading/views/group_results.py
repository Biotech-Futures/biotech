"""The Results section on a group's page: the team's marks and marks summary
once marks are released, and its students' and mentors' certificates once
certificates are, as the results email carries them. For the team's
students, mentors and supervisors, and admins."""
from __future__ import annotations

from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import group_participant_qs, is_admin
from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.management.models import CertificatesRelease, MarksRelease
from apps.management.services import results_notify

from ..models import FinalistFlag
from ..services import content
from ..services.docx import (
    TemplateNotConfigured,
    _mark_text,
    _sum_marks,
    marks_release_fields,
    marks_summary_context,
)
from .student import RELEASED_PARTS, _grades_payload

_ROLES = GroupMembership.MembershipRoleChoices
NOT_SET_UP = "The document template has not been set up yet."


def _group_for(request, group_id: int):
    """The group, or the response refusing it: only its members and admins."""
    group = get_object_or_404(Groups, id=group_id, deleted_at__isnull=True)
    user = request.user
    if is_admin(user) or user.is_staff or user.is_superuser or group_participant_qs(user, group.id).exists():
        return group, None
    return None, Response({"detail": "You're not in this group."}, status=status.HTTP_403_FORBIDDEN)


def _state(group) -> dict:
    """What's out for this group: marks, certificates, and whether its
    certificates are held back (finalists, while certificates exclude them)."""
    certificates = CertificatesRelease.load()
    certificates_released = certificates.released_at is not None
    return {
        "marks_released": MarksRelease.load().released_at is not None,
        "certificates_released": certificates_released,
        "certificates_withheld": bool(
            certificates_released
            and certificates.exclude_finalists
            and FinalistFlag.objects.filter(group=group).exists()
        ),
        # Results are only for a group that made a submission.
        "has_submission": content.has_submitted(group.id),
    }


def _people(group) -> list[tuple[str, object]]:
    """The group's certificate holders: its students, then its mentors, by name."""
    return [
        (kind, user)
        for kind, role in (("student", _ROLES.STUDENT), ("mentor", _ROLES.MENTOR))
        for user in results_notify._team_members([group], role).get(group.id, [])
    ]


def _certificate_name(year: int, kind: str, user) -> str:
    label = "Student_Certificate" if kind == "student" else "Mentor_Certificate"
    return results_notify._file_name(year, label, results_notify._person_name(user), "docx")


def _docx(payload: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(payload, content_type=results_notify.DOCX)
    response["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=filename)
    return response


def _results_part(part: dict) -> dict:
    """The part as its table shows it: marks printed as the marks summary
    prints them ("8", "6.5", not "8.00"), and added up with the most they
    could be for its Subtotal row."""
    most = sum((Decimal(criterion["max_mark"]) for criterion in part["criteria"]), Decimal("0"))
    return {
        **part,
        "criteria": [
            {**criterion, "mark": _mark_text(criterion["mark"]), "max_mark": _mark_text(criterion["max_mark"])}
            for criterion in part["criteria"]
        ],
        "subtotal": _mark_text(_sum_marks(part["criteria"])),
        "subtotal_max": _mark_text(most),
    }


def _summary(group, year: int, components: list[dict], parts: list[dict]) -> dict:
    """The marks summary's own details and total, as its document fills
    them, and the most the total could be (SAQ and Poster together)."""
    fields = marks_release_fields(marks_summary_context(group, year, components))
    most = sum(Decimal(criterion["max_mark"]) for part in parts for criterion in part["criteria"])
    return {
        "project_title": fields["ProjectTitle"],
        "project_category_heading": fields["ProjectCategoryHeading"],
        "project_category": fields["ProjectCategory"],
        "solution_category": fields["SolutionCategory"],
        "combined_total": fields["CombinedTotal"],
        "combined_max": _mark_text(most),
    }


class GroupResultsView(APIView):
    """GET /api/v1/grading/groups/<id>/results/ — what the group's Results
    section shows. The page shows the section once marks or certificates
    are released.

    Shape:
        {"marks_released", "certificates_released", "certificates_withheld",
         "has_submission", "year",
         "components": [...],          # once marks are out: SAQ and Poster only,
                                       # each with "subtotal" and "subtotal_max"
         "summary": {"project_title", "project_category_heading",
                     "project_category", "solution_category",
                     "combined_total", "combined_max"} | null,
         "summary_file_name": str,     # the marks summary's download name
         "certificates": [{"user_id", "name", "kind": "student"|"mentor",
                           "file_name"}]}   # once certificates are out
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id: int):
        group, refused = _group_for(request, group_id)
        if refused:
            return refused
        state = _state(group)
        year = group.year
        shows_marks = state["marks_released"] and state["has_submission"]
        shows_certificates = (
            state["certificates_released"] and state["has_submission"] and not state["certificates_withheld"]
        )
        components = _grades_payload(group, year) if shows_marks else []
        parts = [_results_part(component) for component in components if component["code"] in RELEASED_PARTS]
        return Response({
            **state,
            "year": year,
            "components": parts,
            "summary": _summary(group, year, components, parts) if shows_marks else None,
            "summary_file_name": (
                results_notify._file_name(year, "Marks", group.group_name, "docx") if shows_marks else ""
            ),
            "certificates": [
                {
                    "user_id": user.id,
                    "name": results_notify._person_name(user),
                    "kind": kind,
                    "file_name": _certificate_name(year, kind, user),
                }
                for kind, user in (_people(group) if shows_certificates else [])
            ],
        })


class GroupResultsSummaryView(APIView):
    """GET /api/v1/grading/groups/<id>/results/summary/ — the group's marks
    summary, once marks are released."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id: int):
        group, refused = _group_for(request, group_id)
        if refused:
            return refused
        state = _state(group)
        if not (state["marks_released"] and state["has_submission"]):
            return Response({"detail": "Marks haven't been released for this group."}, status=status.HTTP_403_FORBIDDEN)
        try:
            payload = results_notify.Documents(group.year).marks_summary(group)
        except TemplateNotConfigured:
            return Response({"detail": NOT_SET_UP}, status=status.HTTP_404_NOT_FOUND)
        return _docx(payload, results_notify._file_name(group.year, "Marks", group.group_name, "docx"))


class GroupResultsCertificateView(APIView):
    """GET /api/v1/grading/groups/<id>/results/certificate/<user_id>/ — one
    of the group's students' or mentors' certificates, once certificates are
    released (and not held back for a finalist team)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id: int, user_id: int):
        group, refused = _group_for(request, group_id)
        if refused:
            return refused
        state = _state(group)
        if not (state["certificates_released"] and state["has_submission"]) or state["certificates_withheld"]:
            return Response(
                {"detail": "Certificates haven't been released for this group."}, status=status.HTTP_403_FORBIDDEN
            )
        holder = next(((kind, user) for kind, user in _people(group) if user.id == user_id), None)
        if holder is None:
            return Response({"detail": "No certificate for that person in this group."}, status=status.HTTP_404_NOT_FOUND)
        kind, user = holder
        docs = results_notify.Documents(group.year)
        try:
            payload = docs.certificate(user, group) if kind == "student" else docs.mentor_certificate(user, group)
        except TemplateNotConfigured:
            return Response({"detail": NOT_SET_UP}, status=status.HTTP_404_NOT_FOUND)
        return _docx(payload, _certificate_name(group.year, kind, user))
