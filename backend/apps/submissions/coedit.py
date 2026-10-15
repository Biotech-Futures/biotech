"""Co-editing: a team's answers and title as one shared, live-merged document.

The document is a CRDT (pycrdt, compatible with Yjs in the browser), so concurrent edits merge
without loss. It is kept outside the database - in Redis when configured, so every server worker
sees the same copy - and the server is the only writer of its text to the database.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import threading

from django.conf import settings
from django.db import transaction
from pycrdt import Doc, Text

from .models import Submission, SubmissionQuestion
from .services import deadline_for_group

logger = logging.getLogger(__name__)

TITLE_FIELD = "title"
ANSWER_PREFIX = "answer:"
PROJECT_TITLE_MAX_LENGTH = 150
# Far above any answer, so only a faulty or hostile client reaches them.
MAX_UPDATE_BYTES = 64 * 1024
MAX_FIELD_CHARS = 20_000
# Merged into one base once this many updates have piled up.
COMPACT_AFTER = 200
# Refreshed on every write; the database is the record, so an expired document is simply rebuilt.
STATE_TTL_SECONDS = 14 * 24 * 3600


def enabled() -> bool:
    return bool(getattr(settings, "SUBMISSION_COEDITING_ENABLED", False))


def answer_field(key: str) -> str:
    return f"{ANSWER_PREFIX}{key}"


def _fields() -> list[str]:
    return [TITLE_FIELD] + [answer_field(q.key) for q in SubmissionQuestion.active()]


# ---- Storage -------------------------------------------------------------------------------


class _MemoryStore:
    """One process's copy, for local development and tests without Redis."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict[int, dict] = {}

    def read(self, room: int):
        with self._lock:
            entry = self._data.get(room)
            if entry is None:
                return None, [], None
            return entry["base"], list(entry["updates"]), entry["saved"]

    def create(self, room: int, base: bytes, saved: str) -> None:
        with self._lock:
            self._data.setdefault(room, {"base": base, "updates": [], "saved": saved})

    def append(self, room: int, update: bytes) -> None:
        with self._lock:
            if room in self._data:
                self._data[room]["updates"].append(update)

    def compact(self, room: int, merged: list[bytes], base: bytes) -> None:
        with self._lock:
            entry = self._data.get(room)
            # Skipped if the list no longer starts with exactly what was merged.
            if entry is not None and entry["updates"][: len(merged)] == merged:
                entry["base"] = base
                del entry["updates"][: len(merged)]

    def mark_saved(self, room: int, saved: str) -> None:
        with self._lock:
            if room in self._data:
                self._data[room]["saved"] = saved

    def replace(self, room: int, base: bytes, saved: str) -> None:
        with self._lock:
            self._data[room] = {"base": base, "updates": [], "saved": saved}

    def exists(self, room: int) -> bool:
        with self._lock:
            return room in self._data

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class _RedisStore:
    """Shared by every worker. Each room's keys share a hash tag, so clustered Redis keeps them together."""

    def __init__(self, url: str):
        import redis

        self._redis = redis.Redis.from_url(url)

    @staticmethod
    def _keys(room: int):
        tag = f"coedit:{{{room}}}"
        return f"{tag}:base", f"{tag}:updates", f"{tag}:saved"

    def read(self, room: int):
        base_key, updates_key, saved_key = self._keys(room)
        pipe = self._redis.pipeline(transaction=False)
        pipe.get(base_key).lrange(updates_key, 0, -1).get(saved_key)
        base, updates, saved = pipe.execute()
        return base, list(updates), saved.decode() if saved else None

    def create(self, room: int, base: bytes, saved: str) -> None:
        base_key, _, saved_key = self._keys(room)
        # Only the first worker to build the document stores it, so its text is never added twice.
        if self._redis.set(base_key, base, nx=True, ex=STATE_TTL_SECONDS):
            self._redis.set(saved_key, saved, ex=STATE_TTL_SECONDS)

    def append(self, room: int, update: bytes) -> None:
        base_key, updates_key, saved_key = self._keys(room)
        pipe = self._redis.pipeline(transaction=True)
        pipe.rpush(updates_key, update)
        for key in (base_key, updates_key, saved_key):
            pipe.expire(key, STATE_TTL_SECONDS)
        pipe.execute()

    def compact(self, room: int, merged: list[bytes], base: bytes) -> None:
        import redis

        base_key, updates_key, _ = self._keys(room)
        with self._redis.pipeline() as pipe:
            try:
                # Any write to either key before EXEC cancels the swap, so no unmerged update is dropped.
                pipe.watch(base_key, updates_key)
                if pipe.lrange(updates_key, 0, len(merged) - 1) != merged:
                    pipe.unwatch()
                    return
                pipe.multi()
                pipe.set(base_key, base, ex=STATE_TTL_SECONDS)
                pipe.ltrim(updates_key, len(merged), -1)
                pipe.execute()
            except redis.WatchError:
                # Someone wrote meanwhile; compacting is only tidying, so it waits for the next time.
                pass

    def mark_saved(self, room: int, saved: str) -> None:
        _, _, saved_key = self._keys(room)
        self._redis.set(saved_key, saved, ex=STATE_TTL_SECONDS)

    def replace(self, room: int, base: bytes, saved: str) -> None:
        base_key, updates_key, saved_key = self._keys(room)
        pipe = self._redis.pipeline(transaction=True)
        pipe.set(base_key, base, ex=STATE_TTL_SECONDS)
        pipe.delete(updates_key)
        pipe.set(saved_key, saved, ex=STATE_TTL_SECONDS)
        pipe.execute()

    def exists(self, room: int) -> bool:
        return bool(self._redis.exists(self._keys(room)[0]))

    def clear(self) -> None:
        for key in self._redis.scan_iter(match="coedit:*"):
            self._redis.delete(key)


