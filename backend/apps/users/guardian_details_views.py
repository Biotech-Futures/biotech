"""The daily guardian emails, called by a scheduler: the details email to
students, and the consent form reminder to guardians."""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common import email_jobs

from . import guardian_details, guardian_reminders


class SendGuardianDetailsRemindersView(APIView):
    """POST with the email jobs' token: email today's students with no guardian details."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        return email_jobs.refused(request) or Response(guardian_details.send_due(), status=status.HTTP_200_OK)


class SendGuardianConsentRemindersView(APIView):
    """POST with the email jobs' token: email the consent form to today's
    guardians who haven't signed."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        return email_jobs.refused(request) or Response(guardian_reminders.send_due(), status=status.HTTP_200_OK)
