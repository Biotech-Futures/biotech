"""WebSocket consumer for the shared live note.

The note is a Yjs document edited by every group participant at once.
Unlike apps.chat, content does NOT go through REST: each client sends its
Yjs updates over this socket, the server merges them into the stored
document (``services.apply_note_update``) and relays them to the rest of
the room. ``GET /meetings/<id>/note/`` remains for a plain-text read.

Awareness (each member's name, colour and cursor) rides the same socket.
It is relayed only, never stored -- it is ephemeral, and clients drop a
peer's cursor on their own once it stops being renewed.

Binary payloads travel as base64 inside JSON frames, so this stays a JSON
consumer.

Client -> server:

    {"type": "update",    "update": "<base64 Yjs update>"}
    {"type": "awareness", "update": "<base64 awareness update>"}
    {"type": "presence",  "editing": true | false}

Server -> client:

    {"event": "note.sync",        "update": "<base64 full state>"}  on connect
    {"event": "note.update",      "update": "<base64 Yjs update>"}  others' edits
    {"event": "note.awareness",   "update": "<base64 awareness>"}   others' cursors
    {"event": "note.peer_joined"}                     someone connected
    {"event": "note.presence",    "meeting_id", "user_id", "editing"}

``note.peer_joined`` prompts existing clients to resend their awareness, so
a newcomer sees cursors immediately rather than at the next move.

Nothing is echoed back to its sender. Any other frame shape is dropped.
"""

import base64
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.common.rbac import group_participant_qs, is_admin

from . import services
from .models import GroupMeeting
from .services import meeting_channel_name

logger = logging.getLogger(__name__)

PRESENCE_RATE_LIMIT_SECONDS = 1.0
MAX_UPDATE_CHARS = 200_000
MAX_AWARENESS_CHARS = 10_000


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
        # Per-connection rate-limit clock for presence fan-outs.
        self._last_presence_at = 0.0
        await self.accept()

        state = await database_sync_to_async(services.get_note_state)(self.meeting_id)
        await self.send_json(
            {"event": "note.sync", "update": base64.b64encode(state).decode()}
        )
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "note.peer_joined", "sender": self.channel_name},
        )

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

        Never raise here -- an exception tears down the long-lived socket.
        """
        if not isinstance(content, dict):
            return
        frame_type = content.get("type")
        if frame_type == "update":
            await self._handle_update(content)
        elif frame_type == "awareness":
            await self._handle_awareness(content)
        elif frame_type == "presence":
            await self._handle_presence(content)

    async def _handle_update(self, content):
        raw = content.get("update")
        if not isinstance(raw, str) or len(raw) > MAX_UPDATE_CHARS:
            return
        try:
            update = base64.b64decode(raw, validate=True)
            await database_sync_to_async(services.apply_note_update)(
                self.meeting_id, self.scope["user"].id, update
            )
        except Exception:
            # Bad base64 or a corrupt Yjs update: drop it, keep the socket.
            logger.exception("Bad note update for meeting %s", self.meeting_id)
            return
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "note.update", "update": raw, "sender": self.channel_name},
        )

    async def _handle_awareness(self, content):
        # Relayed as-is: the server never decodes or stores awareness.
        raw = content.get("update")
        if not isinstance(raw, str) or len(raw) > MAX_AWARENESS_CHARS:
            return
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "note.awareness", "update": raw, "sender": self.channel_name},
        )

    async def _handle_presence(self, content):
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

    # -- channel-layer handlers ---------------------------------------------

    async def note_update(self, event):
        if event.get("sender") == self.channel_name:
            return
        await self.send_json({"event": "note.update", "update": event["update"]})

    async def note_awareness(self, event):
        if event.get("sender") == self.channel_name:
            return
        await self.send_json({"event": "note.awareness", "update": event["update"]})

    async def note_peer_joined(self, event):
        if event.get("sender") == self.channel_name:
            return
        await self.send_json({"event": "note.peer_joined"})

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
