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

from apps.chat.models import Messages
from apps.chat.rbac import can_access_chat_group
from apps.chat.views import mark_delivered_cursor
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

        # Catch-up: mark everything currently in the group as delivered
        # for this user, mirroring WhatsApp's "double-tick on app open".
        # Runs after ``accept()`` so a slow DB query never delays the
        # handshake.
        await self._auto_mark_delivered(user)

    @database_sync_to_async
    def _can_access_group(self, user):
        group = Groups.objects.only("id", "track_id").filter(pk=self.group_id).first()
        return can_access_chat_group(user, group)

    @database_sync_to_async
    def _auto_mark_delivered(self, user):
        latest_id = (
            Messages.objects
            .filter(group_id=self.group_id, deleted_at__isnull=True)
            .exclude(sender_user_id=user.id)
            .order_by("-id")
            .values_list("id", flat=True)
            .first()
        )
        if latest_id is None:
            return
        mark_delivered_cursor(user, self.group_id, latest_id)

    async def chat_message(self, event):
        # Mirror per-message live delivery: when this consumer forwards a
        # newly-created message to its client, also mark that message as
        # delivered for the connected user (skipping the sender, who has
        # no MessageStatus row of their own). Idempotent.
        payload = event.get("payload") or {}
        if payload.get("event") == "message.created":
            user = self.scope.get("user")
            msg = payload.get("message") or {}
            sender_id = msg.get("sender_user") or msg.get("sender_id")
            mid = msg.get("id")
            if (
                user is not None
                and getattr(user, "is_authenticated", False)
                and isinstance(mid, int)
                and sender_id != user.id
            ):
                await self._mark_one_delivered(user, mid)
        await self.send_json(payload)

    @database_sync_to_async
    def _mark_one_delivered(self, user, message_id):
        mark_delivered_cursor(user, self.group_id, message_id)

    async def disconnect(self, code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )
