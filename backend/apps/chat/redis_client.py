"""Pooled Redis client used for chat-side caches (link previews today,
read-throughs and rate-limiters in the future).

A single ``ConnectionPool`` is created lazily on first use and shared by every
caller. Per Redis best practice, opening a fresh ``redis.Redis(...)`` per
request would burn an order of magnitude of latency on the TCP/AUTH handshake.

We deliberately keep this independent of the Channels redis layer (which has
its own pool tuned for pub/sub fan-out) so that a flood of OG fetches cannot
starve websocket broadcast capacity.

If ``REDIS_URL`` is unset (e.g. local dev without Redis, or unit tests that
mock at a higher layer) the module exposes a minimal in-process fallback so
that callers can still ``get`` / ``setex`` without conditional imports
sprinkled through the codebase. The fallback is intentionally non-persistent
and process-local — never use it in production.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import redis
from django.conf import settings


_pool_lock = threading.Lock()
_pool: Optional[redis.ConnectionPool] = None
_fallback: Optional["_InMemoryRedis"] = None


class _InMemoryRedis:
    """Tiny subset of the redis-py surface used by this codebase.

    Only ``get``, ``setex``, and ``delete`` are implemented because that's all
    link-preview caching needs. TTLs are honoured lazily (checked on read).
    Thread-safe via a single mutex — fine for the test/dev volumes this is
    meant to handle.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, tuple[bytes, float | None]] = {}

    def get(self, key: str) -> Optional[bytes]:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at is not None and expires_at <= time.monotonic():
                self._data.pop(key, None)
                return None
            return value

    def setex(self, key: str, ttl_seconds: int, value: bytes | str) -> bool:
        if isinstance(value, str):
            value = value.encode("utf-8")
        expires_at = time.monotonic() + ttl_seconds if ttl_seconds > 0 else None
        with self._lock:
            self._data[key] = (value, expires_at)
        return True

    def delete(self, key: str) -> int:
        with self._lock:
            return 1 if self._data.pop(key, None) is not None else 0


def _build_pool(url: str) -> redis.ConnectionPool:
    """Build the shared pool with sensible timeouts.

    ``socket_connect_timeout`` is tighter than ``socket_timeout`` so a dead
    Redis is detected quickly without truncating in-flight reads.
    """
    return redis.ConnectionPool.from_url(
        url,
        max_connections=int(getattr(settings, "REDIS_MAX_CONNECTIONS", 50)),
        socket_connect_timeout=float(
            getattr(settings, "REDIS_CONNECT_TIMEOUT", 2.0)
        ),
        socket_timeout=float(getattr(settings, "REDIS_SOCKET_TIMEOUT", 5.0)),
        retry_on_timeout=True,
        decode_responses=False,
    )


def get_redis() -> "redis.Redis | _InMemoryRedis":
    """Return a process-wide Redis client, creating the pool on first call."""
    global _pool, _fallback

    url = getattr(settings, "REDIS_URL", "") or ""
    if not url:
        if _fallback is None:
            _fallback = _InMemoryRedis()
        return _fallback

    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = _build_pool(url)

    return redis.Redis(connection_pool=_pool)


def reset_for_tests() -> None:
    """Drop any cached pool / fallback. Call from test ``setUp`` / ``tearDown``
    if you flip ``REDIS_URL`` mid-process."""
    global _pool, _fallback
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.disconnect()
            except Exception:  # pragma: no cover - defensive
                pass
        _pool = None
    _fallback = None
