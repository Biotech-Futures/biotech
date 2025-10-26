"""Shared chat business logic across HTTP views and WebSocket consumers."""

from __future__ import annotations

from typing import Iterable

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Message, MessageAttachment
from .serializers import MessageSerializer


def create_message(group, author, text: str, attachments_payload: Iterable[dict] | None = None) -> Message:
    """Create a message with optional attachments after validating payload."""

    normalized_text = (text or "").strip()
    attachments_payload = list(attachments_payload or [])

    if not normalized_text and not attachments_payload:
        raise ValidationError({"text": "Message text or attachments are required."})

    attachments_to_create: list[MessageAttachment] = []

    for raw in attachments_payload:
        if not isinstance(raw, dict):
            raise ValidationError({"attachments": "Each attachment must be an object."})

        file_url = raw.get("url") or raw.get("file_url")
        filename = raw.get("filename")
        file_size = raw.get("size") or raw.get("file_size")
        mime_type = raw.get("mimeType") or raw.get("mime_type") or "application/octet-stream"

        if not file_url:
            raise ValidationError({"attachments": "Attachment is missing url."})
        if not filename:
            raise ValidationError({"attachments": "Attachment is missing filename."})

        try:
            file_size_value = int(file_size) if file_size is not None else 0
        except (TypeError, ValueError) as exc:
            raise ValidationError({"attachments": "Attachment size must be an integer."}) from exc

        attachments_to_create.append(
            MessageAttachment(
                file_url=file_url,
                filename=filename,
                file_size=file_size_value,
                mime_type=mime_type or "application/octet-stream",
            )
        )

    with transaction.atomic():
        message = Message.objects.create(
            group=group,
            author=author,
            text=normalized_text,
        )

        if attachments_to_create:
            for attachment in attachments_to_create:
                attachment.message = message
            MessageAttachment.objects.bulk_create(attachments_to_create)

    return (
        Message.objects.select_related("author", "deleted_by", "moderated_by")
        .prefetch_related("attachments")
        .get(pk=message.pk)
    )


def serialize_message(message: Message, for_user=None) -> dict:
    serializer = MessageSerializer(message, context={"user": for_user})
    return serializer.data


def broadcast_message_event(group_id: str, event_type: str, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        get_group_channel_name(group_id),
        {
            "type": "chat.message",
            "event": event_type,
            "payload": payload,
        },
    )


def get_group_channel_name(group_id: str) -> str:
    return f"group_chat_{group_id}"
