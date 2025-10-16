from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from apps.groups.models import GroupMembers
from apps.users.utils.roles import get_active_assignment

ROLE_ADMIN = "admin"

class GroupChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.group_id = self.scope["url_route"]["kwargs"]["group_id"]
        self.room_group_name = f"group_{self.group_id}"

        user = self.scope["user"]

        # Reject unauthenticated users
        if not user.is_authenticated:
            await self.close(code=4403)
            return

        # Allow admin/supervisor globally
        if await self._has_admin_access(user):
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
            return

        # Otherwise require membership
        if not await self.is_member(user.id):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    @database_sync_to_async
    def _has_admin_access(self, user):
        rah = get_active_assignment(user)
        return bool(
            rah and rah.role and rah.role.role_name in {ROLE_ADMIN}
        )

    @database_sync_to_async
    def is_member(self, uid):
        return GroupMembers.objects.filter(user_id=uid, group_id=self.group_id).exists()


    async def receive_json(self, content, **kwargs):
        # Optional: echo client-sent messages to the group (not used by your tests)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message",
                "payload": {
                    "event": "client.message",
                    "group_id": self.group_id,
                    "message": {
                        "text": content.get("content"),
                        "resource_ids": content.get("resource_ids", []),
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
