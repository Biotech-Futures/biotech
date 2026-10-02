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
from ..services.delivery import already_sent
from ..services.finalist_notify import EMAIL_KEY, notify_finalist, render_finalist_email, symposium_today
from ..services.send_guard import (
    FINALIST_SEND,
    NOT_SENT,
    AlreadySending,
    Work,
    last_missed,
    member_labels,
    missed_people,
    run_state,
    start_run,
    submissions_open_reason,
)
from ..services.symposium_emails import member_ids, reached_ids, role_counts

MISSING_DETAILS = (
    "Set the Symposium date, confirm-by date, slides due date and registration "
    "link before sending."
)
ALREADY_SENDING = "Finalist emails are already being sent. Wait for that to finish."
PAST_DATES = "The email's dates can't be before today. Update them before sending."
# The teams a send can be limited to (see ``_due``).
WHICH = ("new", "missed")


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
    to be emailed at, and how many have been: everyone on a notified team,
    and whoever a run reached on the others (see ``role_counts``)."""
    flags = list(FinalistFlag.objects.values_list("group_id", "notified"))
    group_ids = [group_id for group_id, _ in flags]
    return role_counts(
        member_ids(group_ids),
        group_ids,
        {group_id for group_id, notified in flags if notified},
        reached_ids(EMAIL_KEY, group_ids),
    )


def _tried(flags) -> set[int]:
    """Which of these un-notified finalist teams a send has already tried:
    someone on it has the email, or the last run missed someone on it."""
    tried = set(already_sent(EMAIL_KEY, [flag.group_id for flag in flags]))
    missed = last_missed(FINALIST_SEND)
    for flag in flags:
        prefix = f"({flag.group.group_name}) "
        if any(who.startswith(prefix) for who in missed):
            tried.add(flag.group_id)
    return tried


def _due(which: str = "", group_ids=None) -> list[tuple[FinalistFlag, list[str]]]:
    """The finalist teams not yet notified, each with the addresses on it
    still due the email: all of them, those picked (``group_ids``), those no
    send has tried yet (``which="new"``), or those a send missed someone on
    (``which="missed"``). A team with nobody to email is left out."""
    flags = FinalistFlag.objects.select_related("group").filter(notified=False)
    if group_ids:
        flags = flags.filter(group_id__in=group_ids)
    flags = list(flags)
    if which:
        tried = _tried(flags)
        flags = [flag for flag in flags if (flag.group_id in tried) == (which == "missed")]
    sent = already_sent(EMAIL_KEY, [flag.group_id for flag in flags])
    due = []
    for flag in flags:
        recipients = recipients_for(flag.group)
        if recipients:
            done = sent.get(flag.group_id, set())
            due.append((flag, [address for address in recipients if address.lower() not in done]))
    return due


def _waiting() -> dict:
    """The teams, and the people on them, each limited send would email:
    ``{"new": {"teams", "people"}, "missed": {"teams", "people"}}``."""
    waiting = {}
    for which in WHICH:
        due = _due(which)
        waiting[which] = {"teams": len(due), "people": sum(len(addresses) for _, addresses in due)}
    return waiting


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
            # Who Email Newly Added and Resend Email Those Missed would email.
            "waiting": _waiting(),
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
    groups; omitted or empty means every un-notified finalist. Or
    ``{"which": "new"}`` for the teams no send has tried yet, and
    ``{"which": "missed"}`` for only the people earlier sends missed (see
    ``_due``).

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
        which = request.data.get("which") or ""
        if which not in ("", *WHICH):
            return Response({"detail": "which must be new or missed"}, status=status.HTTP_400_BAD_REQUEST)
        group_ids = request.data.get("group_ids")
        if group_ids:
            if not isinstance(group_ids, list) or not all(isinstance(g, int) for g in group_ids):
                return Response(
                    {"detail": "group_ids must be a list of integers"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        work = []
        # A team whose members all got it in earlier runs is sent to nobody
        # and only marked notified.
        for flag, addresses in _due(which, group_ids):
            people = member_labels(flag.group, addresses)
            work.append(Work(list(people.values()), partial(_notify, flag, people, details, request.user)))
        try:
            start_run(FINALIST_SEND, request.user, work)
        except AlreadySending:
            return Response({"detail": ALREADY_SENDING}, status=status.HTTP_409_CONFLICT)
        return Response({
            **run_state(FINALIST_SEND),
            "pending": FinalistFlag.objects.filter(notified=False).count(),
        })


def _notify(flag, people: dict[str, str], details, actor, connection, cache) -> list[dict]:
    """One finalist team's email, as a run sends it: who it didn't reach and
    why, as ``people`` labels them (everyone, when it didn't go at all)."""
    failed: dict[str, str] = {}
    if notify_finalist(flag, actor=actor, details=details, connection=connection, missed=failed):
        return []
    if failed:
        return missed_people(people, failed)
    return [{"who": who, "reason": NOT_SENT} for who in people.values()]
