"""Management > Challenge Start: the day this year's challenge starts, which
the supervisors' weekly registration status email names. Staff only."""
from __future__ import annotations

from django.utils import timezone
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import IsStaffOrAdmin
from apps.submissions.services import current_cohort

from ..models import ChallengeStart
from ..services.send_guard import person_name


def _state(row: ChallengeStart) -> dict:
    return {
        "year": row.year,
        "starts_on": row.starts_on.isoformat() if row.starts_on else None,
        "set_by": person_name(row.updated_by) if row.updated_by else "",
        "updated_at": row.updated_at,
    }


class ChallengeStartView(APIView):
    """GET this year's start date; PUT ``{"starts_on": "2026-07-27"}``, or
    null to clear it. Both answer with ``{year, starts_on, set_by,
    updated_at}``."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        return Response(_state(ChallengeStart.for_year(current_cohort())))

    def put(self, request):
        if "starts_on" not in request.data:
            raise serializers.ValidationError({"starts_on": "Give the start date, or null to clear it."})
        value = request.data.get("starts_on")
        starts_on = None
        if value not in (None, ""):
            try:
                starts_on = serializers.DateField().run_validation(value)
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({"starts_on": exc.detail}) from None
        row = ChallengeStart.for_year(current_cohort())
        row.starts_on = starts_on
        row.updated_by = request.user
        row.updated_at = timezone.now()
        row.save()
        return Response(_state(row))
