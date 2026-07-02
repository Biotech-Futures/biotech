"""Chat-side background work — no Celery, no extra service.

Public surface:

- ``fetch_og_data(message_id, url)`` — synchronous worker that does the actual
  Redis cache lookup, HTTP fetch, OG parse, DB write and WS broadcast.
- ``dispatch_og(message_id, url)`` — fire-and-forget dispatcher used by the
  view layer. Spawns a daemon thread so the request returns immediately. In
  tests (or when ``LINK_PREVIEW_DISPATCH_SYNC`` is true) it runs inline.

Why not Celery? The platform already runs Daphne (ASGI) + Redis + Django. A
chat link preview is a small, fault-tolerant piece of UX — if it never lands
the user simply sees a plain link. Spending a broker, a scheduler and a worker
fleet on this would be overkill. The Redis cache (``cache:og:<md5(url)>``)
still dedupes fetches across users, and the WebSocket broadcast still surfaces
the preview when it's ready.

Trade-off acknowledged: if the Daphne process restarts mid-fetch, that one
preview is lost. The message itself is already committed, so the user is
never blocked.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

import requests
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import connection, transaction

from .og_extractor import cache_key_for, parse_og_metadata
from .redis_client import get_redis


logger = logging.getLogger(__name__)


_PREVIEW_EVENT = "message.preview_ready"


def _broadcast_preview(group_id: int, message_id: int, preview: dict[str, str]) -> None:
    """Fan a preview-ready event out to every consumer for ``group_id``.

    Payload mirrors the contract every other chat event obeys:
    ``event`` + ``type`` (duplicated mirror), ``group_id``, ``message_id``,
    and the event-specific data. The duplication of ``event``/``type`` and
    the always-present ``group_id`` let the FE branch on a single key
    consistently across the whole taxonomy — see the wire-protocol block
    in ``apps.chat.management.consumers``.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:  # pragma: no cover - misconfig
        logger.warning(
            "channel layer not configured; dropping preview broadcast for "
            "message %s", message_id,
        )
        return

    envelope = {
        "type": "chat.message",
        "payload": {
            "event": _PREVIEW_EVENT,
            "type": _PREVIEW_EVENT,
            "group_id": group_id,
            "message_id": message_id,
            "preview": preview,
        },
    }
    async_to_sync(channel_layer.group_send)(f"group_{group_id}", envelope)


def _read_cached(url: str) -> dict[str, str] | None:
    """Return cached OG payload for ``url`` or ``None`` on miss / parse error.

    A corrupt cache entry (impossible under normal operation, but cheap to be
    defensive) is treated as a miss so we re-fetch and overwrite it.
    """
    redis_client = get_redis()
    try:
        raw = redis_client.get(cache_key_for(url))
    except Exception:  # pragma: no cover - redis transport failure
        logger.exception("redis get failed for url=%s; falling through", url)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("dropping malformed OG cache entry for %s", url)
        return None


def _write_cached(url: str, payload: dict[str, str]) -> None:
    """Best-effort cache write. Failures are logged but never raised — the
    DB write is the source of truth and the user already got their preview."""
    redis_client = get_redis()
    ttl = int(getattr(settings, "LINK_PREVIEW_CACHE_TTL_SECONDS", 86400))
    try:
        redis_client.setex(
            cache_key_for(url), ttl, json.dumps(payload).encode("utf-8")
        )
    except Exception:  # pragma: no cover - redis transport failure
        logger.exception("redis setex failed for url=%s", url)