_store = None
_store_lock = threading.Lock()


def store():
    global _store
    with _store_lock:
        if _store is None:
            url = getattr(settings, "REDIS_URL", "")
            _store = _RedisStore(url) if url else _MemoryStore()
        return _store


# ---- Document helpers ----------------------------------------------------------------------


def _db_texts(submission: Submission | None) -> dict[str, str]:
    answers = (submission.answers or {}) if submission else {}
    texts = {TITLE_FIELD: submission.project_title if submission else ""}
    for question in SubmissionQuestion.active():
        texts[answer_field(question.key)] = answers.get(question.key, "") or ""
    return texts


def _digest(texts: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(texts, sort_keys=True).encode()).hexdigest()


def _build(texts: dict[str, str]) -> bytes:
    doc = Doc()
    for field, value in texts.items():
        doc[field] = Text(value)
    return doc.get_update()


def _texts(doc: Doc) -> dict[str, str]:
    return {field: str(doc.get(field, type=Text)) for field in _fields()}


def _read(room: int) -> tuple[bytes, list[bytes], str | None]:
    """The room's stored base and updates, built from the saved entry the first time they are needed."""
    base, updates, saved = store().read(room)
    if base is None:
        texts = _db_texts(Submission.objects.filter(group_id=room).first())
        store().create(room, _build(texts), _digest(texts))
        base, updates, saved = store().read(room)
    return base, updates, saved


def _doc_from(base: bytes, updates: list[bytes]) -> Doc:
    doc = Doc()
    doc.apply_update(base)
    for update in updates:
        doc.apply_update(update)
    return doc


def _load(room: int) -> tuple[Doc, str | None]:
    base, updates, saved = _read(room)
    return _doc_from(base, updates), saved


def _within_limits(doc: Doc) -> bool:
    allowed = set(_fields())
    if any(name not in allowed for name in doc.keys()):
        return False
    return all(len(str(doc.get(field, type=Text))) <= MAX_FIELD_CHARS for field in allowed)


# ---- What the live room asks for -----------------------------------------------------------


def can_edit(user, room: int) -> bool:
    """Teams type into the shared document while their entry is open; admins edit privately instead."""
    from .views import _is_staff  # views imports this module

    if not enabled() or _is_staff(user):
        return False
    submission = Submission.objects.filter(group_id=room).first()
    if submission is not None and submission.is_locked:
        return False
    return deadline_for_group(room).is_open


