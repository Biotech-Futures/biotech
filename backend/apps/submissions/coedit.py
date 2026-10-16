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
import time
import uuid
from collections import OrderedDict

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from pycrdt import Doc, Map, Text

from .models import Submission, SubmissionQuestion
from .services import deadline_for_group

logger = logging.getLogger(__name__)

TITLE_FIELD = "title"
ANSWER_PREFIX = "answer:"
# Each build of a document from the entry carries a fresh label, so a page's copy of an earlier
# build (Redis restarted, evicted or expired the room) is replaced rather than merged twice over.
GENERATION_ROOT = "meta"
GENERATION_KEY = "generation"
PROJECT_TITLE_MAX_LENGTH = 150
# Far above any answer, so only a faulty or hostile client reaches them.
MAX_UPDATE_BYTES = 64 * 1024
MAX_FIELD_CHARS = 20_000
# Merged into one base once this many updates have piled up.
COMPACT_AFTER = 200
# Rooms whose documents a worker keeps in memory, most recently used first.
CACHED_ROOMS = 256
# Refreshed on every write; the database is the record, so an expired document is simply rebuilt.
STATE_TTL_SECONDS = 14 * 24 * 3600
# A stuck Redis fails a call within this, well inside the page's wait for a save before submitting.
REDIS_TIMEOUT_SECONDS = 2.0
# Idle connections are checked before use, since Azure drops them silently after ten minutes.
REDIS_HEALTH_CHECK_SECONDS = 30


def enabled() -> bool:
    return bool(getattr(settings, "SUBMISSION_COEDITING_ENABLED", False))


def answer_field(key: str) -> str:
    return f"{ANSWER_PREFIX}{key}"


# The questions rarely change, so each worker remembers their fields briefly rather than querying
# the database on every edit; a change made in this worker is seen at once, elsewhere within this.
FIELDS_TTL_SECONDS = 30.0
_known_fields: tuple[float, tuple[str, ...]] | None = None
_fields_lock = threading.Lock()


def _fields() -> tuple[str, ...]:
    global _known_fields
    with _fields_lock:
        if _known_fields is not None and time.monotonic() - _known_fields[0] < FIELDS_TTL_SECONDS:
            return _known_fields[1]
    fields = (TITLE_FIELD, *(answer_field(q.key) for q in SubmissionQuestion.active()))
    with _fields_lock:
        _known_fields = (time.monotonic(), fields)
    return fields


def forget_fields(**_signal) -> None:
    global _known_fields
    with _fields_lock:
        _known_fields = None


post_save.connect(forget_fields, sender=SubmissionQuestion, dispatch_uid="coedit.forget_fields_on_save")
post_delete.connect(forget_fields, sender=SubmissionQuestion, dispatch_uid="coedit.forget_fields_on_delete")


# ---- Storage -------------------------------------------------------------------------------
# Besides its base and updates, a room keeps an epoch: a fresh token whenever the base is rebuilt
# or merged, so a worker's own copy knows whether reading on from where it stopped is still valid.


def _new_epoch() -> str:
    return uuid.uuid4().hex


