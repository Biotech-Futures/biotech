"""A live room's shared document: Yjs updates merged on the server and saved by it.

For room kinds that keep one (rooms.ROOM_DOCUMENTS); the module named there does the merging and
saving, and this part of the connection carries its messages, base64:

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

logger = logging.getLogger(__name__)

DOC_TYPES = ("doc-sync", "doc-update", "doc-flush")
# Base64 of at most the document module's own limit, at a typist's pace.
MAX_DOC_MESSAGE_CHARS = 100_000
MAX_GENERATION_LENGTH = 64
MAX_DOC_UPDATES_PER_SECOND = 30
# A room's edits are saved this long after the first unsaved one, in one save whoever typed.
DOC_SAVE_DELAY = 2.0
# How long a room's save claim outlives a worker that died before saving.
DOC_SAVE_CLAIM_SECONDS = 10.0
# A connection reuses its "may edit" answer this long, so each edit does not query the database.
DOC_PERMISSION_SECONDS = 5.0

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


class SharedDocumentMixin:
    """The shared-document half of a live room's connection; needs self.room, self.room_id and send_json."""

    def _start_document(self, document) -> None:
        self.document = document
        self._doc_window = (0.0, 0)
        self._may_edit = (float("-inf"), False)

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
        if not self._may_edit_now(user):
            return False, False
        return document.apply_and_claim(self.room_id, update, generation, DOC_SAVE_CLAIM_SECONDS if claim else None)

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
