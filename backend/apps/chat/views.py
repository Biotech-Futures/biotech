from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.response import Response

from .management.permissions import (
    CanEditMessage,
    CanModerateMessage,
    IsGroupMemberOrAdmin,
)
from .models import Messages
from .serializers import MessageSerializer, MessageUpdateSerializer


def _broadcast(group_id: int, event: str, message_payload: dict) -> None:
    """Fan a chat event out to every consumer subscribed to ``group_id``.

    Wrapped in ``transaction.on_commit`` so a rolled-back DB write never
    produces a phantom WebSocket event. Envelope shape is the single
    contract documented at the top of
    ``apps/chat/management/consumers.py``.
    """
    channel_layer = get_channel_layer()
    envelope = {
        "type": "chat.message",
        "payload": {
            "event": event,
            "group_id": group_id,
            "message": message_payload,
        },
    }

    def _send():
        async_to_sync(channel_layer.group_send)(f"group_{group_id}", envelope)

    transaction.on_commit(_send)


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsGroupMemberOrAdmin]

    def get_permissions(self):
        if self.action == "destroy":
            return [CanModerateMessage()]
        if self.action == "partial_update":
            return [CanEditMessage()]
        return [IsGroupMemberOrAdmin()]

    def get_serializer_class(self):
        if self.action == "partial_update":
            return MessageUpdateSerializer
        return MessageSerializer

    def get_queryset(self):
        gid = self.kwargs.get("group_pk")
        return (
            Messages.objects.filter(group_id=gid, deleted_at__isnull=True)
            .select_related("sender_user")
            .prefetch_related("resources__resource")
        )

    # GET /chat/groups/{gid}/messages/
    def list(self, request, *args, **kwargs):
        gid = self.kwargs.get("group_pk")
        qs = self.get_queryset().order_by("-sent_at", "-id")

        after = request.query_params.get("after")
        if after:
            try:
                pivot = Messages.objects.get(pk=int(after), group_id=gid)
                qs = qs.filter(
                    Q(sent_at__gt=pivot.sent_at)
                    | Q(sent_at=pivot.sent_at, id__gt=pivot.id)
                )
            except (ValueError, Messages.DoesNotExist):
                pass

        try:
            limit = int(request.query_params.get("limit", 50))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 100))

        items = list(qs[:limit])
        data = self.get_serializer(items, many=True).data
        next_after = items[0].id if items else None

        return Response(
            {"items": data, "next_after": next_after},
            status=status.HTTP_200_OK,
        )

    # POST /chat/groups/{gid}/messages/
    def perform_create(self, serializer):
        gid = int(self.kwargs.get("group_pk"))
        msg = serializer.save(sender_user=self.request.user, group_id=gid)
        _broadcast(gid, "message.created", MessageSerializer(msg).data)

    def create(self, request, *args, **kwargs):
        resp = super().create(request, *args, **kwargs)
        resp.status_code = status.HTTP_201_CREATED
        return resp

    # PATCH /chat/groups/{gid}/messages/{id}/
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        _broadcast(
            instance.group_id, "message.edited", MessageSerializer(instance).data
        )
        return Response(MessageSerializer(instance).data)

    # DELETE /chat/groups/{gid}/messages/{id}/
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        _broadcast(
            instance.group_id, "message.deleted", MessageSerializer(instance).data
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
