import logging
import re

import requests
from django.conf import settings
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.rbac import get_active_role_name, is_admin
from apps.common.role_names import ROLE_ADMIN

from . import knowledge, llm

logger = logging.getLogger(__name__)

# Unicode tag characters render as nothing but models read them, so they can
# smuggle hidden instructions into a question ("ASCII smuggling").
_TAG_CHARS = re.compile("[\U000E0000-\U000E007F]")


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=500)


class AssistantAskView(APIView):
    """Answer a question about using BIOTech Connect, for the asker's role."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "assistant_ask"

    def post(self, request):
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = _TAG_CHARS.sub("", serializer.validated_data["question"]).strip()
        # The role is read here, never taken from the request, so nobody is
        # shown another role's instructions by asking as them.
        role = ROLE_ADMIN if is_admin(request.user) else get_active_role_name(request.user)
        if settings.OPENAI_API_KEY and question:
            try:
                reply = llm.answer(question, role)
            except (requests.RequestException, ValueError, KeyError):
                # ValueError/KeyError: a reply that isn't the JSON asked for.
                logger.exception("assistant: OpenAI call failed, answering from the FAQ")
                reply = None
            if reply is not None:
                return Response(reply)
        return Response(knowledge.answer(question, role))
