from django.db.models import BooleanField, Case, Value, When
from django.db.models.functions import Length, Substr
from django.http import StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin.permissions import IsAdminScoped
from apps.audit.models import AuditLog
from apps.audit.services import log_audit_event
from apps.common import email_jobs

from . import export
from .filters import filter_entries
from .models import SystemLogEntry
from .serializers import MESSAGE_PREVIEW_CHARS, SystemLogDetailSerializer, SystemLogListSerializer
from .services import prune


class SystemLogPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class SystemLogListView(generics.ListAPIView):
    """GET /api/v1/admin/system-logs/ – the System Logs table, newest first,
    filtered as ``filters.filter_entries`` describes."""

    permission_classes = [IsAuthenticated, IsAdminScoped]
    serializer_class = SystemLogListSerializer
    pagination_class = SystemLogPagination
    filter_backends = []

    def get_queryset(self):
        return (
            filter_entries(self.request.query_params)
            .select_related("user")
            # The full text stays in the database; the row shows a preview.
            .defer("message", "traceback", "extra")
            .annotate(
                message_length=Length("message"),
                message_preview=Substr("message", 1, MESSAGE_PREVIEW_CHARS),
                message_truncated=Case(
                    When(message_length__gt=MESSAGE_PREVIEW_CHARS, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                has_traceback=Case(
                    When(traceback="", then=Value(False)),
                    default=Value(True),
                    output_field=BooleanField(),
                ),
            )
        )


class SystemLogDetailView(generics.RetrieveAPIView):
    """GET /api/v1/admin/system-logs/<id>/ – one row in full."""

    permission_classes = [IsAuthenticated, IsAdminScoped]
    serializer_class = SystemLogDetailSerializer
    queryset = SystemLogEntry.objects.select_related("user")


class SystemLogExportView(APIView):
    """GET /api/v1/admin/system-logs/export/?type=csv|json – every row the
    same filters match (up to ``export.EXPORT_MAX_ROWS``, the newest first),
    streamed. ``X-Export-Truncated: true`` says more rows matched than the file
    holds.

    ``type`` rather than ``format``: DRF reads ``?format=`` itself to pick a
    renderer, and would answer 404 for csv.
    """

    permission_classes = [IsAuthenticated, IsAdminScoped]

    FILE_TYPES = {
        "csv": (export.csv_lines, "text/csv; charset=utf-8", "csv"),
        "json": (export.json_lines, "application/x-ndjson; charset=utf-8", "jsonl"),
    }

    @extend_schema(exclude=True)
    def get(self, request):
        file_type = (request.query_params.get("type") or "csv").lower()
        if file_type not in self.FILE_TYPES:
            return Response({"type": ["Use csv or json."]}, status=status.HTTP_400_BAD_REQUEST)
        lines, content_type, extension = self.FILE_TYPES[file_type]
        # Filters are checked here, so a bad one is a 400 rather than a
        # broken download.
        queryset = filter_entries(request.query_params)

        filters = {key: value for key, value in request.query_params.items() if key != "type"}
        # Not about one record, so there's no entity id to name.
        log_audit_event(
            actor=request.user,
            entity_type="system_log",
            entity_id=0,
            action=AuditLog.ActionChoices.EXPORT,
            after_state={"type": file_type, "filters": filters},
        )

        response = StreamingHttpResponse(
            export.streaming_content(request, lines(queryset)),
            content_type=content_type,
        )
        stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
        response["Content-Disposition"] = f'attachment; filename="system-logs-{stamp}.{extension}"'
        response["Cache-Control"] = "no-store"
        response[export.TRUNCATED_HEADER] = "true" if export.is_truncated(queryset) else "false"
        response[export.ROW_LIMIT_HEADER] = str(export.EXPORT_MAX_ROWS)
        return response


class PruneSystemLogsView(APIView):
    """Daily removal of rows past SYSTEM_LOG_RETENTION_DAYS, called by
    .github/workflows/system-log-prune.yml with the jobs' token."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        return email_jobs.refused(request) or Response({"deleted": prune()}, status=status.HTTP_200_OK)
