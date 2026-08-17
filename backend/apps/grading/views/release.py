from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import MarksRelease
from ..permissions import IsGrader


class MarksReleaseView(APIView):
    """GET/POST /api/v1/grading/release/

    Singleton toggle for the "marks visible to students" gate. POST flips the
    ``released_at`` timestamp on (or off, if ``release=false`` — admins may
    need to redact in an emergency). Idempotent — re-releasing is a legitimate
    "restamp the release time" and doesn't fail.

    Every student/supervisor read view checks this row via the
    ``MarksReleased`` permission (from M1), so the entire visibility contract
    lives here.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request):
        rel = MarksRelease.load()
        return Response({
            "released_at": rel.released_at,
            "released_by": getattr(rel.released_by, "email", None) if rel.released_by_id else None,
        })

    def post(self, request):
        want_released = str(request.data.get("release", "true")).lower() != "false"
        rel = MarksRelease.load()
        if want_released:
            rel.released_at = timezone.now()
            rel.released_by = request.user
        else:
            rel.released_at = None
            rel.released_by = None
        rel.save()
        return Response({
            "released_at": rel.released_at,
            "released_by": getattr(rel.released_by, "email", None) if rel.released_by_id else None,
        })
