"""Supervisor-facing read endpoints for released marks.

Supervisors see marks for every student profile whose ``supervisor`` FK
points at their ``SupervisorProfile``. Same release gate as student reads —
before ``MarksRelease.released_at`` is set, supervisors get 403.
"""
from __future__ import annotations

from datetime import date

from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.group_members import GroupMembership
from apps.users.models import StudentProfile

from ..models import GradingJob
from ..permissions import AnythingReleased, MarksReleased
from ..services.dispatch import dispatch_job
from .student import _grades_payload


def _supervised_students(user):
    """Return StudentProfile QuerySet for students supervised by ``user``.

    Guards against non-supervisor callers (missing supervisorprofile).
    """
    profile = getattr(user, "supervisorprofile", None)
    if profile is None:
        return StudentProfile.objects.none()
    return StudentProfile.objects.filter(supervisor=profile).select_related("user")


class SupervisorGradesView(APIView):
    """GET /api/v1/grading/supervisor/students/grades/ — released marks
    aggregated across all students the requester supervises."""

    permission_classes = [permissions.IsAuthenticated, MarksReleased]

    def get(self, request):
        year = int(request.query_params.get("year") or date.today().year)
        students = _supervised_students(request.user)

        # Resolve each student's active group once; a student in no group
        # appears with `group: null` so the supervisor can chase it up.
        student_groups = {}
        student_user_ids = list(students.values_list("user_id", flat=True))
        if student_user_ids:
            memberships = (
                GroupMembership.objects.filter(
                    user_id__in=student_user_ids,
                    left_at__isnull=True,
                    membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
                )
                .select_related("group")
                .order_by("-joined_at")
            )
            for m in memberships:
                # Newest first — first membership wins per user_id.
                student_groups.setdefault(m.user_id, m.group)

        rows = []
        for sp in students:
            group = student_groups.get(sp.user_id)
            rows.append({
                "user_id": sp.user_id,
                "full_name": sp.user.get_full_name() or sp.user.email,
                "email": sp.user.email,
                "group": {"id": group.id, "group_name": group.group_name} if group else None,
                "components": _grades_payload(group, year) if group else [],
            })
        return Response({"year": year, "students": rows})


class SupervisorDownloadView(APIView):
    """POST /api/v1/grading/supervisor/download/ — kick off a zip of every
    supervised student's released documents. Reuses the M4 job infrastructure
    so the download UX is identical to the admin's bulk exports (poll
    ``/jobs/<id>/``, then stream via the Django proxy).

    Adaptive to the two release gates: marks summaries appear only once marks
    are released, certificates only once certificates are — so the bundle can
    never hand a supervisor a document students can't see yet.
    """

    permission_classes = [permissions.IsAuthenticated, AnythingReleased]

    @transaction.atomic
    def post(self, request):
        year = int(request.data.get("year") or date.today().year)
        students = _supervised_students(request.user)
        if not students.exists():
            return Response(
                {"detail": "no supervised students"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        job = GradingJob.objects.create(
            kind=GradingJob.KIND_BULK_ZIP,
            status=GradingJob.STATUS_PENDING,
            params={
                "kind": "supervisor_bundle",
                "supervisor_user_id": request.user.id,
                "year": year,
            },
            created_by=request.user,
        )
        dispatch_job(job)
        return Response({"job_id": job.id}, status=status.HTTP_202_ACCEPTED)
