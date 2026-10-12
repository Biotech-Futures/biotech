"""The scheduled email jobs' shared secret.

GitHub's schedules call each email job's endpoint (the RSVP reminders, the
submission reminders, the unread messages digest and the two guardian
reminders) with a token in the ``X-Email-Jobs-Token`` header. There's no
person behind these calls, so the token stands in for a session.

While the jobs move from ``RSVP_REMINDER_TOKEN`` to ``EMAIL_JOBS_TOKEN``,
either is accepted, so the two can be set on GitHub and Azure in any order.
"""
import hmac

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

HEADER = "X-Email-Jobs-Token"


def refused(request):
    """Why ``request`` can't run an email job, as a response; None when it can.
    With no token set the jobs answer 503 rather than standing open, so a
    deploy that forgot it fails loud."""
    accepted = [
        token
        for token in (getattr(settings, "EMAIL_JOBS_TOKEN", ""), getattr(settings, "RSVP_REMINDER_TOKEN", ""))
        if token
    ]
    if not accepted:
        return Response(
            {"detail": "The email jobs are not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    provided = request.headers.get(HEADER, "")
    # Every token compared, so the time taken doesn't tell which one matched.
    if not sum(hmac.compare_digest(provided, token) for token in accepted):
        return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)
    return None
