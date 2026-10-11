"""A live room: who is typing where, what they have typed, and nudges that something changed.

Nothing here is stored; saving stays on each feature's own endpoints.

    Client -> server: {"type": "typing", "field": "<key>", "typing": true | false}
                      {"type": "text", "field": "<key>", "text": "<whole field>", "caret": <index>}
    Server -> client: {"type": "hello", "user": {"id", "name"}}
                      {"type": "typing", "user": {"id", "name"}, "field", "typing"}
                      {"type": "text", "user": {"id", "name"}, "field", "text", "caret"}
                      {"type": "changed", "item": "<key>", "user": {"id", "name"} | null}
"""
import asyncio
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .rooms import can_join, person, room_name

# Floors per connection, so a faulty client cannot flood the channel layer.
MIN_FRAME_INTERVAL = 0.2
MIN_TYPING_INTERVAL = 1.0
MIN_TEXT_INTERVAL = 0.1
MAX_FIELD_LENGTH = 64
MAX_FIELDS = 100
# Far above any answer (150 words is about 1,000 characters), so normal pastes always pass.
MAX_TEXT_LENGTH = 20_000


def _valid_field(field) -> bool:
    return isinstance(field, str) and 0 < len(field) <= MAX_FIELD_LENGTH


class LiveRoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        kwargs = self.scope["url_route"]["kwargs"]
        kind, room_id = kwargs["kind"], int(kwargs["room_id"])
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4403)
            return
        if not await database_sync_to_async(can_join)(kind, user, room_id):
            await self.close(code=4403)
            return

        self.room = room_name(kind, room_id)
        self.user = person(user)
        self._last_frame = 0.0
        self._last_typing: dict[str, float] = {}
        self._last_text: dict[str, float] = {}
        self._pending_text: dict[str, tuple[str, int]] = {}
        self._text_sends: dict[str, asyncio.Future] = {}
        self._open: set[str] = set()
        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()
        # Tells the page who it is, so it can settle two people starting on one field at once.
        await self.send_json({"type": "hello", "user": self.user})

    async def disconnect(self, code):
        if not getattr(self, "room", None):
            return
        for pending in self._text_sends.values():
            pending.cancel()
        for field, (text, caret) in list(self._pending_text.items()):
            await self._send_to_room("text", field, text=text, caret=caret)
        # Labels clear at once rather than waiting to expire.
        for field in self._open:
            await self._send_to_room("typing", field, typing=False)
        await self.channel_layer.group_discard(self.room, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Anything unexpected is dropped; raising here would close the socket.
        if not isinstance(content, dict) or not _valid_field(content.get("field")):
            return
        if content.get("type") == "typing":
            await self._receive_typing(content["field"], content.get("typing"))
        elif content.get("type") == "text":
            await self._receive_text(content["field"], content.get("text"), content.get("caret"))

    async def _receive_typing(self, field: str, typing) -> None:
        if not isinstance(typing, bool):
            return
        if typing:
            now = time.monotonic()
            if now - self._last_frame < MIN_FRAME_INTERVAL:
                return
            if now - self._last_typing.get(field, 0.0) < MIN_TYPING_INTERVAL:
                return
            if field not in self._open and len(self._open) >= MAX_FIELDS:
                return
            if len(self._last_typing) >= MAX_FIELDS:
                self._last_typing.clear()
            self._last_frame = now
            self._last_typing[field] = now
            self._open.add(field)
        elif field in self._open:
            # A stop only ends a start this connection made, so it needs no floor.
            self._open.discard(field)
        else:
            return
        await self._send_to_room("typing", field, typing=typing)

    async def _receive_text(self, field: str, text, caret) -> None:
        # Oversized text is not relayed; teammates still see the typing label.
        if not isinstance(text, str) or len(text) > MAX_TEXT_LENGTH:
            return
        # Where the typist's cursor is; anything unusable means "at the end".
        if isinstance(caret, bool) or not isinstance(caret, int) or not 0 <= caret <= len(text):
            caret = len(text)
        if field not in self._pending_text and len(self._pending_text) >= MAX_FIELDS:
            return
        # Text arriving too fast is held, not dropped, so the latest always reaches the room.
        self._pending_text[field] = (text, caret)
        if field in self._text_sends:
            return
        wait = MIN_TEXT_INTERVAL - (time.monotonic() - self._last_text.get(field, 0.0))
        self._text_sends[field] = asyncio.ensure_future(self._send_text(field, max(wait, 0.0)))

    async def _send_text(self, field: str, wait: float) -> None:
        if wait:
            await asyncio.sleep(wait)
        self._text_sends.pop(field, None)
        pending = self._pending_text.pop(field, None)
        if len(self._last_text) >= MAX_FIELDS:
            self._last_text.clear()
        self._last_text[field] = time.monotonic()
        if pending is not None:
            await self._send_to_room("text", field, text=pending[0], caret=pending[1])

    async def _send_to_room(self, kind: str, field: str, **values) -> None:
        await self.channel_layer.group_send(self.room, {
            "type": "room.relay", "kind": kind, "user": self.user, "field": field, **values,
        })

    async def room_relay(self, event):
        # Never echoed to the typist, including their other tabs.
        if event["user"]["id"] == self.user["id"]:
            return
        message = {key: value for key, value in event.items() if key not in ("type", "kind")}
        await self.send_json({"type": event["kind"], **message})

    async def room_changed(self, event):
        # Whoever made the change already sees it.
        if (event.get("user") or {}).get("id") == self.user["id"]:
            return
        await self.send_json({"type": "changed", "item": event["item"], "user": event.get("user")})
