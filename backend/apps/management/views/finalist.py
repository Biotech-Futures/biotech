"""The finalist email: its details, its preview, and Notify Finalists,
which emails every finalist team not yet told. Flagging finalists is
grading's (``apps.grading.views.finalist``)."""
from __future__ import annotations

from functools import partial

from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import IsStaffOrAdmin
from apps.grading.models import FinalistFlag
from apps.services.email_branding import LOGO_CID, logo_data_uri
from apps.submissions.emails import recipients_for

from ..models import FinalistEmailSettings
from ..services import test_email
from ..services.finalist_notify import notify_finalist, render_finalist_email, symposium_today
from ..services.send_guard import (
    FINALIST_SEND,
    AlreadySending,
    Work,
    member_labels,
    run_state,
    start_run,
    submissions_open_reason,
)
from ..services.symposium_emails import member_ids, role_counts

MISSING_DETAILS = (
    "Set the Symposium date, confirm-by date, slides due date and registration "
    "link before sending."
)
ALREADY_SENDING = "Finalist emails are already being sent. Wait for that to finish."
PAST_DATES = "The email's dates can't be before today. Update them before sending."


class FinalistEmailSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinalistEmailSettings
        fields = ["symposium_date", "confirm_by", "slides_due", "registration_url"]

    def validate(self, attrs):
        # A date can't be set to a day before today. One saved earlier that
        # has since passed may stay while other details are edited; sending
        # is what refuses it.
        today = symposium_today()
        errors = {}
        for name in FinalistEmailSettings.DATE_FIELDS:
            day = attrs.get(name)
            if day and day < today and day != getattr(self.instance, name, None):
                errors[name] = "Can't be before today."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


def _email_counts() -> dict:
    """The finalist teams' students, mentors and supervisors with an address
    to be emailed at, and how many have been; a notified team's members
    count as emailed (see ``role_counts``)."""
    flags = list(FinalistFlag.objects.values_list("group_id", "notified"))
    return role_counts(
        member_ids(group_id for group_id, _ in flags),
        [group_id for group_id, _ in flags],
        {group_id for group_id, notified in flags if notified},
    )


class FinalistEmailSettingsView(APIView):
    """GET/PATCH /api/v1/management/finalists/email/ — the dates and link the
    finalist email gives teams. Also says whether the email is complete."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    @staticmethod
    def _payload(details: FinalistEmailSettings) -> dict:
        today = symposium_today()
        return {
            **FinalistEmailSettingsSerializer(details).data,
            "complete": details.is_complete,
            # Sydney's today: the earliest the dates may be, and which saved
            # ones are already before it.
            "today": today,
            "dates_in_past": details.dates_before(today),
            # Why sending waits for submissions to close, or "".
            "submissions_open": submissions_open_reason(),
            # Whether a run is sending now, and its progress.
            **run_state(FINALIST_SEND),
            # Everyone due the email and emailed, by role.
            "counts": _email_counts(),
        }

    def get(self, request):
        return Response(self._payload(FinalistEmailSettings.load()))

    def patch(self, request):
        details = FinalistEmailSettings.load()
        serializer = FinalistEmailSettingsSerializer(details, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self._payload(details))


class FinalistEmailPreviewView(APIView):
    """POST /api/v1/management/finalists/email/preview/ — the email exactly as
    a finalist would get it, for the details in the body (unsaved edits) or
    the saved ones. Addressed to ``recipient``'s team (a person picked in
    Send Test Email), else the first finalist team not yet notified."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        details = FinalistEmailSettings.load()
        serializer = FinalistEmailSettingsSerializer(details, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # Show the edits without saving them.
        for field, value in serializer.validated_data.items():
            setattr(details, field, value)
        recipient = request.data.get("recipient")
        if recipient:
            try:
                rendered, group_name, _files = test_email.preview("finalist", str(recipient), request.data)
            except test_email.TestEmailError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            html = rendered.html.replace(f"cid:{LOGO_CID}", logo_data_uri())
            return Response({"subject": rendered.subject, "group_name": group_name, "html": html})
        flag = (
            FinalistFlag.objects.select_related("group")
            .order_by("notified", "group__group_name")
            .first()
        )
        group_name = flag.group.group_name if flag else "Team name"
        # An admin's edited wording shows here too, as it would be sent.
        rendered = render_finalist_email(group_name, details)
        # A browser has no cid: part to resolve, so the logo goes in inline.
        html = rendered.html.replace(f"cid:{LOGO_CID}", logo_data_uri())
        return Response({"subject": rendered.subject, "group_name": group_name, "html": html})


class FinalistNotifyAllView(APIView):
    """POST /api/v1/management/finalists/notify/ — email finalist teams that
    haven't been notified yet.

    Optional body ``{"group_ids": [1, 2, ...]}`` restricts the send to those
    groups; omitted or empty means every un-notified finalist.

    Starts a run on the server that emails them, so the page can be closed,
    and returns the run's progress. Refused until every email detail is set,
    while submissions are still open, and while a run is going.
    ``notify_finalist`` is a no-op per flag when it was already notified.
    """

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        details = FinalistEmailSettings.load()
        if not details.is_complete:
            return Response({"detail": MISSING_DETAILS}, status=status.HTTP_400_BAD_REQUEST)
        if details.dates_before(symposium_today()):
            return Response({"detail": PAST_DATES}, status=status.HTTP_400_BAD_REQUEST)
        open_reason = submissions_open_reason()
        if open_reason:
            return Response({"detail": open_reason}, status=status.HTTP_400_BAD_REQUEST)
        flags = FinalistFlag.objects.select_related("group").filter(notified=False)
        group_ids = request.data.get("group_ids")
        if group_ids:
            if not isinstance(group_ids, list) or not all(isinstance(g, int) for g in group_ids):
                return Response(
                    {"detail": "group_ids must be a list of integers"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            flags = flags.filter(group_id__in=group_ids)
        work = []
        for flag in flags:
            people = member_labels(flag.group, recipients_for(flag.group))
            # A team with nobody to email has nothing to send.
            if people:
                work.append(Work(list(people.values()), partial(_notify, flag, people, details, request.user)))
        try:
            start_run(FINALIST_SEND, request.user, work)
        except AlreadySending:
            return Response({"detail": ALREADY_SENDING}, status=status.HTTP_409_CONFLICT)
        return Response({
            **run_state(FINALIST_SEND),
            "pending": FinalistFlag.objects.filter(notified=False).count(),
        })


def _notify(flag, people: dict[str, str], details, actor, connection, cache) -> list[str]:
    """One finalist team's email, as a run sends it: who it didn't reach, as
    ``people`` labels them (everyone, when it didn't go at all)."""
    missed: list[str] = []
    if notify_finalist(flag, actor=actor, details=details, connection=connection, missed=missed):
        return []
    return [people.get(address, address) for address in missed] if missed else list(people.values())
