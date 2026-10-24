"""The shared note's WebSocket: who gets in, and what travels to whom."""

import base64
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.meetings import consumers, services
from apps.meetings.models import MeetingNote
from config.asgi import application

from .support import MeetingGroupMixin, browser, typed

IN_MEMORY = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


def _b64(data):
    return base64.b64encode(data).decode()


@override_settings(CHANNEL_LAYERS=IN_MEMORY)
class NoteSocketTests(MeetingGroupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.meeting = self.book()
        # Channels tidies up connections around every database call. Inside
        # a TestCase transaction that closes the test's own connection on
        # Postgres (SQLite's in-memory database ignores the close), so the
        # socket tests would only ever pass on SQLite.
        patcher = patch("channels.db.close_old_connections", lambda: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def socket(self, user=None, meeting_id=None):
        """Logs in here, outside any async code, since Django refuses that."""
        headers = []
        if user is not None:
            client = Client()
            client.force_login(user)
            cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
            headers = [(b"cookie", f"{settings.SESSION_COOKIE_NAME}={cookie}".encode())]
        return WebsocketCommunicator(
            application,
            f"/ws/meetings/{meeting_id or self.meeting.pk}/note/",
            headers=headers,
        )

    def connect_result(self, communicator):
        async def attempt():
            connected, code = await communicator.connect()
            await communicator.disconnect()
            return connected, code
        return async_to_sync(attempt)()

    def test_members_and_admins_get_in(self):
        for user in (self.student, self.mentor, self.admin):
            connected, _ = self.connect_result(self.socket(user))
            self.assertTrue(connected, user.email)

    def test_outsiders_and_signed_out_visitors_are_refused(self):
        self.assertEqual(self.connect_result(self.socket(self.outsider)), (False, 4403))
        self.assertEqual(self.connect_result(self.socket()), (False, 4403))

    def test_a_cancelled_meeting_or_unknown_id_accepts_nobody(self):
        self.assertEqual(
            self.connect_result(self.socket(self.student, meeting_id=999999)), (False, 4403)
        )
        services.cancel_meeting(self.meeting)
        self.assertEqual(self.connect_result(self.socket(self.student)), (False, 4403))

    def test_a_deleted_group_accepts_nobody(self):
        self.group.deleted_at = timezone.now()
        self.group.save()
        self.assertEqual(self.connect_result(self.socket(self.admin)), (False, 4403))

    def test_typing_is_saved_and_reaches_the_other_member_but_is_not_echoed(self):
        doc, text = browser()
        services.apply_note_update(self.meeting.pk, self.mentor.pk, typed(doc, text, "Agenda: "))
        amy, ben = self.socket(self.student), self.socket(self.classmate)

        async def exchange():
            await amy.connect()
            amy_sync = await amy.receive_json_from(timeout=2)
            await ben.connect()
            ben_sync = await ben.receive_json_from(timeout=2)
            amy_hears_ben_join = await amy.receive_json_from(timeout=2)

            amy_doc, amy_text = browser(base64.b64decode(amy_sync["update"]))
            update = typed(amy_doc, amy_text, "Amy's point.")
            await amy.send_json_to({"type": "update", "update": _b64(update)})
            ben_gets = await ben.receive_json_from(timeout=2)
            amy_echo_free = await amy.receive_nothing(timeout=0.2)
            await amy.disconnect()
            await ben.disconnect()
            return amy_sync, ben_sync, amy_hears_ben_join, update, ben_gets, amy_echo_free

        amy_sync, ben_sync, joined, update, ben_gets, echo_free = async_to_sync(exchange)()

        self.assertEqual(amy_sync["event"], "note.sync")
        _, synced_text = browser(base64.b64decode(ben_sync["update"]))
        self.assertEqual(str(synced_text), "Agenda: ")
        self.assertEqual(joined, {"event": "note.peer_joined"})
        self.assertEqual(ben_gets, {"event": "note.update", "update": _b64(update)})
        self.assertTrue(echo_free)
        self.assertEqual(MeetingNote.objects.get(meeting=self.meeting).body, "Agenda: Amy's point.")

    def test_cursors_are_relayed_but_never_stored(self):
        amy, ben = self.socket(self.student), self.socket(self.classmate)

        async def exchange():
            await amy.connect()
            await amy.receive_json_from(timeout=2)
            await ben.connect()
            await ben.receive_json_from(timeout=2)
            await amy.receive_json_from(timeout=2)
            await amy.send_json_to({"type": "awareness", "update": "Y3Vyc29y"})
            got = await ben.receive_json_from(timeout=2)
            await amy.disconnect()
            await ben.disconnect()
            return got

        self.assertEqual(async_to_sync(exchange)(), {"event": "note.awareness", "update": "Y3Vyc29y"})
        self.assertEqual(MeetingNote.objects.get(meeting=self.meeting).revision, 0)

    def test_presence_reaches_others_once_a_second_and_not_the_sender(self):
        amy, ben = self.socket(self.student), self.socket(self.classmate)

        async def exchange():
            await amy.connect()
            await amy.receive_json_from(timeout=2)
            await ben.connect()
            await ben.receive_json_from(timeout=2)
            await amy.receive_json_from(timeout=2)
            await amy.send_json_to({"type": "presence", "editing": True})
            first = await ben.receive_json_from(timeout=2)
            await amy.send_json_to({"type": "presence", "editing": False})
            throttled = await ben.receive_nothing(timeout=0.2)
            not_echoed = await amy.receive_nothing(timeout=0.2)
            await amy.disconnect()
            await ben.disconnect()
            return first, throttled, not_echoed

        first, throttled, not_echoed = async_to_sync(exchange)()
        self.assertEqual(first["event"], "note.presence")
        self.assertEqual(first["user_id"], self.student.pk)
        self.assertTrue(first["editing"])
        self.assertTrue(throttled)
        self.assertTrue(not_echoed)

    def test_bad_frames_are_dropped_and_the_socket_stays_open(self):
        amy, ben = self.socket(self.student), self.socket(self.classmate)

        async def exchange():
            await amy.connect()
            await amy.receive_json_from(timeout=2)
            await ben.connect()
            await ben.receive_json_from(timeout=2)
            await amy.receive_json_from(timeout=2)
            for frame in (
                ["not", "a", "dict"],
                {"type": "unknown"},
                {"type": "update", "update": 42},
                {"type": "update", "update": "x" * (consumers.MAX_UPDATE_CHARS + 1)},
                {"type": "update", "update": "!!not base64!!"},
                {"type": "update", "update": _b64(b"not a yjs update")},
                {"type": "awareness", "update": "x" * (consumers.MAX_AWARENESS_CHARS + 1)},
            ):
                await amy.send_json_to(frame)
            nothing_reached_ben = await ben.receive_nothing(timeout=0.3)
            doc, text = browser()
            await amy.send_json_to({"type": "update", "update": _b64(typed(doc, text, "Still here"))})
            after = await ben.receive_json_from(timeout=2)
            await amy.disconnect()
            await ben.disconnect()
            return nothing_reached_ben, after

        with self.assertLogs("apps.meetings.consumers", "ERROR"):
            nothing_reached_ben, after = async_to_sync(exchange)()
        self.assertTrue(nothing_reached_ben)
        self.assertEqual(after["event"], "note.update")
        self.assertEqual(MeetingNote.objects.get(meeting=self.meeting).body, "Still here")

    def test_a_malformed_meeting_id_is_closed_with_4400(self):
        consumer = consumers.MeetingNoteConsumer()
        consumer.scope = {"url_route": {"kwargs": {"meeting_id": "abc"}}}
        closed = []

        async def close(code=None):
            closed.append(code)

        consumer.close = close
        async_to_sync(consumer.connect)()
        self.assertEqual(closed, [4400])

    def test_presence_from_a_signed_out_scope_is_ignored(self):
        from django.contrib.auth.models import AnonymousUser

        consumer = consumers.MeetingNoteConsumer()
        consumer.scope = {"user": AnonymousUser()}
        sent = []

        class Layer:
            async def group_send(self, *args):
                sent.append(args)

        consumer.channel_layer = Layer()
        async_to_sync(consumer._handle_presence)({"editing": True})
        self.assertEqual(sent, [])
