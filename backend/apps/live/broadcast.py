"""Telling a live room, from ordinary request code, that something changed."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .rooms import person, room_name

logger = logging.getLogger(__name__)


def notify_changed(kind: str, room_id: int, item: str, by=None) -> None:
    """Ask everyone in the room but ``by`` to refetch ``item``; best effort, so a save never fails on it."""
    layer = get_channel_layer()
    if layer is None:
        return
    event = {"type": "room.changed", "item": item, "user": person(by) if by is not None else None}
    try:
        async_to_sync(layer.group_send)(room_name(kind, room_id), event)
    except Exception:  # noqa: BLE001
        logger.warning("live.notify_failed kind=%s room=%s", kind, room_id, exc_info=True)
