from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import DashboardNextEventSerializer
from .services import get_personalized_next_event


class DashboardNextEventView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=None, responses={200: DashboardNextEventSerializer, 204: None})
    def get(self, request):
        payload = get_personalized_next_event(request.user)
        if payload is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(DashboardNextEventSerializer(payload).data, status=status.HTTP_200_OK)

