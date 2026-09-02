"""Admin view of the submission deadline.

The deadline itself belongs to the submissions app (it gates the student
portal); this endpoint only lets graders/admins see and set it, going through
``services.content`` — grading's single seam onto the submissions app.
"""
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import IsGrader
from ..services import content


class _SetDeadlineSerializer(serializers.Serializer):
    closes_at = serializers.DateTimeField()
    # Quiet extra hours the server keeps accepting after the announced time,
    # so far-behind timezones don't lose part of their deadline day.
    grace_hours = serializers.IntegerField(min_value=0, max_value=72, default=0)


class SubmissionDeadlineView(APIView):
    """GET/POST /api/v1/grading/deadline/

    GET returns the active deadline (or ``{"deadline": null}`` — submissions
    are closed until one exists). POST creates a new active deadline row; old
    rows are kept as the record, the newest wins.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request):
        return Response({"deadline": content.deadline_status()})

    def post(self, request):
        payload = _SetDeadlineSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        status = content.set_submission_deadline(
            closes_at=payload.validated_data["closes_at"],
            grace_hours=payload.validated_data["grace_hours"],
            set_by=request.user,
        )
        return Response({"deadline": status})
