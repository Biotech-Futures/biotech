"""Read-only admin analytics and CSV export endpoints."""

from django.http import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin.analytics_serializers import (
    AnalyticsDateRangeSerializer,
    EmailDeliveryAnalyticsResponseSerializer,
    GroupActivityAnalyticsResponseSerializer,
    LoginActivityAnalyticsResponseSerializer,
    ReportExportQuerySerializer,
    ResourceAnalyticsDateRangeSerializer,
    ResourceAnalyticsResponseSerializer,
)
from apps.admin.permissions import IsAdminScoped
from apps.admin.services.analytics import (
    get_email_delivery_analytics,
    get_group_activity_analytics,
    get_login_activity_analytics,
    get_resource_analytics,
)
from apps.admin.services.reports import build_report, stream_csv


class _DateRangeAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]
    analytics_getter = None
    message = "Analytics retrieved successfully"
    query_serializer_class = AnalyticsDateRangeSerializer
    response_serializer_class = None

    def get(self, request):
        serializer = self.query_serializer_class(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = self.analytics_getter(
            start_date=serializer.validated_data.get("start"),
            end_date=serializer.validated_data.get("end"),
        )
        payload = {"msg": self.message, "data": data}
        return Response(self.response_serializer_class(payload).data)


class GroupActivityAnalyticsView(_DateRangeAnalyticsView):
    analytics_getter = staticmethod(get_group_activity_analytics)
    message = "Group activity analytics retrieved successfully"
    response_serializer_class = GroupActivityAnalyticsResponseSerializer

    @extend_schema(
        parameters=[AnalyticsDateRangeSerializer],
        responses={200: GroupActivityAnalyticsResponseSerializer},
    )
    def get(self, request):
        return super().get(request)


class LoginActivityAnalyticsView(_DateRangeAnalyticsView):
    analytics_getter = staticmethod(get_login_activity_analytics)
    message = "Login activity analytics retrieved successfully"
    response_serializer_class = LoginActivityAnalyticsResponseSerializer

    @extend_schema(
        parameters=[AnalyticsDateRangeSerializer],
        responses={200: LoginActivityAnalyticsResponseSerializer},
    )
    def get(self, request):
        return super().get(request)


class ResourceAnalyticsView(_DateRangeAnalyticsView):
    analytics_getter = staticmethod(get_resource_analytics)
    message = "Resource analytics retrieved successfully"
    query_serializer_class = ResourceAnalyticsDateRangeSerializer
    response_serializer_class = ResourceAnalyticsResponseSerializer

    @extend_schema(
        parameters=[ResourceAnalyticsDateRangeSerializer],
        responses={200: ResourceAnalyticsResponseSerializer},
    )
    def get(self, request):
        return super().get(request)


class EmailDeliveryAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]

    @extend_schema(responses={200: EmailDeliveryAnalyticsResponseSerializer})
    def get(self, request):
        payload = {
            "msg": "Email delivery analytics retrieved successfully",
            "data": get_email_delivery_analytics(),
        }
        return Response(EmailDeliveryAnalyticsResponseSerializer(payload).data)


class ReportExportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminScoped]

    @extend_schema(
        parameters=[ReportExportQuerySerializer],
        responses={(200, "text/csv"): OpenApiTypes.BINARY},
    )
    def get(self, request):
        serializer = ReportExportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        headers, rows, filename = build_report(serializer.validated_data)
        response = StreamingHttpResponse(
            stream_csv(headers, rows), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