def _fetch_html(url: str) -> tuple[str, str] | None:
    """Download ``url`` and return ``(final_url, html)``.

    Returns ``None`` for any non-2xx, non-HTML, oversized, or transport-error
    response. Follows redirects so we hand the *final* URL back for relative
    image resolution.
    """
    headers = {
        "User-Agent": getattr(
            settings,
            "LINK_PREVIEW_USER_AGENT",
            "BIOTechFuturesBot/1.0",
        ),
        "Accept": "text/html,application/xhtml+xml",
    }
    timeouts = (
        float(getattr(settings, "LINK_PREVIEW_FETCH_CONNECT_TIMEOUT", 3.0)),
        float(getattr(settings, "LINK_PREVIEW_FETCH_READ_TIMEOUT", 5.0)),
    )
    max_bytes = int(getattr(settings, "LINK_PREVIEW_MAX_BYTES", 512 * 1024))

    try:
        with requests.get(
            url,
            headers=headers,
            timeout=timeouts,
            allow_redirects=True,
            stream=True,
        ) as resp:
            if resp.status_code >= 400:
                return None
            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "html" not in content_type and "xml" not in content_type:
                return None
            body = resp.raw.read(max_bytes + 1, decode_content=True)
            if len(body) > max_bytes:
                body = body[:max_bytes]
            try:
                html = body.decode(resp.encoding or "utf-8", errors="replace")
            except (LookupError, UnicodeDecodeError):
                html = body.decode("utf-8", errors="replace")
            return resp.url, html
    except requests.RequestException as exc:
        logger.info("OG fetch failed for %s: %s", url, exc)
        return None


def _persist_and_broadcast(
    message_id: int, url: str, payload: dict[str, str]
) -> None:
    """Write the ``MessagePreview`` row and fan out a websocket event.

    The broadcast is deferred to ``transaction.on_commit`` so a rolled-back
    DB write never produces a phantom WS event — same pattern as the chat
    create/edit/delete paths in ``views.py``.
    """
    from .models import MessagePreview, Messages

    try:
        message = Messages.objects.only("id", "group_id").get(pk=message_id)
    except Messages.DoesNotExist:
        logger.info(
            "skipping preview for missing message id=%s (deleted?)", message_id
        )
        return

    with transaction.atomic():
        MessagePreview.objects.update_or_create(
            message=message,
            defaults={
                "url": url,
                "title": payload.get("title", ""),
                "description": payload.get("desc", ""),
                "image_url": payload.get("img", ""),
            },
        )
        group_id = message.group_id
        transaction.on_commit(
            lambda: _broadcast_preview(group_id, message_id, payload)
        )


def fetch_og_data(message_id: int, url: str) -> dict[str, Any]:
    """Resolve OG metadata for ``url`` and attach it to ``message_id``.

    Returns a status dict so callers (and tests) can verify which branch ran:
    ``cache_hit``, ``fetched``, or ``fetch_failed``.
    """
    cached = _read_cached(url)
    if cached is not None:
        _persist_and_broadcast(message_id, url, cached)
        return {"status": "cache_hit", "message_id": message_id}

    fetched = _fetch_html(url)
    if fetched is None:
        return {"status": "fetch_failed", "message_id": message_id}

    final_url, html = fetched
    payload = parse_og_metadata(html, base_url=final_url)
    _write_cached(url, payload)
    _persist_and_broadcast(message_id, url, payload)
    return {"status": "fetched", "message_id": message_id}


def _run_in_thread(message_id: int, url: str) -> None:
    """Thread target — runs the unfurl and closes the DB connection.

    Each thread gets its own implicit Django connection on first ORM call. We
    close it on exit so we don't leak connections under bursty link traffic.
    """
    try:
        fetch_og_data(message_id, url)
    except Exception:
        logger.exception(
            "link preview worker crashed for message=%s url=%s",
            message_id, url,
        )
    finally:
        try:
            connection.close()
        except Exception:  # pragma: no cover - defensive
            pass


def dispatch_og(message_id: int, url: str) -> threading.Thread | None:
    """Fire-and-forget the OG fetch.

    In production this spawns a daemon thread inside the ASGI worker so the
    HTTP response returns immediately. In tests
    (``LINK_PREVIEW_DISPATCH_SYNC=True``) it runs inline, so assertions on the
    resulting DB row / WS broadcast don't have to race a thread.
    """
    if getattr(settings, "LINK_PREVIEW_DISPATCH_SYNC", False):
        fetch_og_data(message_id, url)
        return None

    thread = threading.Thread(
        target=_run_in_thread,
        args=(message_id, url),
        name=f"og-preview-{message_id}",
        daemon=True,
    )
    thread.start()
    return thread
