import time
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from apps.groups.models import GroupMembership
from apps.users.utils.roles import get_active_assignment

ROLE_ADMIN = "admin"

# Rate limit: max 1 broadcast per 2 seconds per user per group
TYPING_RATE_LIMIT_SECONDS = 2


class GroupChatConsumer(AsyncJsonWebsocketConsumer):

    # Tracks last typing broadcast time per (group, user)
    # { "group_1_user_5": 1234567890.123 }
    _typing_timestamps = {}

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
        return GroupMembership.objects.filter(
            user_id=uid,
            group_id=self.group_id,
            left_at__isnull=True,
        ).exists()

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")

        # Handle typing indicator events
        if event_type == "client.typing":
            await self._handle_typing(content)
            return

        # Default: echo client-sent messages to the group
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

    async def _handle_typing(self, content):
        """
        Rate-limited typing broadcast.
        Max 1 broadcast per TYPING_RATE_LIMIT_SECONDS per user per group.
        """
        user = self.scope["user"]
        status = content.get("status", "started")

        # Rate limit key per user per group
        rate_key = f"group_{self.group_id}_user_{user.id}"
        now = time.monotonic()
        last_sent = self._typing_timestamps.get(rate_key, 0)

        # Only broadcast if enough time has passed
        if now - last_sent < TYPING_RATE_LIMIT_SECONDS:
            return

        # Update timestamp
        self._typing_timestamps[rate_key] = now

        # Broadcast typing event to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing.updated",
                "user_id": user.id,
                "status": status,
                "group_id": self.group_id,
            },
        )

    async def typing_updated(self, event):
        """Forward typing.updated events to WebSocket clients."""
        await self.send_json({
            "type": "typing.updated",
            "user_id": event["user_id"],
            "status": event["status"],
            "group_id": event["group_id"],
        })

    async def chat_message(self, event):
        # Forward the WHOLE event so tests can assert event["payload"][...]
        await self.send_json(event["payload"])

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)