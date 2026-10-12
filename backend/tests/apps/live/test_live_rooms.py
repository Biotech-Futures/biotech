"""Tests for live rooms: who gets in, and how typing frames travel."""
import asyncio
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.groups.models import GroupMembership, Groups
from apps.live import consumers
from apps.live.broadcast import notify_changed
from apps.live.consumers import LiveRoomConsumer
from apps.live.rooms import can_join
from apps.users.models import AdminScope
from config.asgi import application

IN_MEMORY = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


def _consumer(user_id=1, name="Amy"):
    """A consumer wired up as after a successful connect, with no socket."""
    consumer = LiveRoomConsumer()
    consumer.room = "live.submission.7"
    consumer.user = {"id": user_id, "name": name}
    consumer._last_frame = 0.0
    consumer._last_typing = {}
    consumer._last_text = {}
    consumer._pending_text = {}
    consumer._text_sends = {}
    consumer._open = set()
    consumer.channel_layer = AsyncMock()
    consumer.channel_name = "test-channel"
    consumer.send_json = AsyncMock()
    return consumer


def _sent(consumer):
    return [call.args[1] for call in consumer.channel_layer.group_send.await_args_list]


class TypingFrameTests(TestCase):
    def test_a_typing_frame_reaches_the_room(self):
        consumer = _consumer()

        async_to_sync(consumer.receive_json)({"type": "typing", "field": "q1", "typing": True})

        room, event = consumer.channel_layer.group_send.await_args.args
        self.assertEqual(room, "live.submission.7")
        self.assertEqual(event, {
            "type": "room.relay", "kind": "typing", "user": {"id": 1, "name": "Amy"}, "field": "q1", "typing": True,
        })

    def test_repeated_typing_in_one_field_is_held_back(self):
        consumer = _consumer()
        frame = {"type": "typing", "field": "q1", "typing": True}

        async_to_sync(consumer.receive_json)(frame)
        async_to_sync(consumer.receive_json)(frame)

        self.assertEqual(len(_sent(consumer)), 1)

    def test_a_stop_always_follows_its_start(self):
        consumer = _consumer()

        async_to_sync(consumer.receive_json)({"type": "typing", "field": "q1", "typing": True})
        async_to_sync(consumer.receive_json)({"type": "typing", "field": "q1", "typing": False})

        self.assertEqual([event["typing"] for event in _sent(consumer)], [True, False])

    def test_a_stop_without_a_start_is_ignored(self):
        consumer = _consumer()

        async_to_sync(consumer.receive_json)({"type": "typing", "field": "q1", "typing": False})

        consumer.channel_layer.group_send.assert_not_awaited()

    def test_malformed_frames_are_dropped(self):
        consumer = _consumer()
        for frame in (
            "hello", None, {"type": "ping"},
            {"type": "typing", "field": "", "typing": True},
            {"type": "typing", "field": "x" * 65, "typing": True},
            {"type": "typing", "field": "q1", "typing": "yes"},
            {"type": "typing", "field": 3, "typing": True},
        ):
            async_to_sync(consumer.receive_json)(frame)

        consumer.channel_layer.group_send.assert_not_awaited()

    def test_closing_the_tab_clears_its_open_labels(self):
        consumer = _consumer()
        async_to_sync(consumer.receive_json)({"type": "typing", "field": "q1", "typing": True})

        async_to_sync(consumer.disconnect)(1000)

        self.assertEqual(_sent(consumer)[-1]["typing"], False)
        consumer.channel_layer.group_discard.assert_awaited_once()

    def test_the_typist_never_sees_their_own_label(self):
        consumer = _consumer(user_id=1)
        event = {"type": "room.relay", "kind": "typing", "user": {"id": 1, "name": "Amy"}, "field": "q1", "typing": True}

        async_to_sync(consumer.room_relay)(event)

        consumer.send_json.assert_not_awaited()

    def test_teammates_see_who_is_typing_where(self):
        consumer = _consumer(user_id=2)
        event = {"type": "room.relay", "kind": "typing", "user": {"id": 1, "name": "Amy"}, "field": "q1", "typing": True}

        async_to_sync(consumer.room_relay)(event)

        consumer.send_json.assert_awaited_once_with({
            "type": "typing", "user": {"id": 1, "name": "Amy"}, "field": "q1", "typing": True,
        })

    def test_typed_text_reaches_the_room(self):
        consumer = _consumer()

        async def type_it():
            await consumer.receive_json({"type": "text", "field": "q1", "text": "Our idea", "caret": 3})
            await asyncio.sleep(0.01)
        async_to_sync(type_it)()

        self.assertEqual(_sent(consumer), [{
            "type": "room.relay", "kind": "text", "user": {"id": 1, "name": "Amy"}, "field": "q1",
            "text": "Our idea", "caret": 3,
        }])

    def test_an_unusable_caret_means_the_end_of_the_text(self):
        consumer = _consumer()

        async def type_it():
            for i, caret in enumerate((None, -1, 99, True, "2")):
                await consumer.receive_json({"type": "text", "field": f"q{i}", "text": "abc", "caret": caret})
            await asyncio.sleep(0.01)
        async_to_sync(type_it)()

        self.assertEqual([event["caret"] for event in _sent(consumer)], [3, 3, 3, 3, 3])

    def test_a_long_paste_is_relayed_but_an_oversized_one_is_not(self):
        consumer = _consumer()

        async def paste():
            await consumer.receive_json({"type": "text", "field": "q1", "text": "x" * consumers.MAX_TEXT_LENGTH})
            await consumer.receive_json({"type": "text", "field": "q2", "text": "x" * (consumers.MAX_TEXT_LENGTH + 1)})
            await asyncio.sleep(0.05)
        async_to_sync(paste)()

        self.assertEqual([event["field"] for event in _sent(consumer)], ["q1"])

    def test_a_burst_of_text_ends_on_the_latest(self):
        consumer = _consumer()

        async def burst():
            for text in ("a", "ab", "abc"):
                await consumer.receive_json({"type": "text", "field": "q1", "text": text})
            await asyncio.sleep(consumers.MIN_TEXT_INTERVAL * 2)
        async_to_sync(burst)()

        self.assertEqual([event["text"] for event in _sent(consumer)][-1], "abc")
        self.assertNotIn("ab", [event["text"] for event in _sent(consumer)])

    def test_text_still_held_on_leaving_is_sent(self):
        consumer = _consumer()

        async def leave_mid_word():
            await consumer.receive_json({"type": "text", "field": "q1", "text": "a"})
            await asyncio.sleep(0.01)
            await consumer.receive_json({"type": "text", "field": "q1", "text": "ab"})
            await consumer.disconnect(1000)
        async_to_sync(leave_mid_word)()

        self.assertEqual([event["text"] for event in _sent(consumer)], ["a", "ab"])

    def test_malformed_text_frames_are_dropped(self):
        consumer = _consumer()
        for frame in (
            {"type": "text", "field": "q1"},
            {"type": "text", "field": "q1", "text": 5},
            {"type": "text", "field": "", "text": "a"},
        ):
            async_to_sync(consumer.receive_json)(frame)

        consumer.channel_layer.group_send.assert_not_awaited()

    def test_a_flood_of_frames_is_capped(self):
        consumer = _consumer()
        with patch.object(consumers.time, "monotonic", return_value=100.0):
            for i in range(20):
                async_to_sync(consumer.receive_json)({"type": "typing", "field": f"q{i}", "typing": True})

        self.assertEqual(len(_sent(consumer)), 1)


