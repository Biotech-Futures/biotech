import json
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.chat.contracts import build_chat_message_payload
from apps.chat.models import MessageStatus, Messages
from apps.chat.utils import sanitize_text
from apps.groups.models import GroupMembership
from apps.users.utils.roles import get_active_assignment

INVALID_JSON_SENTINEL = "__invalid_json__"
MAX_MESSAGE_BODY_LENGTH = 2000
ROLE_ADMIN = "admin"
TYPING_DEBOUNCE_SECONDS = 1.0


class GroupChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        url_route = self.scope.get("url_route") or {}
        raw_group_id = (url_route.get("kwargs") or {}).get("group_id")
        if raw_group_id is None:
            raw_group_id = (url_route.get("kwargs") or {}).get("conversation_id")

        try:
            self.group_id = int(raw_group_id)
        except (TypeError, ValueError):
            await self.close(code=4400)
            return

        # Keep the stored group id as the single routing primitive even when the client uses
        # the newer conversation-style socket alias.
        self.room_group_name = f"group_{self.group_id}"
        self._typing_started_last_sent_at = 0.0

        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4403)
            return

        if not await self._user_can_participate(user):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def receive_json(self, content, **kwargs):
        if content == INVALID_JSON_SENTINEL:
            await self._send_error("invalid_json", "Malformed JSON payload.")
            return

        if not isinstance(content, dict):
            await self._send_error("invalid_payload", "Payload must be a JSON object.")
            return

        user = self.scope["user"]
        if not user.is_authenticated:
            await self._send_error("not_authenticated", "Authentication required.")
            return

        if not await self._user_can_participate(user):
            await self._send_error("not_participant", "You are not a participant in this conversation.")
            return

        # Accept both the newer canonical event names and the older action/content payloads so
        # existing clients can gain reactions/read receipts without a protocol cut-over.
        event_type = content.get("type")
        action = content.get("action")

        if event_type == "message.send":
            await self._handle_message_send(user.id, content)
            return

        if event_type == "message.read":
            raw_message_ids = content.get("message_ids")
            if raw_message_ids is None and "message_id" in content:
                raw_message_ids = [content.get("message_id")]
            await self._handle_message_read(user.id, raw_message_ids)
            return

        if event_type == "typing.start":
            await self._handle_typing_event("started")
            return

        if event_type == "typing.stop":
            await self._handle_typing_event("stopped")
            return

        if action == "client.mark_read":
            await self._handle_message_read(user.id, content.get("message_ids"))
            return

        if action == "client.typing":
            status = content.get("status")
            if status not in {"started", "stopped"}:
                await self._send_error("invalid_payload", "Typing status must be started or stopped.")
                return
            await self._handle_typing_event(status)
            return

        if "content" in content or "resource_ids" in content:
            await self._handle_legacy_client_message(content)
            return

        await self._send_error("invalid_payload", "Unsupported event type.")

    async def _handle_message_send(self, user_id, content):
        body = content.get("body")
        if not isinstance(body, str):
            await self._send_error("invalid_payload", "Message body must be a string.")
            return

        body = sanitize_text(body.strip())
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
                "type": "chat.message",
                "payload": {
                    "event": "message.created",
                    "group_id": self.group_id,
                    "conversation_id": self.group_id,
                    "message": message_payload,
                },
            },
        )

    async def _handle_message_read(self, user_id, raw_message_ids):
        message_ids = self._normalize_message_ids(raw_message_ids)
        if not message_ids:
            await self._send_error("invalid_payload", "message_ids must include at least one integer.")
            return

        receipt_payload = await self._mark_messages_read(user_id, message_ids)
        if receipt_payload is None:
            await self._send_error("not_found", "Message not found in this conversation.")
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message_read",
                "payload": {
                    "type": "message.read",
                    "group_id": self.group_id,
                    "conversation_id": self.group_id,
                    **receipt_payload,
                },
            },
        )

    async def _handle_typing_event(self, status):
        if status == "started" and self._should_debounce_typing_started():
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.typing_event",
                "payload": {
                    "type": "typing.updated",
                    "group_id": self.group_id,
                    "conversation_id": self.group_id,
                    "status": status,
                    "user_id": self.scope["user"].id,
                    "user_name": self.scope["user"].get_full_name().strip() or self.scope["user"].email,
                },
                "sender_channel_name": self.channel_name,
            },
        )

    async def _handle_legacy_client_message(self, content):
        # This branch intentionally keeps the old ephemeral client.message echo for callers that
        # still send raw content/resource_ids over the socket without persisting a message row.
        raw_text = content.get("content")
        text = sanitize_text(raw_text) if isinstance(raw_text, str) else raw_text

        resource_ids = content.get("resource_ids", [])
        if not isinstance(resource_ids, list):
            resource_ids = []

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message",
                "payload": {
                    "event": "client.message",
                    "group_id": self.group_id,
                    "conversation_id": self.group_id,
                    "message": {
                        "text": text,
                        "resource_ids": resource_ids,
                        "sender_id": self.scope["user"].id,
                    },
                },
            },
        )

    def _normalize_message_ids(self, raw_message_ids):
        if raw_message_ids is None:
            return []

        if not isinstance(raw_message_ids, list):
            raw_message_ids = [raw_message_ids]

        message_ids = []
        seen = set()
        for raw_message_id in raw_message_ids:
            if isinstance(raw_message_id, bool):
                continue
            try:
                message_id = int(raw_message_id)
            except (TypeError, ValueError):
                continue
            if message_id in seen:
                continue
            seen.add(message_id)
            message_ids.append(message_id)
        return message_ids

    def _should_debounce_typing_started(self):
        now = time.monotonic()
        if now - self._typing_started_last_sent_at < TYPING_DEBOUNCE_SECONDS:
            return True
        self._typing_started_last_sent_at = now
        return False

    async def chat_message(self, event):
        await self.send_json(event["payload"])

    async def chat_message_read(self, event):
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
    def _has_admin_access(self, user):
        rah = get_active_assignment(user)
        return bool(rah and rah.role and rah.role.role_name in {ROLE_ADMIN})

    @database_sync_to_async
    def is_member(self, uid):
        return GroupMembership.objects.filter(
            user_id=uid,
            group_id=self.group_id,
            left_at__isnull=True,
        ).exists()

    async def _user_can_participate(self, user):
        if await self._has_admin_access(user):
            return True
        return await self.is_member(user.id)

    @database_sync_to_async
    def _create_message(self, user_id, body):
        message = Messages.objects.create(
            group_id=self.group_id,
            sender_user_id=user_id,
            message_text=body,
        )
        # Prefetch the related chat state once so build_chat_message_payload can emit the full
        # frontend contract in a single websocket frame without N+1 lookups.
        message = Messages.objects.select_related("sender_user").prefetch_related(
            "attachments",
            "resources__resource",
            "reactions",
            "statuses",
        ).get(pk=message.pk)
        return build_chat_message_payload(message)

    @database_sync_to_async
    def _mark_messages_read(self, user_id, message_ids):
        messages = list(
            Messages.objects.filter(
                pk__in=message_ids,
                group_id=self.group_id,
                deleted_at__isnull=True,
            ).order_by("id")
        )
        if not messages:
            return None

        read_ids = []
        read_at = None
        for message in messages:
            # Keep read receipts idempotent: a socket reconnect or duplicated event should update
            # the existing per-user status row instead of creating parallel delivery state.
            status, _ = MessageStatus.objects.get_or_create(
                message=message,
                user_id=user_id,
                defaults={"status": MessageStatus.StatusChoices.SENT},
            )
            status.mark_read()
            read_ids.append(message.id)
            read_at = status.read_at.isoformat() if status.read_at else read_at

        payload = {
            "message_ids": read_ids,
            "read_by": user_id,
            "user_id": user_id,
            "read_at": read_at,
        }
        if len(read_ids) == 1:
            payload["message_id"] = read_ids[0]
        return payload

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
