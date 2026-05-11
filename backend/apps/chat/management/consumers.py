"""WebSocket consumer for group chat.

The WebSocket is strictly **server -> client**. Clients do not send
messages over the socket; every write goes through the REST API
(``POST /chat/groups/{gid}/messages/``), which then calls
``channel_layer.group_send`` to fan the resulting event out to every
subscriber on this consumer.

Wire protocol — every payload received by the client over the socket
has the same envelope:

    {
      "event": "message.created" | "message.edited" | "message.deleted",
      "group_id": <int>,
      "message": { ...full MessageSerializer payload... }
    }

For deletes the embedded message has ``is_deleted=true`` and a non-null
``deleted_at`` so the front end can drive its UI from a single shape.
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.chat.rbac import can_access_chat_group
from apps.groups.models import Groups


class GroupChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        url_route = self.scope.get("url_route") or {}
        raw_group_id = (url_route.get("kwargs") or {}).get("group_id")
        try:
            self.group_id = int(raw_group_id)
        except (TypeError, ValueError):
            await self.close(code=4400)
            return
        self.room_group_name = f"group_{self.group_id}"

        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4403)
            return

        if not await self._can_access_group(user):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    @database_sync_to_async
    def _can_access_group(self, user):
        group = Groups.objects.only("id", "track_id").filter(pk=self.group_id).first()
        return can_access_chat_group(user, group)

    async def chat_message(self, event):
        await self.send_json(event["payload"])

    async def disconnect(self, code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )
