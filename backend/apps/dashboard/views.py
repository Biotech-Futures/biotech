from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action

from .serializers import DashboardSummarySerializer
from . import services


class DashboardViewSet(GenericViewSet):
    """
    Base Dashboard ViewSet.
    No business logic here — all delegated to services.py.
    """

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        data = services.get_dashboard_summary(request.user)
        serializer = DashboardSummarySerializer(data)
        return Response(serializer.data)