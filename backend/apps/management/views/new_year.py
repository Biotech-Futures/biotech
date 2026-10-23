"""Management > New Year: the year in progress, and Start new year, which
moves the platform on to the next one (see ``services.new_year``). Staff only."""
from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import IsStaffOrAdmin

from ..services.new_year import CantStart, new_year_state, start_new_year


class NewYearView(APIView):
    """GET ``{year, next_year, blockers, warnings, started}``. POST
    ``{"year": 2027}``, the next year typed to confirm, starts it and answers
    with the same, ``started.counts`` saying what it changed; 400 with
    ``detail`` when it can't start."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        return Response(new_year_state())

    def post(self, request):
        try:
            state = start_new_year(request.user, confirm_year=request.data.get("year", ""))
        except CantStart as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(state)
