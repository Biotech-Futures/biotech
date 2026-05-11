"""Unit tests for the typing-indicator path on ``GroupChatConsumer``.

Driving a full WebSocket roundtrip from a Django TestCase is brittle
under InMemoryChannelLayer (see notes in ``test_chat.py``). These tests
exercise ``receive_json`` and ``chat_message`` directly with a mocked
channel layer, which is sufficient to pin the behaviour the FE relies
on: typing frames fan out, bursts are rate-limited, and a user never
sees their own indicator echoed back.
"""

from unittest.mock import AsyncMock

from asgiref.sync import async_to_sync
from django.test import TestCase

from apps.chat.management.consumers import (
    GroupChatConsumer,
    TYPING_RATE_LIMIT_SECONDS,
)


class _FakeUser:
    def __init__(self, uid, name="Test User", authenticated=True):
        self.id = uid
        self.is_authenticated = authenticated
        self._name = name

    def get_full_name(self):
        return self._name


def _make_consumer(user_id=10, name="Ana Lee", group_id=42):
    """Build a consumer with the bits ``receive_json`` reads, no socket."""
    consumer = GroupChatConsumer()
    consumer.scope = {"user": _FakeUser(user_id, name=name)}
    consumer.group_id = group_id
    consumer.room_group_name = f"group_{group_id}"
    consumer._last_typing_at = 0.0
    consumer.channel_layer = AsyncMock()
    consumer.channel_layer.group_send = AsyncMock()
    consumer.send_json = AsyncMock()
    return consumer


class TypingReceiveTests(TestCase):
    def test_typing_frame_fans_out_envelope(self):
        consumer = _make_consumer(user_id=10, name="Ana Lee", group_id=42)
        async_to_sync(consumer.receive_json)({"type": "typing", "typing": True})

        consumer.channel_layer.group_send.assert_awaited_once()
        room, envelope = consumer.channel_layer.group_send.call_args.args
        self.assertEqual(room, "group_42")
        self.assertEqual(envelope["type"], "chat.message")
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "user.typing")
        self.assertEqual(payload["type"], "user.typing")
        self.assertEqual(payload["group_id"], 42)
        self.assertEqual(payload["user_id"], 10)
        self.assertEqual(payload["user_name"], "Ana Lee")
        self.assertTrue(payload["typing"])

    def test_typing_false_is_propagated(self):
        consumer = _make_consumer()
        async_to_sync(consumer.receive_json)({"type": "typing", "typing": False})
        _, envelope = consumer.channel_layer.group_send.call_args.args
        self.assertFalse(envelope["payload"]["typing"])

    def test_unknown_frame_type_is_silently_dropped(self):
        consumer = _make_consumer()
        async_to_sync(consumer.receive_json)({"type": "ping"})
        consumer.channel_layer.group_send.assert_not_awaited()

    def test_non_dict_payload_is_silently_dropped(self):
        consumer = _make_consumer()
        async_to_sync(consumer.receive_json)("hello")
        async_to_sync(consumer.receive_json)(None)
        consumer.channel_layer.group_send.assert_not_awaited()

    def test_unauthenticated_user_cannot_emit_typing(self):
        consumer = _make_consumer()
        consumer.scope["user"] = _FakeUser(10, authenticated=False)
        async_to_sync(consumer.receive_json)({"type": "typing", "typing": True})
        consumer.channel_layer.group_send.assert_not_awaited()

    def test_rate_limit_drops_burst(self):
        consumer = _make_consumer()
        async_to_sync(consumer.receive_json)({"type": "typing", "typing": True})
        async_to_sync(consumer.receive_json)({"type": "typing", "typing": True})
        async_to_sync(consumer.receive_json)({"type": "typing", "typing": True})
        self.assertEqual(consumer.channel_layer.group_send.await_count, 1)

    def test_rate_limit_allows_emission_after_window(self):
        consumer = _make_consumer()
        async_to_sync(consumer.receive_json)({"type": "typing", "typing": True})
        # Simulate passage of time by rewinding the recorded timestamp.
        consumer._last_typing_at -= TYPING_RATE_LIMIT_SECONDS + 0.1
        async_to_sync(consumer.receive_json)({"type": "typing", "typing": True})
        self.assertEqual(consumer.channel_layer.group_send.await_count, 2)


class TypingFanoutSkipsSelfTests(TestCase):
    """``chat_message`` is the per-consumer fan-out callback. When the
    layer hands it a ``user.typing`` event the connected user emitted,
    the consumer must drop it instead of echoing it back to the typer."""

    def test_chat_message_skips_self_typing(self):
        consumer = _make_consumer(user_id=10)
        event = {
            "type": "chat.message",
            "payload": {
                "event": "user.typing",
                "type": "user.typing",
                "group_id": 42,
                "user_id": 10,  # same as scope user
                "user_name": "Ana Lee",
                "typing": True,
            },
        }
        async_to_sync(consumer.chat_message)(event)
        consumer.send_json.assert_not_awaited()

    def test_chat_message_forwards_others_typing(self):
        consumer = _make_consumer(user_id=10)
        event = {
            "type": "chat.message",
            "payload": {
                "event": "user.typing",
                "type": "user.typing",
                "group_id": 42,
                "user_id": 11,  # someone else
                "user_name": "Bob",
                "typing": True,
            },
        }
        async_to_sync(consumer.chat_message)(event)
        consumer.send_json.assert_awaited_once_with(event["payload"])
