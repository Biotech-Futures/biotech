from django.db.models import Q
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Messages
from .serializers import MessageSerializer
from .management.permissions import IsGroupMemberOrStaff,  CanModerateMessage


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsGroupMemberOrStaff]

    # choose permissions per action
    def get_permissions(self):
        if self.action == "destroy":
            return [CanModerateMessage()]
        return [IsGroupMemberOrStaff()]

    def get_queryset(self):
        gid = self.kwargs.get("group_pk")
        return (
            Messages.objects.filter(group_id=gid, deleted_flag=False)
            .select_related("sender_user")
            .prefetch_related("resources__resource", "attachments")
        )
    
    # --- #106: DELETE /groups/{gid}/messages/{mid} (soft-delete + WS) ---
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()  # permission already checked on object
        instance.deleted_flag = True
        instance.save(update_fields=["deleted_flag"])

        # broadcast deletion to group room
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"group_{instance.group_id}",
            {
                "type": "chat.message",
                "payload": {
                    "event": "message.deleted",
                    "group_id": instance.group_id,
                    "message_id": instance.id,
                },
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # --- #105: GET /groups/{id}/messages?after={cursor}&limit={n} ---
    def list(self, request, *args, **kwargs):
        gid = self.kwargs.get("group_pk")
        qs = self.get_queryset().order_by("-sent_datetime", "-id")

        # cursor: items newer than this message id
        after = request.query_params.get("after")
        if after:
            try:
                pivot = Messages.objects.get(pk=int(after), group_id=gid)
                qs = qs.filter(
                    Q(sent_datetime__gt=pivot.sent_datetime) |
                    Q(sent_datetime=pivot.sent_datetime, id__gt=pivot.id)
                )
            except (ValueError, Messages.DoesNotExist):
                pass  # ignore bad cursor and return latest

        # limit (default 50, max 100, min 1)
        try:
            limit = int(request.query_params.get("limit", 50))
        except ValueError:
            limit = 50
        limit = 100 if limit > 100 else (1 if limit < 1 else limit)

        items = list(qs[:limit])
        data = self.get_serializer(items, many=True).data
        next_after = items[0].id if items else None

        return Response({"items": data, "next_after": next_after}, status=status.HTTP_200_OK)

    # --- #104: POST /groups/{id}/messages ---
    def perform_create(self, serializer):
        gid = int(self.kwargs.get("group_pk"))
        msg = serializer.save(sender_user=self.request.user, group_id=gid)

        # Broadcast to group WS room after save
        channel_layer = get_channel_layer()
        payload = {
            "type": "chat.message",
            "payload": {
                "event": "message.created",
                "group_id": gid,
                "message": {
                    "id": msg.id,
                    "sender_id": msg.sender_user_id,
                    "text": msg.message_text,
                    "sent_datetime": msg.sent_datetime.isoformat(),
                    "resource_ids": list(msg.resources.values_list("resource_id", flat=True)),
                },
            },
        }
        async_to_sync(channel_layer.group_send)(f"group_{gid}", payload)

    def create(self, request, *args, **kwargs):
        resp = super().create(request, *args, **kwargs)
        resp.status_code = status.HTTP_201_CREATED
        return resp
