"""Management > Challenge Start: when this year's challenge starts, a date
and time, whose day the supervisors' weekly registration status email names.
Staff only."""
from __future__ import annotations

from django.utils import timezone
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import IsStaffOrAdmin
from apps.submissions.services import current_cohort

from ..models import ChallengeStart
from ..services.date_order import challenge_start_problem
from ..services.send_guard import person_name


def _state(row: ChallengeStart) -> dict:
    return {
        "year": row.year,
        "starts_at": row.starts_at.isoformat() if row.starts_at else None,
        "set_by": person_name(row.updated_by) if row.updated_by else "",
        "updated_at": row.updated_at,
    }


class ChallengeStartView(APIView):
    """GET this year's start; PUT ``{"starts_at": "2026-07-27T13:59:00Z"}``
    (a date and time), or null to clear it. Both answer with ``{year,
    starts_at, set_by, updated_at}``."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        return Response(_state(ChallengeStart.for_year(current_cohort())))

    def put(self, request):
        if "starts_at" not in request.data:
            raise serializers.ValidationError({"starts_at": "Give the start date and time, or null to clear it."})
        value = request.data.get("starts_at")
        starts_at = None
        if value not in (None, ""):
            try:
                starts_at = serializers.DateTimeField().run_validation(value)
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({"starts_at": exc.detail}) from None
        year = current_cohort()
        # After registration opens, and before submissions close.
        problem = challenge_start_problem(starts_at, year, request.user)
        if problem:
            raise serializers.ValidationError({"starts_at": problem})
        row = ChallengeStart.for_year(year)
        row.starts_at = starts_at
        row.updated_by = request.user
        row.updated_at = timezone.now()
        row.save()
        return Response(_state(row))
