"""The daily run of the guardian details email, called by a scheduler."""
import hmac

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .guardian_details import send_due


class SendGuardianDetailsRemindersView(APIView):
    """POST with the shared ``X-Reminder-Token``: email today's students with
    no guardian details. Unset ``GUARDIAN_REMINDER_TOKEN`` answers 503 rather
    than standing open."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        expected = getattr(settings, "GUARDIAN_REMINDER_TOKEN", "") or ""
        if not expected:
            return Response(
                {"detail": "Guardian details reminder trigger is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        provided = request.headers.get("X-Reminder-Token", "")
        if not hmac.compare_digest(provided, expected):
            return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(send_due(), status=status.HTTP_200_OK)