class ChangedNoticeTests(TestCase):
    def test_a_change_is_announced_to_the_room(self):
        layer = AsyncMock()
        with patch("apps.live.broadcast.get_channel_layer", return_value=layer):
            notify_changed("submission", 7, "notes")

        layer.group_send.assert_awaited_once_with(
            "live.submission.7", {"type": "room.changed", "item": "notes", "user": None},
        )

    def test_a_change_names_who_made_it_and_skips_them(self):
        layer = AsyncMock()
        author = get_user_model()(id=1, first_name="Amy")
        with patch("apps.live.broadcast.get_channel_layer", return_value=layer):
            notify_changed("submission", 7, "files", by=author)
        event = layer.group_send.await_args.args[1]
        self.assertEqual(event["user"], {"id": 1, "name": "Amy"})

        amy, ben = _consumer(user_id=1), _consumer(user_id=2)
        async_to_sync(amy.room_changed)(event)
        async_to_sync(ben.room_changed)(event)

        amy.send_json.assert_not_awaited()
        ben.send_json.assert_awaited_once_with({"type": "changed", "item": "files", "user": {"id": 1, "name": "Amy"}})

    def test_a_failed_announcement_never_raises(self):
        layer = AsyncMock()
        layer.group_send.side_effect = RuntimeError("redis down")
        with patch("apps.live.broadcast.get_channel_layer", return_value=layer), \
                self.assertLogs("apps.live.broadcast", "WARNING"):
            notify_changed("submission", 7, "notes")


