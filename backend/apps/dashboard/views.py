from django.core.paginator import Paginator
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.views import APIView

from apps.tasks.services import build_progress_snapshot, get_allowed_group_ids
from .serializers import (
    DashboardGroupPreviewSerializer,
    DashboardNextEventSerializer,
    DashboardSummarySerializer,
    GroupsPreviewQuerySerializer,
    ProgressQuerySerializer,
    ProgressSnapshotSerializer,
)
from .services import (
    get_dashboard_summary,
    get_personalized_next_event,
    get_groups_preview,
)

class DashboardProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query_serializer = ProgressQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        group_id = query_serializer.validated_data.get("group_id")

        allowed_ids = list(get_allowed_group_ids(request.user))

        if group_id is not None:
            if group_id not in allowed_ids:
                return Response(
                    {"detail": "You do not have access to this group."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            snapshot = build_progress_snapshot(group_id=group_id)
        else:
            snapshot = build_progress_snapshot(allowed_group_ids=allowed_ids)

        return Response(ProgressSnapshotSerializer(snapshot).data, status=status.HTTP_200_OK)


class DashboardViewSet(GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        data = get_dashboard_summary(request.user)
        serializer = DashboardSummarySerializer(data)
        return Response(serializer.data)


class DashboardNextEventView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=None, responses={200: DashboardNextEventSerializer, 204: None})
    def get(self, request):
        payload = get_personalized_next_event(request.user)
        if payload is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(DashboardNextEventSerializer(payload).data, status=status.HTTP_200_OK)


class GroupsPreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=None, responses={200: DashboardGroupPreviewSerializer(many=True)})
    def get(self, request):
        query = GroupsPreviewQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data

        queryset = get_groups_preview(
            user=request.user,
            mine=params["mine"],
            track_id=params.get("track_id"),
        )

        page_number = params["page"]
        paginator = Paginator(queryset, params["page_size"])
        page = paginator.get_page(page_number)

        serializer = DashboardGroupPreviewSerializer(page.object_list, many=True)
        return Response({
            "count": paginator.count,
            "next": page_number + 1 if page.has_next() else None,
            "previous": page_number - 1 if page.has_previous() else None,
            "results": serializer.data,
        })