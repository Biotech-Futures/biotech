from rest_framework import viewsets, permissions
from .models import Messages
from .serializers import MessageSerializer
from rest_framework.response import Response
from rest_framework import status
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Messages
from .serializers import MessageSerializer
from .permissions import IsGroupMemberOrStaff


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsGroupMemberOrStaff]

    def get_queryset(self):
        gid = self.kwargs.get("group_pk")
        return (
            Messages.objects.filter(group_id=gid, deleted_flag=False)
            .select_related("sender_user")
            .prefetch_related("resources__resource", "attachments")
        )

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