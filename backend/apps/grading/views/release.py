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
    Releasing is refused while submissions are still open (baseline window or
    any per-team extension): marks must not go out while entries can change.
    Turning a gate OFF is always allowed.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]
    model = None  # subclasses set the singleton model

    @staticmethod
    def _blocked_while_open():
        from ..services import content

        if content.submissions_still_open():
            return Response(
                {
                    "detail": (
                        "Submissions are still open (including any extensions) — "
                        "releasing is available once the window has closed."
                    )
                },
                status=400,
            )
        return None

    @staticmethod
    def _submissions_open() -> bool:
        from ..services import content

        return content.submissions_still_open()

    def get(self, request):
        rel = self.model.load()
        return Response({
            "released_at": rel.released_at,
            "released_by": _released_by_label(rel),
            # Lets the release pages disable the button (and skip the confirm
            # dialog entirely) instead of failing the POST after the fact.
            "submissions_open": self._submissions_open(),
        })

    def post(self, request):
        want_released = str(request.data.get("release", "true")).lower() != "false"
        rel = self.model.load()
        if want_released:
            blocked = self._blocked_while_open()
            if blocked is not None:
                return blocked
            rel.released_at = timezone.now()
            rel.released_by = request.user
        else:
            rel.released_at = None
            rel.released_by = None
        rel.save()
        return Response({
            "released_at": rel.released_at,
            "released_by": _released_by_label(rel),
            "submissions_open": self._submissions_open(),
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

    Also carries ``exclude_finalists``: finalist teams receive merit
    certificates separately, so their participation certificates can stay
    locked while everyone else's are released. ``release`` only flips the gate
    when present, so the exclusion can be changed without restamping
    ``released_at``.
    """

    model = CertificatesRelease

    def _payload(self, rel):
        return {
            "released_at": rel.released_at,
            "released_by": _released_by_label(rel),
            "exclude_finalists": rel.exclude_finalists,
            "submissions_open": self._submissions_open(),
        }

    def get(self, request):
        return Response(self._payload(self.model.load()))

    def post(self, request):
        rel = self.model.load()
        # ``release`` defaults to true (matching the base view) except when the
        # request only adjusts the exclusion — that must not restamp the gate.
        if "release" in request.data or "exclude_finalists" not in request.data:
            if str(request.data.get("release", "true")).lower() != "false":
                blocked = self._blocked_while_open()
                if blocked is not None:
                    return blocked
                rel.released_at = timezone.now()
                rel.released_by = request.user
            else:
                rel.released_at = None
                rel.released_by = None
        if "exclude_finalists" in request.data:
            rel.exclude_finalists = (
                str(request.data.get("exclude_finalists")).lower() == "true"
            )
        rel.save()
        return Response(self._payload(rel))
