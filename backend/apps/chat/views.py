# Chat HTTP surface:
#   GET    /chat/groups/{gid}/messages/         list (nested — group-scoped)
#   POST   /chat/groups/{gid}/messages/         send (nested — creates into group)
#   PATCH  /chat/messages/{id}/                 edit (flat — operates on one message)
#   DELETE /chat/messages/{id}/                 soft-delete (flat — same)
#
# All write paths broadcast a ``chat.message`` envelope to the matching
# Channels group so connected WebSocket consumers see message.created /
# message.edited / message.deleted in real time.

from django.db.models import Q
from rest_framework import (
    viewsets,
    status,
    generics,
    mixins,
    permissions,
)
from rest_framework.response import Response
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Messages
from .serializers import MessageSerializer, MessageUpdateSerializer
from .management.permissions import (
    IsGroupMemberOrAdmin,
    CanModerateMessage,
    CanEditMessage,
)


def _broadcast(group_id: int, payload: dict) -> None:
    """
    Single fan-out helper so every write path uses the same envelope shape
    and the same group naming convention. Keeping this in one place avoids
    drift between create / edit / delete payloads.
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"group_{group_id}",
        {"type": "chat.message", "payload": payload},
    )


class MessageViewSet(viewsets.ModelViewSet):
    """
    Nested router for the *collection* operations on a group:
        GET  /chat/groups/{gid}/messages/   — list with cursor pagination
        POST /chat/groups/{gid}/messages/   — send a new message

    Per-message operations (PATCH, DELETE) live on flat URLs — see
    ``MessageDetailView`` in this module — so the URL shape itself signals
    "collection vs. single-message" intent.
    """

    serializer_class = MessageSerializer
    permission_classes = [IsGroupMemberOrAdmin]
    # PATCH and DELETE are served by the flat MessageDetailView (see urls.py).
    # We strip them here so legacy nested calls return 405 instead of silently
    # routing to a different code path.
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        gid = self.kwargs.get("group_pk")
        return (
            Messages.objects.filter(group_id=gid, deleted_at__isnull=True)
            .select_related("sender_user")
            .prefetch_related("resources__resource")
        )

    # GET /chat/groups/{gid}/messages/?after=<id>&limit=<n>
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

        _broadcast(
            gid,
            {
                "event": "message.created",
                "group_id": gid,
                "message": {
                    "id": msg.id,
                    "sender_id": msg.sender_user_id,
                    "text": msg.message_text,
                    "message_type": msg.message_type,
                    "sent_at": msg.sent_at.isoformat(),
                    "resource_ids": list(
                        msg.resources.values_list("resource_id", flat=True)
                    ),
                },
            },
        )

    def create(self, request, *args, **kwargs):
        resp = super().create(request, *args, **kwargs)
        resp.status_code = status.HTTP_201_CREATED
        return resp


class MessageDetailView(
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    generics.GenericAPIView,
):
    """
    Flat per-message endpoint:

        PATCH  /chat/messages/{id}/   — sender-only, time-boxed edit
        DELETE /chat/messages/{id}/   — soft delete (sender within window
                                        OR chat-mod scope)

    The two verbs are deliberately the only ones exposed:

      - GET / POST live on the nested collection URL (``MessageViewSet``);
        retrieving a single message in isolation is not part of the chat
        contract — clients always read messages as a paginated list.
      - PUT is omitted because edits only ever change ``message_text``,
        and partial-update is the right semantic.

    Each verb has its own permission contract — see ``get_permissions``.
    """

    queryset = (
        Messages.objects.filter(deleted_at__isnull=True)
        .select_related("group", "group__track", "sender_user")
    )
    http_method_names = ["patch", "delete", "head", "options"]

    def get_serializer_class(self):
        # DELETE doesn't read or write a serializer body, but DRF still calls
        # this when building the schema, so return a non-None default.
        if self.request.method == "PATCH":
            return MessageUpdateSerializer
        return MessageSerializer

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [permissions.IsAuthenticated(), CanModerateMessage()]
        return [permissions.IsAuthenticated(), CanEditMessage()]

    # ---- PATCH (edit) -------------------------------------------------------
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        _broadcast(
            instance.group_id,
            {
                "event": "message.edited",
                "group_id": instance.group_id,
                "message_id": instance.id,
                "message_text": instance.message_text,
                "edited_at": (
                    instance.edited_at.isoformat() if instance.edited_at else None
                ),
            },
        )
        return Response(MessageSerializer(instance).data)

    # ---- DELETE (soft delete) ----------------------------------------------
    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()

        _broadcast(
            instance.group_id,
            {
                "event": "message.deleted",
                "group_id": instance.group_id,
                "message_id": instance.id,
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
