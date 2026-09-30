"""The Email Nonfinalist tab: the Symposium emails to teams that submitted but
weren't picked, and to teams that didn't submit. For each, who it's for, a
preview, and sending it (a run on the server). The Symposium date and registration link
are the ones set on Notify Finalists."""
from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import IsStaffOrAdmin
from apps.services.email_branding import LOGO_CID, logo_data_uri

from ..models import FinalistEmailSettings
from ..services import symposium_emails, test_email
from ..services.send_guard import AlreadySending, run_state
from ..services.symposium_emails import NONFINALIST, NONSUBMISSION


def _status(email) -> dict:
    """This year's teams due ``email``: how many teams and people have it,
    why sending is refused, if it is, and whether a run is sending it now,
    with its progress."""
    return {
        **symposium_emails.audience(email).counts(),
        "blocked": symposium_emails.send_blocked_reason(email, FinalistEmailSettings.load()),
        **run_state(email.key),
    }


class _StatusView(APIView):
    """GET — this year's teams due the email (see ``_status``)."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]
    email = NONFINALIST

    def get(self, request):
        return Response(_status(self.email))


class _PreviewView(APIView):
    """POST — the email exactly as it would go out, addressed to
    ``recipient``'s team (a person picked in Send Test Email), else the first
    team due to get it."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]
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
    """POST — start a run emailing every team due it and not yet emailed, on
    the server, so the page can be closed; returns the status with the run's
    progress. Refused until the Symposium date and link are set, while
    submissions are open, and while a run is going."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]
    email = NONFINALIST

    def post(self, request):
        reason = symposium_emails.send_blocked_reason(self.email, FinalistEmailSettings.load())
        if reason:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)
        try:
            symposium_emails.start_send(self.email, request.user)
        except AlreadySending:
            return Response(
                {"detail": symposium_emails.already_sending(self.email)}, status=status.HTTP_409_CONFLICT,
            )
        return Response(_status(self.email))


# /api/v1/management/nonfinalists/ (and preview/, send/): teams that submitted but
# weren't picked as finalists.
class NonFinalistEmailView(_StatusView):
    email = NONFINALIST


class NonFinalistEmailPreviewView(_PreviewView):
    email = NONFINALIST


class NonFinalistEmailSendView(_SendView):
    email = NONFINALIST


# /api/v1/management/nonsubmissions/ (and preview/, send/): teams that didn't submit.
class NonSubmissionEmailView(_StatusView):
    email = NONSUBMISSION


class NonSubmissionEmailPreviewView(_PreviewView):
    email = NONSUBMISSION
    test_kind = "nonsubmissions"


class NonSubmissionEmailSendView(_SendView):
    email = NONSUBMISSION
