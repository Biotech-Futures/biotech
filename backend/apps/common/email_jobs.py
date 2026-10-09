"""The scheduled email jobs' shared secret.

GitHub's schedules call each email job's endpoint (the RSVP reminders, the
submission reminders, the unread messages digest and the two guardian
reminders) with ``EMAIL_JOBS_TOKEN`` in the ``X-Email-Jobs-Token`` header.
There's no person behind these calls, so the token stands in for a session.
"""
import hmac

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

HEADER = "X-Email-Jobs-Token"


def refused(request):
    """Why ``request`` can't run an email job, as a response; None when it can.
    With ``EMAIL_JOBS_TOKEN`` unset the jobs answer 503 rather than standing
    open, so a deploy that forgot it fails loud."""
    expected = getattr(settings, "EMAIL_JOBS_TOKEN", "") or ""
    if not expected:
        return Response(
            {"detail": "The email jobs are not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if not hmac.compare_digest(request.headers.get(HEADER, ""), expected):
        return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)
    return None
