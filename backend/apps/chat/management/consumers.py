from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from apps.chat.utils import sanitize_text

from apps.chat.rbac import can_access_chat_group
from apps.groups.models import Groups

class GroupChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Defensive parsing: the URL route kwarg may be missing, non-numeric,
        # or otherwise malformed. We refuse the connection cleanly instead
        # of letting an unhandled exception take the consumer down.
        url_route = self.scope.get("url_route") or {}
        raw_group_id = (url_route.get("kwargs") or {}).get("group_id")
        try:
            self.group_id = int(raw_group_id)
        except (TypeError, ValueError):
            await self.close(code=4400)
            return
        self.room_group_name = f"group_{self.group_id}"

        user = self.scope["user"]

        # Reject unauthenticated users
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

    async def receive_json(self, content, **kwargs):
        # Defensive: a malformed client could send a JSON list / string /
        # number. Reject anything that is not a dict before we try to
        # call ``.get`` on it.
        if not isinstance(content, dict):
            return

        raw_text = content.get("content")
        # Sanitise transient broadcasts too, so the same moderation policy
        # applies whether the message hits the DB via the REST endpoint or
        # is just echoed across the websocket group.
        text = sanitize_text(raw_text) if isinstance(raw_text, str) else raw_text

        resource_ids = content.get("resource_ids", [])
        if not isinstance(resource_ids, list):
            resource_ids = []

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message",
                "payload": {
                    "event": "client.message",
                    "group_id": self.group_id,
                    "message": {
                        "text": text,
                        "resource_ids": resource_ids,
                        "sender_id": self.scope["user"].id,
                    },
                },
            },
        )

    async def chat_message(self, event):
        # Forward the WHOLE event so tests can assert event["payload"][...]
        await self.send_json(event["payload"])

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
