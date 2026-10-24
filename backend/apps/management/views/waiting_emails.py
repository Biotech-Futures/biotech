"""The trigger for sending, by hand from
``.github/workflows/waiting-emails.yml`` (the backend's timer runs the same
code every 10 minutes, ``apps.management.scheduler``), to send the emails kept while the
mail server couldn't be reached (``services.waiting_email``)."""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common import email_jobs
from apps.services.waiting_email import queue_waiting


class SendWaitingEmailsView(APIView):
    """POST: give up on the waiting emails past their time, then queue a run
    for each mailbox with emails still waiting, and answer at once (202) with
    ``{"status": "queued", "mailboxes": [...]}``. Called with the email jobs'
    shared token in the ``X-Email-Jobs-Token`` header, as the other scheduled
    jobs are: there's no person behind the call."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        refusal = email_jobs.refused(request)
        if refusal:
            return refusal
        return Response({"status": "queued", "mailboxes": queue_waiting()}, status=status.HTTP_202_ACCEPTED)
