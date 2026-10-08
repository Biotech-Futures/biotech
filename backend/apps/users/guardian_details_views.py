"""The daily guardian emails, called by a scheduler: the details email to
students, and the consent form reminder to guardians."""
import hmac

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import guardian_details, guardian_reminders


def _refused(request):
    """Why the shared ``X-Reminder-Token`` doesn't let this run; None when it
    does. Unset ``GUARDIAN_REMINDER_TOKEN`` answers 503 rather than standing
    open."""
    expected = getattr(settings, "GUARDIAN_REMINDER_TOKEN", "") or ""
    if not expected:
        return Response(
            {"detail": "Guardian reminder trigger is not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if not hmac.compare_digest(request.headers.get("X-Reminder-Token", ""), expected):
        return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)
    return None


class SendGuardianDetailsRemindersView(APIView):
    """POST with the token: email today's students with no guardian details."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        return _refused(request) or Response(guardian_details.send_due(), status=status.HTTP_200_OK)


class SendGuardianConsentRemindersView(APIView):
    """POST with the token: email the consent form to today's guardians who
    haven't signed."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        return _refused(request) or Response(guardian_reminders.send_due(), status=status.HTTP_200_OK)
