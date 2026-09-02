from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import CertificatesRelease, MarksRelease
from ..permissions import IsGrader


def _released_by_label(rel):
    if not rel.released_by_id:
        return None
    user = rel.released_by
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.email


class _SingletonReleaseView(APIView):
    """Shared GET/POST toggle behavior for singleton release gates.

    POST flips ``released_at`` on (or off with ``release=false`` — admins may
    need to redact in an emergency). Idempotent — re-releasing restamps.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]
    model = None  # subclasses set the singleton model

    def get(self, request):
        rel = self.model.load()
        return Response({
            "released_at": rel.released_at,
            "released_by": _released_by_label(rel),
        })

    def post(self, request):
        want_released = str(request.data.get("release", "true")).lower() != "false"
        rel = self.model.load()
        if want_released:
            rel.released_at = timezone.now()
            rel.released_by = request.user
        else:
            rel.released_at = None
            rel.released_by = None
        rel.save()
        return Response({
            "released_at": rel.released_at,
            "released_by": _released_by_label(rel),
        })


class MarksReleaseView(_SingletonReleaseView):
    """GET/POST /api/v1/grading/release/ — the "marks visible" gate.

    Every student/supervisor read view checks this row via the
    ``MarksReleased`` permission, so the entire visibility contract lives here.
    """

    model = MarksRelease


class CertificatesReleaseView(_SingletonReleaseView):
    """GET/POST /api/v1/grading/certificates-release/ — certificate gate.

    Separate from marks so certificates can go out on a different day (e.g. at
    the ceremony) than the grades. Checked by ``CertificatesReleased``.
    """

    model = CertificatesRelease
