"""WebSocket consumer for group chat.

The WebSocket is **mostly** server -> client: every persisted event
(message create/edit/delete, read/delivered cursors, reactions) is
published by the REST handler via ``channel_layer.group_send`` and
fanned to subscribers here.

The one client -> server frame this consumer accepts is **typing
indicators**, which are ephemeral (no DB write) and so do not justify a
REST round-trip. The wire shape is:

    Client -> server: {"type": "typing", "typing": true | false}

The consumer rate-limits each connection (``TYPING_RATE_LIMIT_SECONDS``)
so a stuck FE cannot flood Redis. Unknown ``type`` values are silently
dropped — never raise from ``receive_json``, since an exception tears
down the long-lived socket.

Wire protocol — every payload received by the client over the socket
has the same envelope:

    {
      "event": <one of below>,
      "type":  <same as event>,           # duplicated for FE convenience
      "group_id": <int>,
      "message_id": <int|null>,           # set on every message-scoped event
      ...event-specific fields...
    }

Event taxonomy:
  message.created              embeds  message: {...}
  message.edited               embeds  message: {...}  (is_edited=true)
  message.deleted              embeds  message: {...}  (is_deleted=true)
  message.reaction_updated     flat:   reactions: {...}
  message.read_updated         flat:   reader_id, up_to_id
  message.delivered_updated    flat:   user_id, up_to_id
  message.preview_ready        flat:   preview: {title, desc, img}
  user.typing                  flat:   user_id, user_name, typing
  mention.created              flat:   sender_user_id, preview (text snippet)

``mention.created`` is published to a per-user channel ``user_{id}``
that every authenticated connection joins on ``connect``. This means a
mention raised in group A reaches the recipient even if the only
socket they currently have open belongs to group B.

For deletes the embedded message has ``is_deleted=true`` and a non-null
``deleted_at`` so the front end can drive its UI from a single shape.
"""

import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.chat.models import Messages
from apps.chat.rbac import can_access_chat_group
from apps.chat.views import mark_delivered_cursor
from apps.groups.models import Groups


# Per-connection floor between two outbound typing fan-outs. A keystroke
# debounce on the FE keeps normal use well under this; the cap exists so
# a buggy client cannot turn the WS into an amplifier against Redis.
TYPING_RATE_LIMIT_SECONDS = 2.0


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
        # Per-user channel so mention pushes can reach the user
        # regardless of which group's WS they currently have open.
        # Stored on ``self`` for symmetric ``disconnect()`` cleanup.
        self.user_group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

        # Per-connection rate limit clock for typing fan-outs.
        self._last_typing_at = 0.0

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

    async def receive_json(self, content, **kwargs):
        """Handle client -> server frames.

        Only ``{"type": "typing", "typing": <bool>}`` is recognised; any
        other shape is dropped silently. Rate-limited per connection so
        a flooding client cannot DoS the Redis channel layer.
        """
        if not isinstance(content, dict):
            return
        if content.get("type") != "typing":
            return
        user = self.scope.get("user")
        if user is None or not getattr(user, "is_authenticated", False):
            return

        now = time.monotonic()
        if now - self._last_typing_at < TYPING_RATE_LIMIT_SECONDS:
            return
        self._last_typing_at = now

        typing = bool(content.get("typing", True))
        name = user.get_full_name() if hasattr(user, "get_full_name") else ""
        envelope = {
            "type": "chat.message",
            "payload": {
                "event": "user.typing",
                "type": "user.typing",
                "group_id": self.group_id,
                "user_id": user.id,
                "user_name": name,
                "typing": typing,
            },
        }
        await self.channel_layer.group_send(self.room_group_name, envelope)

    async def chat_message(self, event):
        # Mirror per-message live delivery: when this consumer forwards a
        # newly-created message to its client, also mark that message as
        # delivered for the connected user (skipping the sender, who has
        # no MessageStatus row of their own). Idempotent.
        payload = event.get("payload") or {}
        # Don't echo a user's own typing indicator back to them — the FE
        # already knows it's typing locally and showing "you are typing"
        # would be noise.
        if payload.get("event") == "user.typing":
            user = self.scope.get("user")
            if user is not None and payload.get("user_id") == getattr(user, "id", None):
                return
        if payload.get("event") == "message.created":
            user = self.scope.get("user")
            msg = payload.get("message") or {}
            sender_id = msg.get("sender_user")
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
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(
                self.user_group_name, self.channel_name
            )
