import json
import time

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.chat.models import Messages
from apps.chat.tasks import enqueue_process_chat_message_created
from apps.groups.models import GroupMembership

MAX_MESSAGE_BODY_LENGTH = 2000
TYPING_EVENT_DEBOUNCE_SECONDS = 1.0
INVALID_JSON_SENTINEL = "__invalid_json__"


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket contract:
      inbound:  {"type": "message.send", "body": "<text>"}
      inbound:  {"type": "typing.start"} / {"type": "typing.stop"}
      outbound: {"type": "message.created", "message": {...}}
      outbound: {"type": "typing.started", "conversation_id": <id>, "user_id": <id>}
      outbound: {"type": "typing.stopped", "conversation_id": <id>, "user_id": <id>}
      errors:   {"type": "error", "error": {"code": "...", "detail": "..."}}

    The consumer also listens to the older `group_<id>` channel-layer group so REST chat
    endpoints can keep broadcasting their existing payloads while the websocket route and
    client contract move to `conversation_id`.
    """

    async def connect(self):
        self.conversation_id = int(self.scope["url_route"]["kwargs"]["conversation_id"])
        # `conversation_<id>` is the primary group used by the new websocket contract.
        self.room_group_name = f"conversation_{self.conversation_id}"
        # `group_<id>` is kept as a compatibility bridge for existing REST broadcasts.
        self.legacy_room_group_name = f"group_{self.conversation_id}"

        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4403)
            return

        if not await self._is_participant(user.id):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.channel_layer.group_add(self.legacy_room_group_name, self.channel_name)
        await self.accept()
        # This state lives only for the lifetime of the socket connection.
        self._typing_started_last_sent_at = 0.0

    async def receive_json(self, content, **kwargs):
        if content == INVALID_JSON_SENTINEL:
            await self._send_error("invalid_json", "Malformed JSON payload.")
            return

        user = self.scope["user"]

        if not user.is_authenticated:
            await self._send_error("not_authenticated", "Authentication required.")
            return

        # Re-check membership on every event so an already-open socket cannot keep sending
        # after the user has been removed from the conversation.
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
        # Live websocket delivery happens before Celery enqueue so chat stays responsive
        # even if the broker is temporarily unavailable.
        #
        # `group_send` publishes an internal event onto the channel layer. Channels routes the
        # event to `chat_message_created` below because the `type` value is
        # `chat.message_created` -> method name `chat_message_created`.
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
        # Celery's `.delay()` API is synchronous at the call site: it just pushes a job onto the
        # broker and returns quickly. We still wrap it with `sync_to_async` because the consumer
        # itself is async and should not directly call sync functions on the event loop thread.
        await sync_to_async(enqueue_process_chat_message_created)(message_payload["id"])

    async def _handle_typing_event(self, outbound_type):
        if outbound_type == "typing.started" and self._should_debounce_typing_started():
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.typing_event",
                "payload": {
                    "type": outbound_type,
                    "conversation_id": self.conversation_id,
                    "user_id": self.scope["user"].id,
                },
                # Group fan-out is still used for typing, but the originating socket is
                # tagged so we can suppress the echo in chat_typing_event.
                "sender_channel_name": self.channel_name,
            },
        )

    def _should_debounce_typing_started(self):
        now = time.monotonic()
        if now - self._typing_started_last_sent_at < TYPING_EVENT_DEBOUNCE_SECONDS:
            return True
        self._typing_started_last_sent_at = now
        return False

    async def chat_message_created(self, event):
        # This handler name is derived from the `type` used in `group_send`.
        await self.send_json(event["payload"])

    async def chat_message(self, event):
        # Compatibility bridge for REST paths that still publish the older payload shape.
        await self.send_json(event["payload"])

    async def chat_typing_event(self, event):
        # Typing indicators are only intended for the other participants in the conversation.
        if event.get("sender_channel_name") == self.channel_name:
            return
        await self.send_json(event["payload"])

    async def disconnect(self, code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        if hasattr(self, "legacy_room_group_name"):
            await self.channel_layer.group_discard(self.legacy_room_group_name, self.channel_name)

    @classmethod
    async def decode_json(cls, text_data):
        try:
            return json.loads(text_data)
        except ValueError:
            return INVALID_JSON_SENTINEL

    @database_sync_to_async
    def _is_participant(self, user_id):
        # ORM work is wrapped with `database_sync_to_async` because Django's ORM is still
        # synchronous here, while the websocket consumer runs in an async context.
        return GroupMembership.objects.filter(
            user_id=user_id,
            group_id=self.conversation_id,
            left_at__isnull=True,
        ).exists()

    @database_sync_to_async
    def _create_message(self, user_id, body):
        # Message persistence stays on the request/socket path; Celery is only for follow-up
        # work after the message already exists in the database.
        message = Messages.objects.create(
            group_id=self.conversation_id,
            sender_user_id=user_id,
            message_text=body,
        )
        return {
            "id": message.id,
            "conversation_id": message.group_id,
            "sender_id": message.sender_user_id,
            "body": message.message_text,
            "created_at": message.sent_at.isoformat(),
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
