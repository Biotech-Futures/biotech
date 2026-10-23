"""The trigger for the check, by hand from
``.github/workflows/bounce-check.yml`` (the backend's timer runs the same
code every 10 minutes, ``apps.management.scheduler``), to check the sending mailboxes for
bounce notices (``services.bounce_check``)."""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common import email_jobs

from ..services.bounce_check import start_check


class BounceCheckTriggerView(APIView):
    """POST: start a bounce check on a background thread and answer at once
    (202), with ``{"status"}``: "started", "already running", or "off" while
    no Mail API key is set. Called with the email jobs' shared token in the
    ``X-Email-Jobs-Token`` header, as the other scheduled jobs are: there's no
    person behind the call."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        refusal = email_jobs.refused(request)
        if refusal:
            return refusal
        return Response({"status": start_check()}, status=status.HTTP_202_ACCEPTED)
