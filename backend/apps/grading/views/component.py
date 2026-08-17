from datetime import date

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.groups import Groups
from apps.submissions.models import Submission, SubmissionComponent

from ..models import Grade, Rubric
from ..permissions import IsGrader
from ..serializers import SubmissionComponentSerializer


class ComponentMarkingListView(APIView):
    """Table of every group's status for a single component.

    Shape:
        {
          "component": {...},
          "year": 2026,
          "criteria_total": 3,
          "rows": [
            {"group_id", "group_name",
             "submission_id" | null, "submitted_at" | null, "is_late",
             "criteria_graded": <int>}
          ]
        }

    Sorted by group_name for predictable table ordering. Rows include groups
    with no submission yet so admins can see the full cohort's progress.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request, code: str):
        component = get_object_or_404(SubmissionComponent, code=code)
        year = int(request.query_params.get("year") or date.today().year)

        rubric = Rubric.objects.filter(component=component, year=year, active=True).first()
        criteria_total = rubric.criteria.count() if rubric else 0

        groups = list(
            Groups.objects.filter(deleted_at__isnull=True)
            .order_by("group_name")
            .values("id", "group_name")
        )
        submissions = {
            s["group_id"]: s
            for s in Submission.objects.filter(component=component).values(
                "id", "group_id", "submitted_at", "is_late"
            )
        }
        # Count *scored* grades per submission (mark is not null). A Grade row
        # with a null mark exists when a comment was left but the rubric row
        # wasn't scored yet — treat that as "in progress", not "graded".
        graded_counts = {}
        submission_ids = [s["id"] for s in submissions.values()]
        if submission_ids:
            counts = (
                Grade.objects.filter(submission_id__in=submission_ids, mark__isnull=False)
                .values("submission_id")
                .annotate(cnt=Count("id"))
            )
            graded_counts = {row["submission_id"]: row["cnt"] for row in counts}

        rows = []
        for g in groups:
            submission = submissions.get(g["id"])
            rows.append({
                "group_id": g["id"],
                "group_name": g["group_name"],
                "submission_id": submission["id"] if submission else None,
                "submitted_at": submission["submitted_at"] if submission else None,
                "is_late": submission["is_late"] if submission else False,
                "criteria_graded": graded_counts.get(submission["id"], 0) if submission else 0,
            })

        return Response({
            "component": SubmissionComponentSerializer(component).data,
            "year": year,
            "criteria_total": criteria_total,
            "rows": rows,
        })
