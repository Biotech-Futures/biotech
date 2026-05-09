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

from apps.groups.models import GroupMembership, Groups
from apps.users.utils.admin_scope import can_admin_track


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

        if not await self._can_read_group(user, self.group_id):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    @database_sync_to_async
    def _can_read_group(self, user, group_id):
        if GroupMembership.objects.filter(
            user=user, group_id=group_id, left_at__isnull=True
        ).exists():
            return True
        track_id = (
            Groups.objects.filter(pk=group_id)
            .values_list("track_id", flat=True)
            .first()
        )
        return can_admin_track(user, track_id)

    async def chat_message(self, event):
        await self.send_json(event["payload"])

    async def disconnect(self, code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )
