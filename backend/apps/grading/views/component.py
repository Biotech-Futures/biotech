from datetime import date

from decimal import Decimal

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.groups import Groups

from ..models import Grade, Rubric, SubmissionComponent
from ..permissions import IsGrader
from ..serializers import SubmissionComponentSerializer
from ..services import content


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
             "criteria_graded": <int>,
             "last_grader_name": <str> | null,
             "grader_names": [<str>, ...]}
          ]
        }

    Sorted by group_name for predictable table ordering. Rows include groups
    with no submission yet so admins can see the full cohort's progress.

    A submission id spans every component of a group's entry, so all Grade
    queries here pin ``criterion__rubric__component`` — without it, marks
    given on other components would leak into this table.
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
        entries = {
            e.group_id: e
            for e in content.submission_entries(component_code=component.code)
        }
        # Count *scored* grades per submission (mark is not null). A Grade row
        # with a null mark exists when a comment was left but the rubric row
        # wasn't scored yet — treat that as "in progress", not "graded".
        graded_counts = {}
        mark_totals = {}
        # Grader attribution: latest-first walk over scored grades gives us both
        # the most-recent grader (first hit per submission) and the deduped list
        # (insertion order = latest-first) in a single pass.
        last_grader = {}
        graders_by_sub = {}
        submission_ids = [e.submission_id for e in entries.values()]
        if submission_ids:
            counts = (
                Grade.objects.filter(
                    submission_id__in=submission_ids,
                    mark__isnull=False,
                    criterion__rubric__component=component,
                )
                .values("submission_id")
                .annotate(cnt=Count("id"), total=Sum("mark"))
            )
            graded_counts = {row["submission_id"]: row["cnt"] for row in counts}
            # Pin to 2 dp — SQLite aggregates lose the decimal scale ("12.5").
            mark_totals = {
                row["submission_id"]: str(Decimal(row["total"]).quantize(Decimal("0.01")))
                for row in counts
            }

            grader_rows = (
                Grade.objects.filter(
                    submission_id__in=submission_ids,
                    mark__isnull=False,
                    graded_by__isnull=False,
                    criterion__rubric__component=component,
                )
                .order_by("submission_id", "-graded_at")
                .values(
                    "submission_id",
                    "graded_by__first_name",
                    "graded_by__last_name",
                )
            )
            for row in grader_rows:
                name = f'{row["graded_by__first_name"]} {row["graded_by__last_name"]}'.strip()
                if not name:
                    continue
                sid = row["submission_id"]
                last_grader.setdefault(sid, name)
                names = graders_by_sub.setdefault(sid, [])
                if name not in names:
                    names.append(name)

        rows = []
        for g in groups:
            entry = entries.get(g["id"])
            sid = entry.submission_id if entry else None
            rows.append({
                "group_id": g["id"],
                "group_name": g["group_name"],
                "submission_id": sid,
                "submitted_at": entry.submitted_at if entry else None,
                "is_late": entry.is_late if entry else False,
                "criteria_graded": graded_counts.get(sid, 0) if sid else 0,
                "marks_total": mark_totals.get(sid) if sid else None,
                "last_grader_name": last_grader.get(sid) if sid else None,
                "grader_names": graders_by_sub.get(sid, []) if sid else [],
            })

        return Response({
            "component": SubmissionComponentSerializer(component).data,
            "year": year,
            "criteria_total": criteria_total,
            "rows": rows,
        })