@override_settings(CHANNEL_LAYERS=IN_MEMORY)
class RoomConnectionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.group = Groups.objects.create(group_name="BTF-LIVE")
        self.amy = User.objects.create_user(email="amy@test.local", password="x", first_name="Amy")
        self.ben = User.objects.create_user(email="ben@test.local", password="x", first_name="Ben")
        self.outsider = User.objects.create_user(email="out@test.local", password="x", first_name="Olu")
        self.admin = User.objects.create_user(email="admin@test.local", password="x", first_name="Ada")
        AdminScope.objects.create(user=self.admin)
        for user in (self.amy, self.ben):
            GroupMembership.objects.create(group=self.group, user=user, membership_role="student")

    def _communicator(self, user, path=None):
        """Logs in here, outside any async code, since Django refuses that."""
        client = Client()
        client.force_login(user)
        cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
        return WebsocketCommunicator(
            application,
            path or f"/ws/live/submission/{self.group.id}/",
            headers=[(b"cookie", f"{settings.SESSION_COOKIE_NAME}={cookie}".encode())],
        )

    def _connects(self, user, path=None):
        communicator = self._communicator(user, path)

        async def attempt():
            connected, _ = await communicator.connect()
            await communicator.disconnect()
            return connected
        return async_to_sync(attempt)()

    def test_team_members_and_admins_can_join(self):
        self.assertTrue(self._connects(self.amy))
        self.assertTrue(self._connects(self.admin))

    def test_people_outside_the_team_are_refused(self):
        self.assertFalse(self._connects(self.outsider))

    def test_a_deleted_team_or_unknown_room_kind_is_refused(self):
        self.assertFalse(self._connects(self.amy, "/ws/live/notes/1/"))
        self.group.deleted_at = timezone.now()
        self.group.save()
        self.assertFalse(self._connects(self.amy))

    def test_a_teammate_sees_typing_and_text_live(self):
        amy, ben = self._communicator(self.amy), self._communicator(self.ben)

        async def exchange():
            await amy.connect()
            await ben.connect()
            hello = await amy.receive_json_from(timeout=2)
            await ben.receive_json_from(timeout=2)
            await amy.send_json_to({"type": "typing", "field": "q1", "typing": True})
            await amy.send_json_to({"type": "text", "field": "q1", "text": "Our idea", "caret": 8})
            received = [await ben.receive_json_from(timeout=2) for _ in range(2)]
            echoed = await amy.receive_nothing(timeout=0.2)
            await amy.disconnect()
            await ben.disconnect()
            return hello, received, echoed

        hello, received, echoed = async_to_sync(exchange)()

        amy = {"id": self.amy.id, "name": "Amy"}
        self.assertEqual(hello, {"type": "hello", "user": amy})
        self.assertEqual(received, [
            {"type": "typing", "user": amy, "field": "q1", "typing": True},
            {"type": "text", "user": amy, "field": "q1", "text": "Our idea", "caret": 8},
        ])
        self.assertTrue(echoed)

    def test_the_room_rule_matches_the_portal(self):
        self.assertTrue(can_join("submission", self.ben, self.group.id))
        self.assertFalse(can_join("submission", self.outsider, self.group.id))
        self.assertFalse(can_join("submission", self.amy, self.group.id + 999))
