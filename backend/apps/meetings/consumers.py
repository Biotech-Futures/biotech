"""WebSocket consumer for the shared live note.

Mirrors the split apps.chat uses: the REST handler persists, the socket is
pure fan-out. The only client -> server frame accepted here is an ephemeral
presence ping (no DB write, so no REST round-trip is justified). Note
*content* always goes through ``PATCH /meetings/<id>/note/`` so the
revision check runs -- writing to the DB on every keystroke from the
consumer will not hold up.

    Client -> server: {"type": "presence", "editing": true | false}

Server -> client envelope:

    {"event": "note.updated",  "meeting_id", "body", "revision", ...}
    {"event": "note.presence", "meeting_id", "user_id", "editing"}
"""

import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.common.rbac import group_participant_qs, is_admin

from .models import GroupMeeting
from .services import meeting_channel_name


PRESENCE_RATE_LIMIT_SECONDS = 1.0


class MeetingNoteConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        url_route = self.scope.get("url_route") or {}
        raw_id = (url_route.get("kwargs") or {}).get("meeting_id")
        try:
            self.meeting_id = int(raw_id)
        except (TypeError, ValueError):
            await self.close(code=4400)
            return

        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4403)
            return
        if not await self._can_access(user):
            await self.close(code=4403)
            return

        self.room_group_name = meeting_channel_name(self.meeting_id)
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        # Per-connection rate-limit clock for presence fan-outs.
        self._last_presence_at = 0.0

    @database_sync_to_async
    def _can_access(self, user):
        # A cancelled meeting or deleted group accepts no subscribers,
        # including former members.
        row = (
            GroupMeeting.objects.filter(
                pk=self.meeting_id,
                event__deleted_at__isnull=True,
                group__deleted_at__isnull=True,
            )
            .values("group_id")
            .first()
        )
        if row is None:
            return False
        if is_admin(user):
            return True
        return group_participant_qs(user, row["group_id"]).exists()

    async def receive_json(self, content, **kwargs):
        """Handle client -> server frames.

        Only presence is recognised; any other shape is dropped. Never raise
        here -- an exception tears down the long-lived socket.
        """
        if not isinstance(content, dict):
            return
        if content.get("type") != "presence":
            return
        user = self.scope.get("user")
        if user is None or not getattr(user, "is_authenticated", False):
            return

        now = time.monotonic()
        if now - self._last_presence_at < PRESENCE_RATE_LIMIT_SECONDS:
            return
        self._last_presence_at = now

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "meeting.event",
                "payload": {
                    "event": "note.presence",
                    "type": "note.presence",
                    "meeting_id": self.meeting_id,
                    "user_id": user.id,
                    "editing": bool(content.get("editing", True)),
                },
            },
        )

    async def meeting_event(self, event):
        payload = event.get("payload") or {}
        # Don't echo a user's own presence ping back at them.
        if payload.get("event") == "note.presence":
            user = self.scope.get("user")
            if user is not None and payload.get("user_id") == getattr(user, "id", None):
                return
        await self.send_json(payload)

    async def disconnect(self, code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )
