"""Celery tasks for chat-side background work.

Currently a single task: ``fetch_og_data``. The contract is fire-and-forget
from the view's perspective:

    fetch_og_data.delay(message_id, url)

The worker:

1. Looks up ``cache:og:<md5(url)>`` in Redis. If present, the URL was unfurled
   in the last 24h by *some* user — reuse the metadata, write it through to
   this message's preview row, and broadcast immediately. No outbound HTTP.

2. Otherwise, fetch the URL with a tight timeout, parse OG meta, persist a
   ``MessagePreview`` row, populate the cache (``setex`` with the 24h TTL),
   and broadcast.

Failures are swallowed and logged: a missing preview is a UX downgrade, never
an error visible to the user. Celery retries are deliberately *not* used —
most OG failures (404, blocked bot UA, malformed HTML) won't get better with
a retry, and the cost of pinning a worker on retry backoff outweighs the
recovery rate.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction

from .og_extractor import cache_key_for, parse_og_metadata
from .redis_client import get_redis


logger = logging.getLogger(__name__)


_PREVIEW_EVENT = "message.preview_ready"


def _broadcast_preview(group_id: int, message_id: int, preview: dict[str, str]) -> None:
    """Fan a preview-ready event out to every consumer for ``group_id``.

    Mirrors ``apps.chat.views._broadcast`` but uses the dedicated event name
    so the front end can render previews without interpreting it as a brand
    new message. The envelope ``type`` stays ``chat.message`` because that's
    the consumer handler the existing ``GroupChatConsumer`` dispatches on.
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
            "type": _PREVIEW_EVENT,
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
    response. The OG fetcher follows redirects so we hand the *final* URL back
    for relative-image resolution.
    """
    headers = {
        "User-Agent": getattr(
            settings,
            "LINK_PREVIEW_USER_AGENT",
            "BiotechFuturesBot/1.0",
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
                # Truncate rather than reject — the <head> with OG tags is
                # almost always within the first few KB, and a giant single
                # <body> (image gallery, etc.) shouldn't cost us the preview.
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


@shared_task(name="apps.chat.tasks.fetch_og_data", ignore_result=True)
def fetch_og_data(message_id: int, url: str) -> dict[str, Any]:
    """Resolve OG metadata for ``url`` and attach it to ``message_id``.

    Returns a small status dict mostly for the eager-mode unit tests; live
    callers ignore the return value.
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
