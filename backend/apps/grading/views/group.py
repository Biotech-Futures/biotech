from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.groups import Groups
from apps.submissions.models import Submission, SubmissionComponent

from ..models import Grade, Rubric
from ..permissions import IsGrader
from ..serializers import (
    GradeSerializer,
    RubricCriterionSerializer,
    SubmissionComponentSerializer,
    SubmissionSerializer,
)


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
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request, group_id: int):
        group = get_object_or_404(Groups.objects.filter(deleted_at__isnull=True), pk=group_id)
        year = int(request.query_params.get("year") or date.today().year)

        components = list(SubmissionComponent.objects.all().order_by("order", "id"))
        submissions_by_component = {
            s.component_id: s
            for s in Submission.objects.filter(group=group).select_related("component")
        }
        rubrics_by_component = {
            r.component_id: r
            for r in Rubric.objects.filter(year=year, active=True).prefetch_related("criteria")
        }
        grades_by_submission = {}
        submission_ids = [s.id for s in submissions_by_component.values()]
        if submission_ids:
            for grade in Grade.objects.filter(submission_id__in=submission_ids):
                grades_by_submission.setdefault(grade.submission_id, []).append(grade)

        payload_components = []
        for component in components:
            submission = submissions_by_component.get(component.id)
            rubric = rubrics_by_component.get(component.id)
            criteria = list(rubric.criteria.all()) if rubric else []
            grades = grades_by_submission.get(submission.id, []) if submission else []

            payload_components.append({
                "component": SubmissionComponentSerializer(component).data,
                "submission": SubmissionSerializer(submission).data if submission else None,
                "rubric_id": rubric.id if rubric else None,
                "criteria": RubricCriterionSerializer(criteria, many=True).data,
                "grades": GradeSerializer(grades, many=True).data,
            })

        return Response({
            "group": {"id": group.id, "group_name": group.group_name},
            "year": year,
            "components": payload_components,
        })
