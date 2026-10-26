import logging

import anthropic
from django.conf import settings
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import get_active_role_name, is_admin
from apps.common.role_names import ROLE_ADMIN

from . import knowledge, llm

logger = logging.getLogger(__name__)


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=500)


class AssistantAskView(APIView):
    """Answer a question about using BIOTech Connect, for the asker's role."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "assistant_ask"

    def post(self, request):
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data["question"]
        # The role is read here, never taken from the request, so nobody is
        # shown another role's instructions by asking as them.
        role = ROLE_ADMIN if is_admin(request.user) else get_active_role_name(request.user)
        if settings.ANTHROPIC_API_KEY:
            try:
                reply = llm.answer(question, role)
            except (anthropic.AnthropicError, ValueError):
                # ValueError: a reply that isn't the JSON asked for.
                logger.exception("assistant: Claude call failed, answering from the FAQ")
                reply = None
            if reply is not None:
                return Response(reply)
        return Response(knowledge.answer(question, role))
