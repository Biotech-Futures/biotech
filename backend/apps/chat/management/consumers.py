import json
import time

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

import redis.asyncio as aioredis
from decouple import config

from apps.chat.contracts import build_chat_message_payload
from apps.chat.models import MessageStatus, Messages
from apps.chat.tasks import enqueue_process_chat_message_created
from apps.groups.models import GroupMembership

MAX_MESSAGE_BODY_LENGTH = 2000
TYPING_EVENT_DEBOUNCE_SECONDS = 1.0
INVALID_JSON_SENTINEL = "__invalid_json__"
TYPING_RATE_LIMIT_SECONDS = 2


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    Canonical WebSocket contract:
      inbound:  {"type": "message.send", "body": "<text>"}
      inbound:  {"type": "message.read", "message_id": <id>}
      inbound:  {"type": "typing.start"} / {"type": "typing.stop"}
      outbound: {"type": "message.created", "message": {...}}
      outbound: {"type": "message.read", "conversation_id": <id>, "message_id": <id>, ...}
      outbound: {"type": "typing.started", "conversation_id": <id>, "user_id": <id>}
      outbound: {"type": "typing.stopped", "conversation_id": <id>, "user_id": <id>}
      errors:   {"type": "error", "error": {"code": "...", "detail": "..."}}
    """

    _redis = None

    @classmethod
    async def get_redis(cls):
        """Return a shared async Redis client, creating it on first use."""
        redis_url = config("REDIS_URL", default=None)
        if not redis_url:
            return None
        if cls._redis is None:
            cls._redis = aioredis.from_url(redis_url, decode_responses=True)
        return cls._redis

    async def connect(self):
        self.conversation_id = int(self.scope["url_route"]["kwargs"]["conversation_id"])
        self.room_group_name = f"conversation_{self.conversation_id}"

        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4403)
            return

        if not await self._is_participant(user.id):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        self._typing_started_last_sent_at = 0.0

    async def receive_json(self, content, **kwargs):
        if content == INVALID_JSON_SENTINEL:
            await self._send_error("invalid_json", "Malformed JSON payload.")
            return

        user = self.scope["user"]

        if not user.is_authenticated:
            await self._send_error("not_authenticated", "Authentication required.")
            return

        if not await self._is_participant(user.id):
            await self._send_error("not_participant", "You are not a participant in this conversation.")
            return

        if not isinstance(content, dict):
            await self._send_error("invalid_payload", "Payload must be a JSON object.")
            return

        event_type = content.get("type")
        if event_type == "message.send":
            await self._handle_message_send(user.id, content)
            return

        if event_type == "message.read":
            await self._handle_message_read(user.id, content)
            return

        if event_type == "typing.start":
            await self._handle_typing_event("typing.started")
            return

        if event_type == "typing.stop":
            await self._handle_typing_event("typing.stopped")
            return

        await self._send_error("invalid_payload", "Unsupported event type.")

    async def _handle_message_send(self, user_id, content):
        body = content.get("body")
        if not isinstance(body, str):
            await self._send_error("invalid_payload", "Message body must be a string.")
            return

        body = body.strip()
        if not body:
            await self._send_error("invalid_payload", "Message body cannot be empty.")
            return

        if len(body) > MAX_MESSAGE_BODY_LENGTH:
            await self._send_error(
                "invalid_payload",
                f"Message body must be at most {MAX_MESSAGE_BODY_LENGTH} characters.",
            )
            return

        message_payload = await self._create_message(user_id, body)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message_created",
                "payload": {
                    "type": "message.created",
                    "message": message_payload,
                },
            },
        )
        await sync_to_async(enqueue_process_chat_message_created)(message_payload["id"])

    async def _handle_message_read(self, user_id, content):
        message_id = content.get("message_id")
        # `bool` is a subclass of `int` in Python, so reject it explicitly instead of silently
        # treating `true`/`false` as message ids `1`/`0`.
        if isinstance(message_id, bool):
            message_id = None

        try:
            message_id = int(message_id)
        except (TypeError, ValueError):
            await self._send_error("invalid_payload", "message_id must be an integer.")
            return

        receipt_payload = await self._mark_message_read(user_id, message_id)
        if receipt_payload is None:
            # Keep the error generic to avoid leaking whether a message exists in some other
            # conversation the current socket should not be able to inspect.
            await self._send_error("not_found", "Message not found in this conversation.")
            return

        # Read receipts are lightweight state updates, so the current implementation simply
        # fan-outs the normalized state to every socket in the conversation, including the
        # reader, instead of introducing a separate acknowledgement path.
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message_read",
                "payload": {
                    "type": "message.read",
                    **receipt_payload,
                },
            },
        )

    async def _handle_typing_event(self, outbound_type):
        if outbound_type == "typing.started":
            rate_key = f"typing_rate_limit:{self.conversation_id}:{self.scope['user'].id}"
            redis = await self.get_redis()
            if redis is not None:
                acquired = await redis.set(rate_key, 1, nx=True, ex=TYPING_RATE_LIMIT_SECONDS)
                if not acquired:
                    return
            elif self._should_debounce_typing_started():
                return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.typing_event",
                "payload": {
                    "type": outbound_type,
                    "conversation_id": self.conversation_id,
                    "user_id": self.scope["user"].id,
                    "user_name": self.scope["user"].get_full_name().strip() or self.scope["user"].email,
                },
                "sender_channel_name": self.channel_name,
            },
        )

    def _should_debounce_typing_started(self):
        now = time.monotonic()
        last = getattr(self, "_typing_started_last_sent_at", 0.0)
        if now - last < TYPING_EVENT_DEBOUNCE_SECONDS:
            return True
        self._typing_started_last_sent_at = now
        return False

    async def chat_message_created(self, event):
        await self.send_json(event["payload"])

    async def chat_message(self, event):
        await self.send_json(event["payload"])

    async def chat_message_read(self, event):
        # Read-receipt fan-out uses the same `group_send` -> handler-name convention as the
        # message-created path; the payload is already normalized by `_handle_message_read`.
        await self.send_json(event["payload"])

    async def chat_typing_event(self, event):
        if event.get("sender_channel_name") == self.channel_name:
            return
        await self.send_json(event["payload"])

    async def disconnect(self, code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    @classmethod
    async def decode_json(cls, text_data):
        try:
            return json.loads(text_data)
        except ValueError:
            return INVALID_JSON_SENTINEL

    @database_sync_to_async
    def _is_participant(self, user_id):
        return GroupMembership.objects.filter(
            user_id=user_id,
            group_id=self.conversation_id,
            left_at__isnull=True,
        ).exists()

    @database_sync_to_async
    def _create_message(self, user_id, body):
        message = Messages.objects.create(
            group_id=self.conversation_id,
            sender_user_id=user_id,
            message_text=body,
        )
        message = Messages.objects.select_related("sender_user").prefetch_related(
            "resources__resource", "reactions", "statuses"
        ).get(pk=message.pk)
        return build_chat_message_payload(message)

    @database_sync_to_async
    def _mark_message_read(self, user_id, message_id):
        try:
            message = Messages.objects.get(
                pk=message_id,
                group_id=self.conversation_id,
                deleted_at__isnull=True,
            )
        except Messages.DoesNotExist:
            return None

        # The existing model is already "one message / one user", which is enough for the
        # current requirement. This deliberately avoids introducing per-device tracking.
        # The status row may already exist from the message-created side-effect path, but a
        # get_or_create keeps read receipts working even if Celery is delayed or unavailable.
        status, _ = MessageStatus.objects.get_or_create(
            message=message,
            user_id=user_id,
            defaults={"status": MessageStatus.StatusChoices.SENT},
        )
        status.mark_read()

        return {
            "conversation_id": message.group_id,
            "message_id": message.id,
            "user_id": user_id,
            "read_at": status.read_at.isoformat(),
        }

    async def _send_error(self, code, detail):
        await self.send_json(
            {
                "type": "error",
                "error": {
                    "code": code,
                    "detail": detail,
                },
            }
        )
