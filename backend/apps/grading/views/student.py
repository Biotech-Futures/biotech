"""Student-facing read endpoints for released marks.

All views here are gated by the ``MarksReleased`` permission (M1). Before
``MarksRelease.released_at`` is set, students get 403 — even authenticated
ones. Once flipped, each endpoint returns only the requesting user's own
data.
"""
from __future__ import annotations

from datetime import date

from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.group_members import GroupMembership

from ..models import Grade, Rubric, SubmissionComponent
from ..permissions import MarksReleased
from ..services import content
from ..services.docx import (
    certificate_context,
    marks_summary_context,
    render_marks_summary,
    render_participation_certificate,
)


def _active_group_for(user):
    """Return the requester's active student group, or ``None``.

    Students are in exactly one group per program year (transcript said so);
    if the data ever violates that we just pick the most recent active
    membership rather than 500ing the read.
    """
    membership = (
        GroupMembership.objects.filter(
            user=user,
            left_at__isnull=True,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        .select_related("group")
        .order_by("-joined_at")
        .first()
    )
    return membership.group if membership else None


def _grades_payload(group, year: int) -> list[dict]:
    """Shape one group's marks for both JSON reads and docx rendering.

    A criterion belongs to exactly one component, so looking a grade up by
    ``(submission_id, criterion_id)`` stays exact even though every component
    of an entry shares one submission id.
    """
    components = list(SubmissionComponent.objects.order_by("order", "id"))
    entries = {
        e.component_id: e
        for e in content.submission_entries(group_id=group.id)
    }
    feedback = content.feedback_map([group.id])
    rubrics = {
        r.component_id: r
        for r in Rubric.objects.filter(year=year, active=True).prefetch_related("criteria")
    }
    grades_by_pair: dict[tuple[int, int], Grade] = {}
    submission_ids = {e.submission_id for e in entries.values()}
    if submission_ids:
        for g in Grade.objects.filter(submission_id__in=submission_ids):
            grades_by_pair[(g.submission_id, g.criterion_id)] = g

    out = []
    for component in components:
        entry = entries.get(component.id)
        rubric = rubrics.get(component.id)
        criteria = list(rubric.criteria.all()) if rubric else []
        criteria_out = []
        for c in criteria:
            grade = grades_by_pair.get((entry.submission_id, c.id)) if entry else None
            criteria_out.append({
                "name": c.name,
                "max_mark": str(c.max_mark),
                "mark": str(grade.mark) if grade and grade.mark is not None else "",
                "comment": grade.comment if grade else "",
            })
        out.append({
            "code": component.code,
            "name": component.name,
            "submitted": entry is not None,
            "overall_comment": feedback.get((group.id, component.id), ""),
            "criteria": criteria_out,
        })
    return out


class MyGradesView(APIView):
    """GET /api/v1/grading/me/grades/ — released marks for the requester's group."""

    permission_classes = [permissions.IsAuthenticated, MarksReleased]

    def get(self, request):
        group = _active_group_for(request.user)
        if group is None:
            return Response({"detail": "not a member of any group"}, status=404)
        year = int(request.query_params.get("year") or date.today().year)
        return Response({
            "group": {"id": group.id, "group_name": group.group_name},
            "year": year,
            "components": _grades_payload(group, year),
        })


class MySummaryView(APIView):
    """GET /api/v1/grading/me/summary/ — marks summary docx for the requester's group."""

    permission_classes = [permissions.IsAuthenticated, MarksReleased]

    def get(self, request):
        group = _active_group_for(request.user)
        if group is None:
            return Response({"detail": "not a member of any group"}, status=404)
        year = int(request.query_params.get("year") or date.today().year)
        components = _grades_payload(group, year)
        # Docx template iterates .criteria (see docx template) so shape mirrors JSON.
        for c in components:
            c["criteria"] = c["criteria"]  # already the shape docx expects
        payload = render_marks_summary(marks_summary_context(group, year, components))
        return _docx_response(payload, f"marks-summary-{group.id}.docx")


class MyCertificateView(APIView):
    """GET /api/v1/grading/me/certificate/ — participation certificate docx."""

    permission_classes = [permissions.IsAuthenticated, MarksReleased]

    def get(self, request):
        group = _active_group_for(request.user)
        if group is None:
            return Response({"detail": "not a member of any group"}, status=404)
        year = int(request.query_params.get("year") or date.today().year)
        student_full_name = (
            request.user.get_full_name() if hasattr(request.user, "get_full_name") else ""
        ) or request.user.email
        payload = render_participation_certificate(
            certificate_context(
                student_full_name,
                group.group_name,
                year,
                first_name=request.user.first_name,
                last_name=request.user.last_name,
            )
        )
        return _docx_response(payload, f"certificate-{group.id}.docx")


def _docx_response(payload: bytes, filename: str) -> HttpResponse:
    resp = HttpResponse(
        payload,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