def state_since(room: int, state_vector: bytes | None) -> tuple[bytes, bytes]:
    """What a page is missing, and the server's state vector, so the page can send what the server lacks."""
    doc, _ = _load(room)
    missing = doc.get_update(state_vector) if state_vector else doc.get_update()
    return missing, doc.get_state()


def apply(user, room: int, update: bytes) -> bool:
    """Adds one client update, if this user may edit and the result stays within limits."""
    if not update or len(update) > MAX_UPDATE_BYTES or not can_edit(user, room):
        return False
    base, updates, _ = _read(room)
    doc = _doc_from(base, updates)
    try:
        doc.apply_update(update)
    except Exception:  # noqa: BLE001 - a malformed update is refused, not raised
        return False
    if not _within_limits(doc):
        return False
    store().append(room, update)
    if len(updates) + 1 >= COMPACT_AFTER:
        # Only the updates read above are merged, and only dropped if nothing else changed meanwhile.
        store().compact(room, updates, _doc_from(base, updates).get_update())
    return True


def save(room: int) -> bool:
    """Writes the document's text to the entry; the single writer while co-editing is on.

    Returns False when nothing could be written: a submitted entry, or one changed outside the
    document (it then wins, and the document is rebuilt from it).
    """
    if not store().exists(room):
        return True
    questions = {q.key: q for q in SubmissionQuestion.active()}
    with transaction.atomic():
        submission, created = Submission.objects.select_for_update().get_or_create(group_id=room)
        if submission.is_locked:
            return False
        # Read under the row lock, so a save that finished meanwhile is not taken for an outside change.
        doc, saved = _load(room)
        texts = _texts(doc)
        current = _db_texts(submission)
        if saved is not None and _digest(current) != saved:
            store().replace(room, _build(current), _digest(current))
            transaction.on_commit(lambda: broadcast_reset(room))
            return False
        answers = dict(submission.answers or {})
        # Saved as typed, over its word limit or not, so the entry is always the team's real draft;
        # the limit is checked when the entry is submitted.
        for key in questions:
            answers[key] = texts[answer_field(key)]
        title = texts[TITLE_FIELD]
        if len(title) <= PROJECT_TITLE_MAX_LENGTH:
            submission.project_title = title
        submission.answers = answers
        written = _db_texts(submission)
        if written != current or created:
            submission.save()
        store().mark_saved(room, _digest(written))
    if created:
        transaction.on_commit(lambda: _notify_changed(room))
    return True


def flush(room: int) -> bool:
    """Saves at once, before anything reads the entry's text (submit, auto-submit)."""
    if not enabled():
        return True
    try:
        return save(room)
    except Exception:  # noqa: BLE001 - the saved entry stands; the next save tries again
        logger.exception("coedit.flush_failed room=%s", room)
        return False


def write_fields(room: int, texts: dict[str, str]) -> None:
    """Puts an admin's saved text into the document, after it has been written to the entry."""
    if not enabled() or not texts:
        return
    doc, _ = _load(room)
    before = doc.get_state()
    with doc.transaction():
        for field, value in texts.items():
            text = doc.get(field, type=Text)
            if str(text) != value:
                del text[:]
                text.insert(0, value)
    update = doc.get_update(before)
    store().append(room, update)
    store().mark_saved(room, _digest(_db_texts(Submission.objects.filter(group_id=room).first())))
    broadcast_update(room, update)


# ---- Telling the room ----------------------------------------------------------------------


def _group_send(room: int, event: dict) -> None:
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from apps.live.rooms import room_name

    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(room_name("submission", room), event)
    except Exception:  # noqa: BLE001 - best effort; pages catch up on their next sync
        logger.warning("coedit.broadcast_failed room=%s", room, exc_info=True)


def broadcast_update(room: int, update: bytes) -> None:
    _group_send(room, {"type": "room.doc", "update": base64.b64encode(update).decode(), "sender": None})


def broadcast_reset(room: int) -> None:
    _group_send(room, {"type": "room.doc_reset"})


def _notify_changed(room: int) -> None:
    from apps.live.broadcast import notify_changed

    notify_changed("submission", room, "draft")