class _MemoryStore:
    """One process's copy, for local development and tests without Redis."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict[int, dict] = {}
        self._claims: dict[int, float] = {}

    def snapshot(self, room: int):
        with self._lock:
            entry = self._data.get(room)
            if entry is None:
                return None, [], None, None
            return entry["base"], list(entry["updates"]), entry["saved"], entry["epoch"]

    def read(self, room: int):
        return self.snapshot(room)[:3]

    def read_since(self, room: int, epoch: str | None, start: int):
        with self._lock:
            entry = self._data.get(room)
            if entry is None or entry["epoch"] != epoch:
                return None, None
            return entry["saved"], entry["updates"][start:]

    def create(self, room: int, base: bytes, saved: str) -> None:
        with self._lock:
            self._data.setdefault(room, {"base": base, "updates": [], "saved": saved, "epoch": _new_epoch()})

    def append(self, room: int, update: bytes, claim_seconds: float | None = None) -> tuple[int, bool]:
        with self._lock:
            if room not in self._data:
                return 0, False
            self._data[room]["updates"].append(update)
            return len(self._data[room]["updates"]), claim_seconds is not None and self._claim(room, claim_seconds)

    def compact(self, room: int, merged: list[bytes], base: bytes) -> None:
        with self._lock:
            entry = self._data.get(room)
            # Skipped if the list no longer starts with exactly what was merged.
            if entry is not None and entry["updates"][: len(merged)] == merged:
                entry["base"] = base
                del entry["updates"][: len(merged)]
                entry["epoch"] = _new_epoch()

    def mark_saved(self, room: int, saved: str) -> None:
        with self._lock:
            if room in self._data:
                self._data[room]["saved"] = saved

    def replace(self, room: int, base: bytes, saved: str) -> None:
        with self._lock:
            self._data[room] = {"base": base, "updates": [], "saved": saved, "epoch": _new_epoch()}

    def exists(self, room: int) -> bool:
        with self._lock:
            return room in self._data

    def claim_save(self, room: int, seconds: float) -> bool:
        with self._lock:
            return self._claim(room, seconds)

    def _claim(self, room: int, seconds: float) -> bool:
        now = time.monotonic()
        if self._claims.get(room, 0.0) > now:
            return False
        self._claims[room] = now + seconds
        return True

    def release_save(self, room: int) -> None:
        with self._lock:
            self._claims.pop(room, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._claims.clear()


class _RedisStore:
    """Shared by every worker. Each room's keys share a hash tag, so clustered Redis keeps them together."""

    def __init__(self, url: str):
        import redis

        self._redis = redis.Redis.from_url(
            url,
            socket_timeout=REDIS_TIMEOUT_SECONDS,
            socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
            health_check_interval=REDIS_HEALTH_CHECK_SECONDS,
        )

    @staticmethod
    def _keys(room: int):
        tag = f"coedit:{{{room}}}"
        return f"{tag}:base", f"{tag}:updates", f"{tag}:saved"

    @staticmethod
    def _epoch_key(room: int) -> str:
        return f"coedit:{{{room}}}:epoch"

    def snapshot(self, room: int):
        base_key, updates_key, saved_key = self._keys(room)
        # One transaction, so a merge landing between the reads cannot pair an old base with a trimmed list.
        pipe = self._redis.pipeline(transaction=True)
        pipe.get(base_key).lrange(updates_key, 0, -1).get(saved_key).get(self._epoch_key(room))
        base, updates, saved, epoch = pipe.execute()
        return base, list(updates), saved.decode() if saved else None, epoch.decode() if epoch else None

    def read(self, room: int):
        return self.snapshot(room)[:3]

    def read_since(self, room: int, epoch: str | None, start: int):
        _, updates_key, saved_key = self._keys(room)
        pipe = self._redis.pipeline(transaction=True)
        pipe.get(self._epoch_key(room)).get(saved_key).lrange(updates_key, start, -1)
        current, saved, newer = pipe.execute()
        if current is None or epoch is None or current.decode() != epoch:
            return None, None
        return saved.decode() if saved else None, list(newer)

    def create(self, room: int, base: bytes, saved: str) -> None:
        base_key, _, saved_key = self._keys(room)
        # Only the first worker to build the document stores it, so its text is never added twice.
        if self._redis.set(base_key, base, nx=True, ex=STATE_TTL_SECONDS):
            pipe = self._redis.pipeline(transaction=True)
            pipe.set(saved_key, saved, ex=STATE_TTL_SECONDS)
            pipe.set(self._epoch_key(room), _new_epoch(), ex=STATE_TTL_SECONDS)
            pipe.execute()

    def append(self, room: int, update: bytes, claim_seconds: float | None = None) -> tuple[int, bool]:
        base_key, updates_key, saved_key = self._keys(room)
        pipe = self._redis.pipeline(transaction=True)
        pipe.rpush(updates_key, update)
        for key in (base_key, updates_key, saved_key, self._epoch_key(room)):
            pipe.expire(key, STATE_TTL_SECONDS)
        if claim_seconds is not None:
            # In the same trip, so a typist's edit costs two round trips to Redis rather than three.
            pipe.set(self._claim_key(room), 1, nx=True, px=int(claim_seconds * 1000))
        results = pipe.execute()
        return results[0], claim_seconds is not None and bool(results[-1])

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
                pipe.set(self._epoch_key(room), _new_epoch(), ex=STATE_TTL_SECONDS)
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
        pipe.set(self._epoch_key(room), _new_epoch(), ex=STATE_TTL_SECONDS)
        pipe.execute()

    def exists(self, room: int) -> bool:
        return bool(self._redis.exists(self._keys(room)[0]))

    @staticmethod
    def _claim_key(room: int) -> str:
        return f"coedit:{{{room}}}:saving"

    def claim_save(self, room: int, seconds: float) -> bool:
        return bool(self._redis.set(self._claim_key(room), 1, nx=True, px=int(seconds * 1000)))

    def release_save(self, room: int) -> None:
        self._redis.delete(self._claim_key(room))

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
    doc[GENERATION_ROOT] = Map({GENERATION_KEY: uuid.uuid4().hex})
    return doc.get_update()


def _generation(doc: Doc) -> str | None:
    if GENERATION_ROOT not in doc.keys():
        return None
    return doc.get(GENERATION_ROOT, type=Map).get(GENERATION_KEY)


def _texts(doc: Doc) -> dict[str, str]:
    return {field: str(doc.get(field, type=Text)) for field in _fields()}


def _read(room: int) -> tuple[bytes, list[bytes], str | None, str | None]:
    """The room's stored base, updates, saved digest and epoch, built from the entry the first time."""
    base, updates, saved, epoch = store().snapshot(room)
    if base is None:
        texts = _db_texts(Submission.objects.filter(group_id=room).first())
        store().create(room, _build(texts), _digest(texts))
        base, updates, saved, epoch = store().snapshot(room)
    return base, updates, saved, epoch


def _doc_from(base: bytes, updates: list[bytes]) -> Doc:
    doc = Doc()
    doc.apply_update(base)
    for update in updates:
        doc.apply_update(update)
    return doc


class _Copy:
    __slots__ = ("doc", "epoch", "seen")

    def __init__(self, doc: Doc, epoch: str | None, seen: int):
        self.doc, self.epoch, self.seen = doc, epoch, seen


# Each worker keeps the documents it serves, reading only the updates added since, so an edit costs
# one short Redis read rather than rebuilding the whole document. Held while a copy is used; a
# worker runs its document work on one thread anyway.
_copies: OrderedDict[int, _Copy] = OrderedDict()
_copies_lock = threading.RLock()


def _forget(room: int) -> None:
    """Drops this worker's copy, e.g. after a change to it was refused; the next read rebuilds it."""
    with _copies_lock:
        _copies.pop(room, None)


def _load(room: int) -> tuple[Doc, str | None]:
    """The room's document, up to date with every worker's updates; use it while holding _copies_lock."""
    with _copies_lock:
        copy = _copies.get(room)
        if copy is not None:
            saved, newer = store().read_since(room, copy.epoch, copy.seen)
            if newer is not None:
                for update in newer:
                    copy.doc.apply_update(update)
                copy.seen += len(newer)
                _copies.move_to_end(room)
                return copy.doc, saved
        base, updates, saved, epoch = _read(room)
        doc = _doc_from(base, updates)
        _copies[room] = _Copy(doc, epoch, len(updates))
        _copies.move_to_end(room)
        while len(_copies) > CACHED_ROOMS:
            _copies.popitem(last=False)
        return doc, saved


def _within_limits(doc: Doc) -> bool:
    allowed = set(_fields())
    if any(name not in allowed | {GENERATION_ROOT} for name in doc.keys()):
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


def generation(room: int) -> str | None:
    """The label of the room's current build; a page holding another must start again from it."""
    with _copies_lock:
        return _generation(_load(room)[0])


def state_since(room: int, state_vector: bytes | None) -> tuple[bytes, bytes]:
    """What a page is missing, and the server's state vector, so the page can send what the server lacks."""
    with _copies_lock:
        doc, _ = _load(room)
        missing = doc.get_update(state_vector) if state_vector else doc.get_update()
        return missing, doc.get_state()


