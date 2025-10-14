from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from apps.groups.models import GroupMembers


class GroupChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.group_id = self.scope["url_route"]["kwargs"]["group_id"]
        self.room_group_name = f"group_{self.group_id}"

        user = self.scope["user"]
        if not user.is_authenticated or not await self.is_member(user.id):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    @database_sync_to_async
    def is_member(self, uid):
        return GroupMembers.objects.filter(user_id=uid, group_id=self.group_id).exists()

    async def receive_json(self, content):
        # Broadcast message text + optional resource IDs
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message",
                "payload": {
                    "user": self.scope["user"].id,
                    "content": content.get("content"),
                    "resource_ids": content.get("resource_ids", []),
                },
            },
        )

    async def chat_message(self, event):
        await self.send_json(event["payload"])

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
