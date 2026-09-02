"""Admin view of the submission deadline.

The deadline itself belongs to the submissions app (it gates the student
portal); this endpoint only lets graders/admins see and set it, going through
``services.content`` — grading's single seam onto the submissions app.
"""
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.groups import Groups

from ..permissions import IsGrader
from ..services import content


class _SetDeadlineSerializer(serializers.Serializer):
    closes_at = serializers.DateTimeField()
    # Quiet extra hours the server keeps accepting after the announced time,
    # so far-behind timezones don't lose part of their deadline day.
    grace_hours = serializers.IntegerField(min_value=0, max_value=72, default=0)


class _SetExtensionSerializer(serializers.Serializer):
    group_id = serializers.IntegerField(min_value=1)
    extended_until = serializers.DateTimeField()
    reason = serializers.CharField(allow_blank=True, required=False, default="")


class GroupExtensionListView(APIView):
    """GET/POST /api/v1/grading/deadline/extensions/

    Per-team extra time on top of the global deadline. POST upserts (one
    extension per team); the granted date is enforced exactly as entered —
    no grace hours are added on top.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request):
        return Response({"extensions": content.group_extensions()})

    def post(self, request):
        payload = _SetExtensionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        group = get_object_or_404(
            Groups.objects.filter(deleted_at__isnull=True),
            pk=payload.validated_data["group_id"],
        )
        # An "extension" earlier than the global deadline would shorten the
        # team's window — almost certainly a typo, so refuse it outright.
        deadline = content.deadline_status()
        if deadline and payload.validated_data["extended_until"] <= deadline["closes_at"]:
            return Response(
                {"detail": (
                    "The extension must be later than the current deadline "
                    f"({deadline['closes_at'].isoformat()})."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        extension = content.set_group_extension(
            group_id=group.id,
            extended_until=payload.validated_data["extended_until"],
            reason=payload.validated_data["reason"],
            granted_by=request.user,
        )
        return Response({"extension": extension})


class GroupExtensionDetailView(APIView):
    """DELETE /api/v1/grading/deadline/extensions/<group_id>/ — revoke.

    Idempotent 204 either way, so a double-click can't 500.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def delete(self, request, group_id: int):
        content.remove_group_extension(group_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
