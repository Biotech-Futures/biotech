"""WebSocket consumer delivering real-time group chat updates."""

from __future__ import annotations

from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework.exceptions import ValidationError

from groups.models import Group

from .permissions import user_has_group_access
from .services import (
    create_message,
    get_group_channel_name,
    serialize_message,
)


class GroupChatConsumer(AsyncJsonWebsocketConsumer):
    """Provide a JWT-authenticated WebSocket endpoint per group."""

    async def connect(self) -> None:
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return

        self.group_id = str(self.scope["url_route"]["kwargs"].get("group_id"))

        try:
            group = await self._fetch_group()
        except Group.DoesNotExist:
            await self.close(code=4404)
            return

        has_access = await self._user_has_access(user, group)
        if not has_access:
            await self.close(code=4403)
            return

        self.group = group
        self.room_group_name = get_group_channel_name(self.group_id)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connection.established", "groupId": self.group_id})

    async def disconnect(self, code: int) -> None:  # noqa: D401 - inherited docstring
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        action = content.get("action") or content.get("type")
        if action == "send_message":
            await self._handle_send_message(content)
        elif action == "ping":
            await self.send_json({"type": "pong"})
        else:
            await self.send_json({"type": "error", "error": "unknown_action"})

    async def _handle_send_message(self, payload: dict[str, Any]) -> None:
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.send_json({"type": "error", "error": "unauthenticated"})
            return

        text = payload.get("text", "")
        attachments = payload.get("attachments") or []

        try:
            message = await self._create_message(user, text, attachments)
        except ValidationError as exc:
            await self.send_json(
                {
                    "type": "error",
                    "error": "validation_error",
                    "detail": _first_validation_message(exc.detail),
                }
            )
            return

        serialized = await self._serialize_message(message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message",
                "event": "message.created",
                "payload": serialized,
            },
        )

    async def chat_message(self, event: dict[str, Any]) -> None:
        await self.send_json({"type": event.get("event"), "payload": event.get("payload")})

    # --- Database helpers -------------------------------------------------

    @database_sync_to_async
    def _fetch_group(self) -> Group:
        return (
            Group.objects.select_related("mentor")
            .prefetch_related("members__user")
            .get(pk=self.group_id)
        )

    @database_sync_to_async
    def _user_has_access(self, user, group) -> bool:
        return user_has_group_access(user, group)

    @database_sync_to_async
    def _create_message(self, user, text: str, attachments) -> Any:
        # Fetch the latest state from the database before creation.
        group = (
            Group.objects.select_related("mentor")
            .prefetch_related("members__user")
            .get(pk=self.group_id)
        )
        return create_message(group, user, text, attachments)

    @database_sync_to_async
    def _serialize_message(self, message) -> dict[str, Any]:
        # Use moderator context so the payload is complete; clients enforce visibility.
        return serialize_message(message, for_user=None)


def _first_validation_message(detail) -> str:
    if isinstance(detail, dict):
        for value in detail.values():
            message = _first_validation_message(value)
            if message:
                return message
    elif isinstance(detail, (list, tuple)):
        for item in detail:
            message = _first_validation_message(item)
            if message:
                return message
    else:
        return str(detail)
    return "Invalid payload."
