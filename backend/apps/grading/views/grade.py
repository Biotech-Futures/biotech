from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics

from apps.submissions.models import Submission

from ..models import Grade, RubricCriterion
from ..permissions import IsGrader
from ..serializers import GradeBulkRequestSerializer, GradeSerializer


class GradeUpdateView(generics.UpdateAPIView):
    """PATCH /api/v1/grading/grades/{id}/ — set/amend a single grade's mark or comment."""

    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [permissions.IsAuthenticated, IsGrader]
    http_method_names = ["patch"]

    def perform_update(self, serializer):
        # graded_at is auto_now, so it re-stamps on every save; graded_by we
        # set explicitly so the audit trail reflects the last mutator.
        serializer.save(graded_by=self.request.user)


class GradeBulkView(APIView):
    """POST /api/v1/grading/grades/bulk/ — upsert many grades in one round trip.

    Body: ``{"items": [{"submission": <id>, "criterion": <id>,
                        "mark": <decimal|null>, "comment": "..."}, ...]}``

    Behavior:
      - Each item upserts a Grade against ``(submission, criterion)``.
      - Enforces that the criterion's rubric.component matches the submission's
        component — a mismatched pair is a bug and would silently corrupt data.
      - All-or-nothing: any invalid item rolls the whole batch back.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    @transaction.atomic
    def post(self, request):
        req = GradeBulkRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        items = req.validated_data["items"]

        submission_ids = {i["submission"] for i in items}
        criterion_ids = {i["criterion"] for i in items}
        submissions = {
            s.id: s for s in Submission.objects.filter(id__in=submission_ids).select_related("component")
        }
        criteria = {
            c.id: c for c in RubricCriterion.objects.filter(id__in=criterion_ids).select_related("rubric")
        }

        # Validate every item before any write.
        for i, item in enumerate(items):
            submission = submissions.get(item["submission"])
            criterion = criteria.get(item["criterion"])
            if submission is None:
                return Response(
                    {"detail": f"items[{i}]: submission {item['submission']} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if criterion is None:
                return Response(
                    {"detail": f"items[{i}]: criterion {item['criterion']} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if criterion.rubric.component_id != submission.component_id:
                return Response(
                    {"detail": (
                        f"items[{i}]: criterion belongs to component "
                        f"{criterion.rubric.component_id} but submission is for "
                        f"component {submission.component_id}"
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        saved = []
        for item in items:
            grade, _ = Grade.objects.update_or_create(
                submission_id=item["submission"],
                criterion_id=item["criterion"],
                defaults={
                    "mark": item.get("mark"),
                    "comment": item.get("comment", ""),
                    "graded_by": request.user,
                },
            )
            saved.append(grade)

        return Response(GradeSerializer(saved, many=True).data)
