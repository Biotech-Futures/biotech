from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import get_active_role_name, is_admin
from apps.common.role_names import ROLE_ADMIN

from .knowledge import answer


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=500)


class AssistantAskView(APIView):
    """Answer a question about using BIOTech Connect, for the asker's role."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "assistant_ask"

    def post(self, request):
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # The role is read here, never taken from the request, so nobody is
        # shown another role's instructions by asking as them.
        role = ROLE_ADMIN if is_admin(request.user) else get_active_role_name(request.user)
        return Response(answer(serializer.validated_data["question"], role))