def apply(user, room: int, update: bytes, checked: bool = False, generation: str | None = None) -> bool:
    """Adds one client update, if this user may edit and the result stays within limits.

    checked: the caller asked can_edit for this user moments ago, so it is not asked again.
    generation: the build the page's copy came from; an update from another build is refused.
    """
    if not (checked or can_edit(user, room)):
        return False
    return _apply(room, update, generation, None)[0]


def apply_and_claim(room: int, update: bytes, generation: str | None, claim_seconds: float | None) -> tuple[bool, bool]:
    """apply() for a live room that has checked can_edit itself; with claim_seconds, also claims the
    room's next save in the same trip to Redis. Returns (accepted, claimed).
    """
    return _apply(room, update, generation, claim_seconds)


def _apply(room: int, update: bytes, generation: str | None, claim_seconds: float | None) -> tuple[bool, bool]:
    if not update or len(update) > MAX_UPDATE_BYTES:
        return False, False
    with _copies_lock:
        doc, _ = _load(room)
        current = _generation(doc)
        if generation is not None and generation != current:
            return False, False
        try:
            doc.apply_update(update)
        except Exception:  # noqa: BLE001 - a malformed update is refused, not raised
            _forget(room)
            return False, False
        # A refused update has already reached this copy, so the copy is dropped with it.
        if not _within_limits(doc) or _generation(doc) != current:
            _forget(room)
            return False, False
        try:
            stored, claimed = store().append(room, update, claim_seconds)
        except Exception:
            _forget(room)
            raise
    if stored >= COMPACT_AFTER:
        _compact(room)
    return True, claimed


def _compact(room: int) -> None:
    """Merges the room's updates into its base, so a document read from scratch stays short."""
    base, updates, _ = store().read(room)
    if base is not None and len(updates) >= COMPACT_AFTER:
        # Only the updates read here are merged, and only dropped if nothing else changed meanwhile.
        store().compact(room, updates, _doc_from(base, updates).get_update())


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
        with _copies_lock:
            doc, saved = _load(room)
            texts = _texts(doc)
        current = _db_texts(submission)
        if saved is not None and _digest(current) != saved:
            _forget(room)
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


def release_save(room: int) -> None:
    """Frees the room's save claim, taken by apply_and_claim, so an edit landing meanwhile claims the next."""
    store().release_save(room)


def _replace_fields(room: int, texts: dict[str, str]) -> None:
    """Each field given becomes the text given, in the document and on every open page."""
    with _copies_lock:
        doc, _ = _load(room)
        before = doc.get_state()
        changed = False
        with doc.transaction():
            for field, value in texts.items():
                text = doc.get(field, type=Text)
                if str(text) != value:
                    del text[:]
                    text.insert(0, value)
                    changed = True
        if not changed:
            return
        update = doc.get_update(before)
        try:
            store().append(room, update)
        except Exception:
            _forget(room)
            raise
    broadcast_update(room, update)


def write_fields(room: int, texts: dict[str, str]) -> None:
    """Puts an admin's saved text into the document, after it has been written to the entry."""
    if not enabled() or not texts:
        return
    try:
        _replace_fields(room, texts)
        store().mark_saved(room, _digest(_db_texts(Submission.objects.filter(group_id=room).first())))
    except Exception:  # noqa: BLE001 - the entry is the record; the next save finds it newer and rebuilds from it
        logger.exception("coedit.write_fields_failed room=%s", room)


def take_typing(room: int, texts: dict[str, str]) -> bool:
    """Saves typing from a page that cannot hold the live connection, whole answer by whole answer.

    It goes into the document and is saved from there, so teammates see it live and the document
    stays the one writer. False when the document is out of reach or was rebuilt meanwhile; the
    caller then writes the text to the entry itself.
    """
    if not enabled() or not texts:
        return True
    try:
        _replace_fields(room, texts)
        return save(room)
    except Exception:  # noqa: BLE001 - the caller saves the text to the entry instead
        logger.exception("coedit.take_typing_failed room=%s", room)
        return False


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
