from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.groups import Groups

from ..models import Grade, Rubric, SubmissionComponent
from ..permissions import IsGrader
from ..serializers import (
    GradeSerializer,
    RubricCriterionSerializer,
    SubmissionComponentSerializer,
)
from ..services import content


class GroupMarkingView(APIView):
    """Composite marking payload for a single group.

    Shape:
        {
          "group": {"id": ..., "group_name": ...},
          "year": 2026,
          "components": [
            {
              "component":  {...},
              "submission": {...} | null,
              "rubric_id":  <int|null>,
              "criteria":   [{...}, ...],
              "grades":     [{...}, ...],
            },
            ...
          ]
        }

    Every component block of one group shares the same submission id (a team's
    entry is one row); grades are split per block by their criterion's
    component, which is what keeps the blocks distinct.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request, group_id: int):
        group = get_object_or_404(Groups.objects.filter(deleted_at__isnull=True), pk=group_id)
        year = int(request.query_params.get("year") or date.today().year)

        components = list(SubmissionComponent.objects.all().order_by("order", "id"))
        entries_by_component = {
            e.component_id: e for e in content.submission_entries(group_id=group.id)
        }
        feedback = content.feedback_map([group.id])
        rubrics_by_component = {
            r.component_id: r
            for r in Rubric.objects.filter(year=year, active=True).prefetch_related("criteria")
        }

        grades_by_component: dict[int, list[Grade]] = {}
        submission_ids = {e.submission_id for e in entries_by_component.values()}
        if submission_ids:
            for grade in Grade.objects.filter(
                submission_id__in=submission_ids
            ).select_related("criterion__rubric"):
                grades_by_component.setdefault(
                    grade.criterion.rubric.component_id, []
                ).append(grade)

        payload_components = []
        for component in components:
            entry = entries_by_component.get(component.id)
            rubric = rubrics_by_component.get(component.id)
            criteria = list(rubric.criteria.all()) if rubric else []
            grades = grades_by_component.get(component.id, []) if entry else []

            payload_components.append({
                "component": SubmissionComponentSerializer(component).data,
                "submission": content.entry_payload(
                    entry, feedback.get((group.id, component.id), "")
                ),
                "rubric_id": rubric.id if rubric else None,
                "criteria": RubricCriterionSerializer(criteria, many=True).data,
                "grades": GradeSerializer(grades, many=True).data,
            })

        return Response({
            "group": {"id": group.id, "group_name": group.group_name},
            "year": year,
            "components": payload_components,
        })
