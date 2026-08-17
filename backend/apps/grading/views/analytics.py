"""Analytics endpoint (M9) — Team 4 consumes this for dashboards.

Same permission gate as the marking views (``IsGrader``) since the output
includes unreleased marks. No pagination — the whole cohort fits in a single
JSON payload at capstone scale.
"""
from __future__ import annotations

from datetime import date

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from ..permissions import IsGrader
from ..services.analytics import (
    DEFAULT_HISTOGRAM_BUCKETS,
    DEFAULT_TOP_N,
    compute_component_analytics,
)


class ComponentAnalyticsView(APIView):
    """GET /api/v1/grading/components/<code>/analytics/?year=YYYY&top=N&buckets=N

    Returns aggregate stats for a component (see ``services/analytics.py``
    for the payload shape). Query params:

      * ``year`` — defaults to the current year.
      * ``top``  — number of leaderboard rows; default 10, clamps at 100.
      * ``buckets`` — histogram bucket count; default 10, clamps at 50.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request, code: str):
        year = int(request.query_params.get("year") or date.today().year)
        top = min(int(request.query_params.get("top") or DEFAULT_TOP_N), 100)
        buckets = min(int(request.query_params.get("buckets") or DEFAULT_HISTOGRAM_BUCKETS), 50)
        return Response(
            compute_component_analytics(code, year, top=top, buckets=buckets)
        )
