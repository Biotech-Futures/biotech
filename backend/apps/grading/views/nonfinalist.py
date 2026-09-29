"""The Email Nonfinalist tab: the Symposium emails to teams that submitted but
weren't picked, and to teams that didn't submit. For each, who it's for, a
preview, and sending it in batches. The Symposium date and registration link
are the ones set on Notify Finalists."""
from __future__ import annotations

import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.services.email_branding import LOGO_CID, logo_data_uri

from ..models import FinalistEmailSettings
from ..permissions import IsGrader
from ..services import symposium_emails, test_email
from ..services.symposium_emails import NONFINALIST, NONSUBMISSION

logger = logging.getLogger(__name__)


class _StatusView(APIView):
    """GET — this year's teams due the email: how many teams and students
    have it, and why sending is refused, if it is."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]
    email = NONFINALIST

    def get(self, request):
        return Response({
            **symposium_emails.audience(self.email).counts(),
            "blocked": symposium_emails.send_blocked_reason(self.email, FinalistEmailSettings.load()),
        })


class _PreviewView(APIView):
    """POST — the email exactly as it would go out, addressed to
    ``recipient``'s team (a person picked in Send Test Email), else the first
    team due to get it."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]
    email = NONFINALIST
    # Its Send Test Email list.
    test_kind = "nonfinalists"

    def post(self, request):
        recipient = request.data.get("recipient")
        if recipient:
            try:
                rendered, to, _files = test_email.preview(self.test_kind, str(recipient), request.data)
            except test_email.TestEmailError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            due = symposium_emails.audience(self.email)
            pending = [t for t in due.teams if t.id not in due.emailed] or due.teams
            to = pending[0].group_name if pending else "Team name"
            rendered = symposium_emails.render_email(self.email, to, FinalistEmailSettings.load())
        # A browser has no cid: part to resolve, so the logo goes in inline.
        html = rendered.html.replace(f"cid:{LOGO_CID}", logo_data_uri())
        return Response({"subject": rendered.subject, "to": to, "html": html})


class _SendView(APIView):
    """POST — email the next few teams not emailed yet. The page calls it
    again with the returned ``cursor`` until ``done``. Refused until the
    Symposium date and link are set."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]
    email = NONFINALIST

    def post(self, request):
        cursor = request.data.get("cursor")
        if cursor is not None and not isinstance(cursor, int):
            return Response({"detail": "cursor must be a number"}, status=status.HTTP_400_BAD_REQUEST)
        reason = symposium_emails.send_blocked_reason(self.email, FinalistEmailSettings.load())
        if reason:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = symposium_emails.send_batch(self.email, request.user, cursor)
        except (ConnectionError, OSError) as exc:
            logger.error("%s: mail server unreachable error=%s", self.email.key, type(exc).__name__)
            return Response(
                {"detail": "Couldn't reach the mail server. Nothing more was sent; try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(result)


# /api/v1/grading/nonfinalists/ (and preview/, send/): teams that submitted but
# weren't picked as finalists.
class NonFinalistEmailView(_StatusView):
    email = NONFINALIST


class NonFinalistEmailPreviewView(_PreviewView):
    email = NONFINALIST


class NonFinalistEmailSendView(_SendView):
    email = NONFINALIST


# /api/v1/grading/nonsubmissions/ (and preview/, send/): teams that didn't submit.
class NonSubmissionEmailView(_StatusView):
    email = NONSUBMISSION


class NonSubmissionEmailPreviewView(_PreviewView):
    email = NONSUBMISSION
    test_kind = "nonsubmissions"


class NonSubmissionEmailSendView(_SendView):
    email = NONSUBMISSION
