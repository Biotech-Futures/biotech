"""A live room: who is typing where, what they have typed, and nudges that something changed.

Nothing here is stored; saving stays on each feature's own endpoints.

    Client -> server: {"type": "typing", "field": "<key>", "typing": true | false}
                      {"type": "text", "field": "<key>", "text": "<whole field>", "caret": <index>}
    Server -> client: {"type": "hello", "user": {"id", "name"}}
                      {"type": "typing", "user": {"id", "name"}, "field", "typing"}
                      {"type": "text", "user": {"id", "name"}, "field", "text", "caret"}
                      {"type": "changed", "item": "<key>", "user": {"id", "name"} | null}

Rooms whose kind keeps a shared document (see rooms.ROOM_DOCUMENTS) also carry Yjs updates, base64:
    Client -> server: {"type": "doc-sync", "vector": "<state vector>", "update": "<local changes>" | "", "generation"}
                      {"type": "doc-update", "update": "<update>", "generation"}
                      {"type": "doc-flush", "id": <n>}
    Server -> client: {"type": "doc-state", "update": "<missing>", "vector": "<server's>", "full": bool, "editable": bool}
                      {"type": "doc-update", "update": "<update>"}
                      {"type": "doc-reject"}       the last update was refused; resync from scratch
                      {"type": "doc-reset"}        the document was rebuilt; resync from scratch
                      {"type": "doc-flushed", "id": <n>, "ok": bool}
"generation" names the build the page's copy came from, or is null before it has one.
"""
import asyncio
import base64
import binascii
import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .rooms import can_join, document_for, person, room_name

logger = logging.getLogger(__name__)

# Floors per connection, so a faulty client cannot flood the channel layer.
MIN_FRAME_INTERVAL = 0.2
MIN_TYPING_INTERVAL = 1.0
MIN_TEXT_INTERVAL = 0.1
MAX_FIELD_LENGTH = 64
MAX_FIELDS = 100
# Far above any answer (150 words is about 1,000 characters), so normal pastes always pass.
MAX_TEXT_LENGTH = 20_000
# Shared-document updates: base64 of at most the document module's own limit, at a typist's pace.
MAX_DOC_MESSAGE_CHARS = 100_000
MAX_GENERATION_LENGTH = 64
MAX_DOC_UPDATES_PER_SECOND = 30
# A room's edits are saved this long after the first unsaved one, in one save whoever typed.
DOC_SAVE_DELAY = 2.0
# How long a room's save claim outlives a worker that died before saving.
DOC_SAVE_CLAIM_SECONDS = 10.0
# A connection reuses its "may edit" answer this long, so each edit does not query the database.
DOC_PERMISSION_SECONDS = 5.0
DOC_TYPES = ("doc-sync", "doc-update", "doc-flush")

# The save each room is waiting on in this process; it outlives the connection that claimed it.
_waiting_saves: dict[str, asyncio.Task] = {}


def _valid_generation(value) -> bool:
    return value is None or (isinstance(value, str) and 0 < len(value) <= MAX_GENERATION_LENGTH)


def _decode(value) -> bytes | None:
    """A base64 field as bytes; None when missing, too long or not base64."""
    if value in (None, ""):
        return b""
    if not isinstance(value, str) or len(value) > MAX_DOC_MESSAGE_CHARS:
        return None
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None


