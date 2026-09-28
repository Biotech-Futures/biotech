"""The results emails on the Release Results tab: the feedback survey details
they give teams, a preview of each, and sending them in batches."""
from __future__ import annotations

import logging

from django.http import HttpResponse
from django.utils.http import content_disposition_header
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.services.email_branding import LOGO_CID, logo_data_uri

from ..models import CertificatesRelease, MarksRelease, ResultsEmailSettings
from ..permissions import IsGrader
from ..services import results_notify
from ..services.finalist_notify import symposium_today

logger = logging.getLogger(__name__)


class ResultsEmailSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultsEmailSettings
        fields = ["survey_url", "survey_closes"]

    def validate_survey_closes(self, value):
        # Can't be set to a day before today; one saved earlier that has since
        # passed may stay while the link is edited, and sending refuses it.
        if value and value < symposium_today() and value != getattr(self.instance, "survey_closes", None):
            raise serializers.ValidationError("Can't be before today.")
        return value


def _payload(details: ResultsEmailSettings) -> dict:
    today = symposium_today()
    audience = results_notify.results_audience()
    return {
        **ResultsEmailSettingsSerializer(details).data,
        "complete": details.is_complete,
        "today": today,
        "closes_in_past": bool(details.survey_closes and details.survey_closes < today),
        "year": audience.year,
        "marks_released": MarksRelease.load().released_at is not None,
        "certificates_released": CertificatesRelease.load().released_at is not None,
        # Whether each email is switched on in System Emails.
        "emails_on": results_notify.emails_on(),
        # Whether the documents each email carries can be made.
        "templates_ready": results_notify.templates_ready(),
        **audience.counts(),
    }


class ResultsEmailSettingsView(APIView):
    """GET/PATCH /api/v1/grading/results-email/ — the survey details the team
    email gives, whether sending may start, and how many are emailed."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request):
        return Response(_payload(ResultsEmailSettings.load()))

    def patch(self, request):
        details = ResultsEmailSettings.load()
        serializer = ResultsEmailSettingsSerializer(details, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(_payload(details))


class ResultsSampleSheetView(APIView):
    """GET /api/v1/grading/results-email/sample-sheet/ — the marks spreadsheet
    the supervisor email carries, filled with made-up groups, so an admin can
    see what supervisors will get."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request):
        year = results_notify.results_audience().year
        response = HttpResponse(results_notify.sample_marks_sheet(year), content_type=results_notify.XLSX)
        response["Content-Disposition"] = content_disposition_header(
            as_attachment=True, filename=f"{year}_BTF_Student_Marks_Sample.xlsx"
        )
        return response


class ResultsSupervisorSheetView(APIView):
    """GET /api/v1/grading/results-email/supervisor-sheet/<supervisor_id>/ —
    the real marks spreadsheet that supervisor's email would carry, to check
    before sending. Only for a supervisor due the email."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request, supervisor_id: int):
        audience = results_notify.results_audience()
        supervisor = next((s for s in audience.supervisors if s.id == supervisor_id), None)
        if supervisor is None:
            return Response(
                {"detail": "That supervisor isn't due the results email."}, status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(
            results_notify.supervisor_marks_sheet(audience, supervisor), content_type=results_notify.XLSX,
        )
        # Named as the email attaches it.
        response["Content-Disposition"] = content_disposition_header(
            as_attachment=True, filename=f"{audience.year}_BTF_Student_Marks.xlsx"
        )
        return response


class ResultsEmailPreviewView(APIView):
    """POST /api/v1/grading/results-email/preview/ — one email exactly as it
    would go out, for the details in the body (unsaved edits) or the saved
    ones, with the names of the files it carries (not made here). ``audience``
    is "groups" or "supervisors"; it is addressed to the first team or
    supervisor due to get it."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def post(self, request):
        audience_kind = request.data.get("audience")
        if audience_kind not in results_notify.AUDIENCES:
            return Response(
                {"detail": 'audience must be "groups" or "supervisors"'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        details = ResultsEmailSettings.load()
        serializer = ResultsEmailSettingsSerializer(details, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for name, value in serializer.validated_data.items():
            setattr(details, name, value)

        audience = results_notify.results_audience()
        docs = results_notify.Documents(audience.year)
        attachments = results_notify.example_file_names(audience_kind, audience.year)
        if audience_kind == results_notify.GROUPS:
            team = audience.teams[0] if audience.teams else None
            to = team.group_name if team else "Team name"
            rendered = results_notify.render_team_email(to, details, audience.year)
            if team:
                attachments = [f.name for f in results_notify.team_files(docs, audience, team)]
        else:
            supervisor = audience.supervisors[0] if audience.supervisors else None
            to = results_notify._person_name(supervisor) if supervisor else "Supervisor name"
            rendered = results_notify.render_supervisor_email(to, audience.year)
            if supervisor:
                attachments = [f.name for f in results_notify.supervisor_files(docs, audience, supervisor)]
        # A browser has no cid: part to resolve, so the logo goes in inline.
        html = rendered.html.replace(f"cid:{LOGO_CID}", logo_data_uri())
        return Response({"subject": rendered.subject, "to": to, "html": html, "attachments": attachments})


class ResultsEmailSendView(APIView):
    """POST /api/v1/grading/results-email/send/ — email ``audience``
    ("groups" or "supervisors") for the next few teams or supervisors not
    emailed yet. The page calls it again with the returned ``cursor`` until
    ``done``. Refused until marks and certificates are released, and for
    students until the survey details are set."""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def post(self, request):
        audience = request.data.get("audience")
        if audience not in results_notify.AUDIENCES:
            return Response(
                {"detail": 'audience must be "groups" or "supervisors"'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cursor = request.data.get("cursor")
        if cursor is not None and not isinstance(cursor, int):
            return Response({"detail": "cursor must be a number"}, status=status.HTTP_400_BAD_REQUEST)
        reason = results_notify.send_blocked_reason(ResultsEmailSettings.load(), audience)
        if reason:
            return Response({"detail": reason}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = results_notify.send_results_batch(request.user, audience, cursor)
        except (ConnectionError, OSError) as exc:
            logger.error("results email: mail server unreachable error=%s", type(exc).__name__)
            return Response(
                {"detail": "Couldn't reach the mail server. Nothing more was sent; try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(result)
