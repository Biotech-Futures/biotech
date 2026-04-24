from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.views import APIView

from django.core.paginator import Paginator

from .serializers import (
    DashboardGroupPreviewSerializer,
    DashboardNextEventSerializer,
    DashboardSummarySerializer,
)
from .services import (
    get_dashboard_summary,
    get_groups_preview,
    get_personalized_next_event,
)

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
    """
    GET /dashboard/v1/groups-preview/

    Returns paginated group rows with DB-annotated member_count and lead fields;
    see ``get_groups_preview`` and ``DashboardGroupPreviewSerializer``.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        mine = request.query_params.get("mine", "false").lower() == "true"

        # Optional filter aligned with the dashboard widget (integer track primary key).
        track_id_param = request.query_params.get("track_id")
        track_id = None
        if track_id_param not in (None, ""):
            try:
                track_id = int(track_id_param)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "track_id must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        results = get_groups_preview(user=request.user, mine=mine, track_id=track_id)

        page_size = int(request.query_params.get("page_size", 20))
        page_number = int(request.query_params.get("page", 1))
        paginator = Paginator(results, page_size)
        page = paginator.get_page(page_number)

        # Materialize one page so serialization does not issue extra queries per row.
        serializer = DashboardGroupPreviewSerializer(list(page.object_list), many=True)
        return Response({
            "count": paginator.count,
            "next": page_number + 1 if page.has_next() else None,
            "previous": page_number - 1 if page.has_previous() else None,
            "results": serializer.data,
        })