def _encode(value: bytes) -> str:
    return base64.b64encode(value).decode()


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
        self.room_id = room_id
        self.document = document_for(kind)
        self.user = person(user)
        self._doc_window = (0.0, 0)
        self._may_edit = (float("-inf"), False)
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
        if not isinstance(content, dict):
            return
        if content.get("type") in DOC_TYPES:
            await self._receive_doc(content)
            return
        if not _valid_field(content.get("field")):
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

    async def _receive_doc(self, content) -> None:
        document = self.document
        if document is None or not document.enabled():
            return
        user = self.scope["user"]
        try:
            if content["type"] == "doc-flush":
                ok = await database_sync_to_async(document.flush)(self.room_id)
                await self.send_json({"type": "doc-flushed", "id": content.get("id"), "ok": ok})
            elif content["type"] == "doc-sync":
                await self._sync_document(document, user, content)
            else:
                await self._update_document(document, user, content)
        except Exception:  # noqa: BLE001 - a failed step is retried from scratch by the page
            logger.exception("live.doc_failed room=%s", self.room)
            await self.send_json({"type": "doc-reject"})

    async def _sync_document(self, document, user, content) -> None:
        vector, local = _decode(content.get("vector")), _decode(content.get("update"))
        generation = content.get("generation")
        if vector is None or local is None or not _valid_generation(generation):
            await self.send_json({"type": "doc-reject"})
            return
        editable = await database_sync_to_async(self._may_edit_now)(user, True)
        # A copy of an earlier build is never merged; the page is sent the whole current one instead.
        accepted = generation is None or generation == await database_sync_to_async(document.generation)(self.room_id)
        if local and accepted:
            accepted = editable and await self._apply(document, user, local, generation)
            if accepted:
                await self._share_update(local)
        # Local changes that were refused must not linger in the page, so it starts again from the full state.
        missing, server_vector = await database_sync_to_async(document.state_since)(
            self.room_id, vector if accepted else None
        )
        await self.send_json({
            "type": "doc-state", "update": _encode(missing), "vector": _encode(server_vector),
            "full": not accepted, "editable": editable,
        })

    async def _update_document(self, document, user, content) -> None:
        started, count = self._doc_window
        now = time.monotonic()
        if now - started >= 1.0:
            started, count = now, 0
        self._doc_window = (started, count + 1)
        update = _decode(content.get("update"))
        generation = content.get("generation")
        # Refused rather than dropped, so the page resyncs instead of quietly diverging.
        if count + 1 > MAX_DOC_UPDATES_PER_SECOND or not update or not _valid_generation(generation):
            await self.send_json({"type": "doc-reject"})
            return
        if not await self._apply(document, user, update, generation):
            await self.send_json({"type": "doc-reject"})
            return
        await self._share_update(update)

    async def _apply(self, document, user, update: bytes, generation: str | None) -> bool:
        waiting = _waiting_saves.get(self.room)
        claim = waiting is None or waiting.done()
        accepted, claimed = await database_sync_to_async(self._apply_and_claim)(
            document, user, update, generation, claim
        )
        if claimed:
            _waiting_saves[self.room] = asyncio.ensure_future(_save_after_pause(document, self.room_id, self.room))
        return accepted

    def _apply_and_claim(self, document, user, update: bytes, generation, claim: bool) -> tuple[bool, bool]:
        # One trip to the worker thread for the permission, the edit and the room's next save.
        if not self._may_edit_now(user) or not document.apply(
            user, self.room_id, update, checked=True, generation=generation
        ):
            return False, False
        return True, claim and document.claim_save(self.room_id, DOC_SAVE_CLAIM_SECONDS)

    def _may_edit_now(self, user, fresh: bool = False) -> bool:
        checked_at, allowed = self._may_edit
        now = time.monotonic()
        if fresh or now - checked_at >= DOC_PERMISSION_SECONDS:
            allowed = self.document.can_edit(user, self.room_id)
            self._may_edit = (now, allowed)
        return allowed

    async def _share_update(self, update: bytes) -> None:
        await self.channel_layer.group_send(self.room, {
            "type": "room.doc", "update": _encode(update), "sender": self.channel_name,
        })

    async def room_doc(self, event):
        # Every other connection gets it, including the sender's other tabs.
        if event.get("sender") == self.channel_name:
            return
        await self.send_json({"type": "doc-update", "update": event["update"]})

    async def room_doc_reset(self, event):
        await self.send_json({"type": "doc-reset"})

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


async def _save_after_pause(document, room_id: int, room: str) -> None:
    await asyncio.sleep(DOC_SAVE_DELAY)
    # Edits from here on claim the next save, since this one may read the document before them.
    if _waiting_saves.get(room) is asyncio.current_task():
        del _waiting_saves[room]
    try:
        await database_sync_to_async(_release_and_save)(document, room_id)
    except Exception:  # noqa: BLE001 - the next save, or a flush before submitting, tries again
        logger.exception("live.doc_save_failed room=%s", room)


def _release_and_save(document, room_id: int) -> None:
    # Released before reading, so an edit landing during this save claims the one after it.
    document.release_save(room_id)
    document.save(room_id)
