"""The non-finalist email on the Email Nonfinalist tab: who it's for, a
preview, and sending it in batches. Its Symposium date and registration
link are the ones set on Notify Finalists."""
from __future__ import annotations

import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.services.email_branding import LOGO_CID, logo_data_uri

from ..models import FinalistEmailSettings
from ..permissions import IsGrader
from ..services import nonfinalist_notify

logger = logging.getLogger(__name__)


class NonFinalistEmailView(APIView):
    """GET /api/v1/grading/nonfinalists/ — this year's teams that submitted
    but weren't picked as finalists: how many teams and students have the
    email, and why sending is refused, if it is."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request):
        return Response({
            **nonfinalist_notify.nonfinalist_audience().counts(),
            "blocked": nonfinalist_notify.send_blocked_reason(FinalistEmailSettings.load()),
        })


class NonFinalistEmailPreviewView(APIView):
    """POST /api/v1/grading/nonfinalists/preview/ — the email exactly as it
    would go out, addressed to the first team due to get it."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def post(self, request):
        audience = nonfinalist_notify.nonfinalist_audience()
        pending = [t for t in audience.teams if t.id not in audience.emailed] or audience.teams
        to = pending[0].group_name if pending else "Team name"
        rendered = nonfinalist_notify.render_nonfinalist_email(to, FinalistEmailSettings.load())
        # A browser has no cid: part to resolve, so the logo goes in inline.
        html = rendered.html.replace(f"cid:{LOGO_CID}", logo_data_uri())
        return Response({"subject": rendered.subject, "to": to, "html": html})


class NonFinalistEmailSendView(APIView):
    """POST /api/v1/grading/nonfinalists/send/ — email the next few teams not
    emailed yet. The page calls it again with the returned ``cursor`` until
    ``done``. Refused until the Symposium date and link are set."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def post(self, request):
        cursor = request.data.get("cursor")
        if cursor is not None and not isinstance(cursor, int):
            return Response({"detail": "cursor must be a number"}, status=status.HTTP_400_BAD_REQUEST)
        reason = nonfinalist_notify.send_blocked_reason(FinalistEmailSettings.load())
        if reason:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = nonfinalist_notify.send_nonfinalist_batch(request.user, cursor)
        except (ConnectionError, OSError) as exc:
            logger.error("nonfinalist email: mail server unreachable error=%s", type(exc).__name__)
            return Response(
                {"detail": "Couldn't reach the mail server. Nothing more was sent; try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(result)
