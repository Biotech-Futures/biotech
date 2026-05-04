from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from apps.groups.models import GroupMembership
from apps.users.utils.roles import get_active_assignment
from apps.chat.utils import sanitize_text

ROLE_ADMIN = "admin"

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
