from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.views import APIView

from .serializers import DashboardNextEventSerializer, DashboardSummarySerializer
from .services import get_dashboard_summary, get_personalized_next_event


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
