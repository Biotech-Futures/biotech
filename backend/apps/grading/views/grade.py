from django.db import transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics

from ..models import ComponentFeedback, Grade, RubricCriterion
from ..permissions import IsGrader
from ..serializers import GradeBulkRequestSerializer, GradeSerializer
from ..services import content


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
                        "mark": <decimal|null>, "comment": "..."}, ...],
             "overall_comments": [{"submission": <id>, "component": "POSTER",
                                   "comment": "..."}, ...]}``

    Behavior:
      - Each item upserts a Grade against ``(submission, criterion)``. A
        submission id covers the group's whole entry, so the criterion alone
        decides which component a grade belongs to.
      - Enforces that the criterion's component actually has submitted content
        on that entry — grading an absent poster is a client bug and would
        silently corrupt data.
      - ``overall_comments`` upsert :class:`ComponentFeedback`. ``component``
        (a code) is required whenever the entry spans more than one component,
        since the submission id alone cannot say which comment this is.
      - All-or-nothing: any invalid item rolls the whole batch back.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    @transaction.atomic
    def post(self, request):
        req = GradeBulkRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)
        items = req.validated_data["items"]
        overall_comments = req.validated_data.get("overall_comments") or []

        submission_ids = {i["submission"] for i in items} | {
            o["submission"] for o in overall_comments
        }
        criterion_ids = {i["criterion"] for i in items}
        entries = content.entries_by_submission(
            content.submission_entries(submission_ids=list(submission_ids))
        ) if submission_ids else {}
        criteria = {
            c.id: c for c in RubricCriterion.objects.filter(id__in=criterion_ids).select_related("rubric")
        }

        # Validate every item before any write.
        for i, item in enumerate(items):
            sub_entries = entries.get(item["submission"])
            criterion = criteria.get(item["criterion"])
            if sub_entries is None:
                return Response(
                    {"detail": f"items[{i}]: submission {item['submission']} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if criterion is None:
                return Response(
                    {"detail": f"items[{i}]: criterion {item['criterion']} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not any(
                e.component_id == criterion.rubric.component_id for e in sub_entries
            ):
                return Response(
                    {"detail": (
                        f"items[{i}]: criterion belongs to component "
                        f"{criterion.rubric.component_id} but submission "
                        f"{item['submission']} has no submitted content for it"
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        feedback_targets = []
        for i, entry_item in enumerate(overall_comments):
            sub_entries = entries.get(entry_item["submission"])
            if sub_entries is None:
                return Response(
                    {"detail": f"overall_comments[{i}]: submission {entry_item['submission']} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            code = (entry_item.get("component") or "").strip().upper()
            if code:
                matches = [e for e in sub_entries if e.component_code == code]
                if not matches:
                    return Response(
                        {"detail": (
                            f"overall_comments[{i}]: submission has no submitted "
                            f"content for component {code!r}"
                        )},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            elif len(sub_entries) == 1:
                matches = sub_entries
            else:
                return Response(
                    {"detail": (
                        f"overall_comments[{i}]: 'component' is required — this "
                        "entry has content for more than one component"
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            feedback_targets.append((matches[0], entry_item["comment"]))

        for entry, comment in feedback_targets:
            ComponentFeedback.objects.update_or_create(
                group_id=entry.group_id,
                component_id=entry.component_id,
                defaults={"comment": comment, "updated_by": request.user},
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
