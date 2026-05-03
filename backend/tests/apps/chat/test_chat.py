import asyncio
import contextlib
from datetime import timedelta
from unittest.mock import patch, AsyncMock

from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory
from django.test import TransactionTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from config.asgi import application
from apps.chat.models import MessageStatus, Messages
from apps.chat.tasks import process_chat_message_created
from apps.chat.management.consumers import GroupChatConsumer
from apps.resources.models import Roles, RoleAssignmentHistory, Resources
from apps.groups.models import Groups, GroupMembership, Countries, CountryStates, Tracks

# The websocket tests do not need Redis itself; an in-memory layer keeps the suite fast
# and avoids depending on external infrastructure.
CHANNEL_TEST_SETTINGS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}

CELERY_TEST_SETTINGS = {
    "CELERY_BROKER_URL": "memory://",
    "CELERY_RESULT_BACKEND": "cache+memory://",
    "CELERY_TASK_ALWAYS_EAGER": True,
    "CELERY_TASK_EAGER_PROPAGATES": True,
}


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS, **CELERY_TEST_SETTINGS)
class ChatFeatureTests(TransactionTestCase):
    """
    Integration tests for chat:
      - POST /chat/groups/{id}/messages/
      - GET  /chat/groups/{id}/messages/?after=&limit=
      - DELETE /chat/groups/{id}/messages/{mid}/  (soft delete)
      - WebSocket broadcasts (message.created / message.deleted)
      - Permissions by role: mentor (group-scoped), supervisor (group-scoped), admin (global)

    TransactionTestCase is used instead of TestCase because the websocket communicator
    and async DB access need committed rows that are visible across async boundaries.
    """

    def setUp(self):
        User = get_user_model()

        self.student = User.objects.create_user(email="student@test.com", password="pw")
        self.mentor = User.objects.create_user(email="mentor@test.com", password="pw")
        self.supervisor = User.objects.create_user(email="supervisor@test.com", password="pw")
        self.admin = User.objects.create_user(email="admin@test.com", password="pw", is_staff=False)

        self.role_mentor = Roles.objects.create(role_name="mentor")
        self.role_supervisor = Roles.objects.create(role_name="supervisor")
        self.role_admin = Roles.objects.create(role_name="admin")
        self.role_student = Roles.objects.create(role_name="basic_student")

        now = timezone.now()
        future = now.replace(year=2099)

        RoleAssignmentHistory.objects.create(user=self.student, role=self.role_student, valid_from=now, valid_to=future)
        RoleAssignmentHistory.objects.create(user=self.mentor, role=self.role_mentor, valid_from=now, valid_to=future)
        RoleAssignmentHistory.objects.create(user=self.supervisor, role=self.role_supervisor, valid_from=now, valid_to=future)
        RoleAssignmentHistory.objects.create(user=self.admin, role=self.role_admin, valid_from=now, valid_to=future)

        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=self.state)

        self.group = Groups.objects.create(group_name="G1", track=self.track)
        GroupMembership.objects.create(user=self.student, group=self.group)
        GroupMembership.objects.create(user=self.mentor, group=self.group)
        GroupMembership.objects.create(user=self.supervisor, group=self.group)
        self.non_participant = User.objects.create_user(email="outsider@test.com", password="pw")

        self.res1 = Resources.objects.create(
            name="R1",
            description="d1",
            uploaded_by=self.admin,
            uploaded_at=timezone.now() - timedelta(minutes=1),
        )
        self.res2 = Resources.objects.create(
            name="R2",
            description="d2",
            uploaded_by=self.admin,
            uploaded_at=timezone.now() - timedelta(minutes=1),
        )

        self.client_student = APIClient(); self.client_student.force_authenticate(user=self.student)
        self.client_mentor = APIClient(); self.client_mentor.force_authenticate(user=self.mentor)
        self.client_supervisor = APIClient(); self.client_supervisor.force_authenticate(user=self.supervisor)
        self.client_admin = APIClient(); self.client_admin.force_authenticate(user=self.admin)

        self._session_cookies = {
            self.student.id: self._build_session_cookie(self.student),
            self.mentor.id: self._build_session_cookie(self.mentor),
            self.supervisor.id: self._build_session_cookie(self.supervisor),
            self.non_participant.id: self._build_session_cookie(self.non_participant),
        }

    # --------- helpers ---------
    def _list_url(self, group_id=None):
        gid = group_id or self.group.id
        return reverse("group-messages-list", kwargs={"group_pk": gid})

    def _detail_url(self, mid, group_id=None):
        gid = group_id or self.group.id
        return reverse("group-messages-detail", kwargs={"group_pk": gid, "pk": mid})

    def _build_session_cookie(self, user):
        c = Client()
        c.force_login(user)
        return c.cookies[settings.SESSION_COOKIE_NAME].value

    def _session_cookie(self, user):
        return self._session_cookies[user.id]

    async def _ws_connect_with_session(self, user):
        cookie = self._session_cookie(user)
        headers = [(b"cookie", f"{settings.SESSION_COOKIE_NAME}={cookie}".encode())]
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{self.group.id}/",
            headers=headers,
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected, "WebSocket failed to connect")
        return communicator

    async def _receive_ws_event(self, communicator, expected_type, attempts=3):
        for _ in range(attempts):
            event = await communicator.receive_json_from(timeout=5)
            if event.get("event") == "chat.connected":
                continue
            if event.get("type") == expected_type:
                return event
        self.fail(f"Did not receive websocket event of type {expected_type!r}")

    async def _receive_ws_payload_event(self, communicator, expected_event, attempts=3):
        for _ in range(attempts):
            event = await communicator.receive_json_from(timeout=5)
            if event.get("event") == "chat.connected":
                continue
            if event.get("event") == expected_event:
                return event
        self.fail(f"Did not receive websocket payload event {expected_event!r}")

    async def _send_ws_json(self, communicator, payload):
        await communicator.send_json_to(payload)

    async def _send_ws_text(self, communicator, text_data):
        await communicator.send_to(text_data=text_data)

    async def _disconnect_ws(self, communicator):
        with contextlib.suppress(Exception, asyncio.CancelledError):
            await communicator.disconnect()

    async def _message_exists(self, *, sender_user, message_text):
        return await sync_to_async(
            Messages.objects.filter(
                group=self.group,
                sender_user=sender_user,
                message_text=message_text,
            ).exists
        )()

    async def _message_count(self):
        return await sync_to_async(Messages.objects.count)()

    async def _remove_participation(self, user):
        await sync_to_async(
            GroupMembership.objects.filter(
                user=user,
                group=self.group,
                left_at__isnull=True,
            ).update
        )(left_at=timezone.now())

    async def _get_message_status(self, message, user):
        return await sync_to_async(
            MessageStatus.objects.get
        )(message=message, user=user)

    def test_ws_connect_allowed_for_participant(self):
        async def scenario():
            comm = await self._ws_connect_with_session(self.student)
            try:
                self.assertIsNotNone(comm)
            finally:
                await self._disconnect_ws(comm)
        async_to_sync(scenario)()

    def test_ws_connect_denied_for_non_participant(self):
        async def scenario():
            cookie = self._session_cookie(self.non_participant)
            headers = [(b"cookie", f"{settings.SESSION_COOKIE_NAME}={cookie}".encode())]
            communicator = WebsocketCommunicator(application, f"/ws/chat/{self.group.id}/", headers=headers)
            connected, _ = await communicator.connect()
            self.assertFalse(connected)
        async_to_sync(scenario)()

    def test_ws_connect_denied_for_anonymous_user(self):
        async def scenario():
            communicator = WebsocketCommunicator(application, f"/ws/chat/{self.group.id}/")
            connected, _ = await communicator.connect()
            self.assertFalse(connected)
        async_to_sync(scenario)()

    def test_ws_send_persists_and_broadcasts_to_all_clients(self):
        async def scenario():
            sender_comm = await self._ws_connect_with_session(self.student)
            listener_comm = await self._ws_connect_with_session(self.mentor)
            try:
                await self._send_ws_json(sender_comm, {"type": "message.send", "body": "hello"})
                sender_event = await self._receive_ws_event(sender_comm, "message.created")
                listener_event = await self._receive_ws_event(listener_comm, "message.created")
                self.assertEqual(sender_event, listener_event)
                self.assertEqual(sender_event["message"]["conversation_id"], self.group.id)
                self.assertEqual(sender_event["message"]["sender_id"], self.student.id)
                self.assertEqual(sender_event["message"]["body"], "hello")
                self.assertIn("created_at", sender_event["message"])
                self.assertTrue(await self._message_exists(sender_user=self.student, message_text="hello"))
            finally:
                await self._disconnect_ws(sender_comm)
                await self._disconnect_ws(listener_comm)
        async_to_sync(scenario)()

    # ---- Sanitisation integration tests --------------------------------------
    # These exercise the same end-to-end paths as the unit tests in
    # ``tests/apps/chat/test_sanitize.py`` but go through DRF + Channels so we
    # catch wiring mistakes (e.g. forgetting to call sanitize_text in a code
    # path that bypasses the serializer).

    def test_rest_post_sanitises_profanity_before_persist(self):
        response = self.client_student.post(
            self._list_url(),
            {"message_text": "what the hell is this shit", "resources": []},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            response.data["message_text"],
            "what the *** is this ***",
            "Serializer must sanitise before save() so the API response, DB row, "
            "and downstream broadcast all see the cleaned text.",
        )
        stored = Messages.objects.get(pk=response.data["id"])
        self.assertEqual(stored.message_text, "what the *** is this ***")

    def test_rest_post_sanitises_leetspeak_and_punctuation_variants(self):
        # Bypass attempts the reviewer specifically called out.
        response = self.client_student.post(
            self._list_url(),
            {"message_text": "sh1t and f*ck and s.h.i.t", "resources": []},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["message_text"], "*** and *** and ***")

    def test_rest_patch_edit_sanitises_profanity(self):
        msg = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="clean original"
        )
        url = self._detail_url(msg.id)
        response = self.client_student.patch(
            url, {"message_text": "what the hell"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        msg.refresh_from_db()
        self.assertEqual(msg.message_text, "what the ***")
        self.assertIsNotNone(msg.edited_at)

    def test_ws_send_sanitises_profanity_in_persisted_and_broadcast_payload(self):
        async def scenario():
            sender_comm = await self._ws_connect_with_session(self.student)
            listener_comm = await self._ws_connect_with_session(self.mentor)
            try:
                await self._send_ws_json(
                    sender_comm,
                    {"type": "message.send", "body": "what the hell sh1t f*ck"},
                )
                sender_event = await self._receive_ws_event(sender_comm, "message.created")
                listener_event = await self._receive_ws_event(listener_comm, "message.created")
                self.assertEqual(sender_event, listener_event)
                self.assertEqual(
                    sender_event["message"]["body"],
                    "what the *** *** ***",
                    "WebSocket consumer must sanitise — it bypasses the DRF "
                    "serializer entirely.",
                )
                self.assertTrue(
                    await self._message_exists(
                        sender_user=self.student,
                        message_text="what the *** *** ***",
                    )
                )
            finally:
                await self._disconnect_ws(sender_comm)
                await self._disconnect_ws(listener_comm)
        async_to_sync(scenario)()

    def test_rest_post_clean_message_passes_through_unchanged(self):
        # Negative control: non-profanity must NOT be modified.
        response = self.client_student.post(
            self._list_url(),
            {"message_text": "Hi team, looking forward to the workshop!", "resources": []},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            response.data["message_text"],
            "Hi team, looking forward to the workshop!",
        )

    def test_ws_broadcast_on_rest_create(self):
        async def scenario():
            communicator = await self._ws_connect_with_session(self.student)
            try:
                response = await sync_to_async(self.client_student.post)(
                    self._list_url(),
                    {"message_text": "hi from rest", "resources": []},
                    format="json",
                )
                self.assertEqual(response.status_code, 201, response.content)
                event = await self._receive_ws_payload_event(communicator, "message.created")
                self.assertEqual(event["group_id"], self.group.id)
                self.assertEqual(event["message"]["text"], "hi from rest")
                self.assertEqual(event["message"]["sender_id"], self.student.id)
            finally:
                await self._disconnect_ws(communicator)
        async_to_sync(scenario)()

    def test_ws_broadcast_on_rest_delete(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="to remove")

        async def scenario():
            communicator = await self._ws_connect_with_session(self.mentor)
            try:
                response = await sync_to_async(self.client_mentor.delete)(self._detail_url(msg.id))
                self.assertEqual(response.status_code, 204, response.content)
                event = await self._receive_ws_payload_event(communicator, "message.deleted")
                self.assertEqual(event["group_id"], self.group.id)
                self.assertEqual(event["message_id"], msg.id)
            finally:
                await self._disconnect_ws(communicator)
        async_to_sync(scenario)()

    def test_reaction_toggle_adds_new(self):
        from apps.chat.models import MessageReaction
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="react to me")
        url = reverse("group-messages-react", kwargs={"group_pk": self.group.id, "pk": msg.id})
        resp = self.client_student.post(url, {"emoji_string": "👍"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["message_id"], msg.id)
        self.assertEqual(resp.data["reactions"]["👍"], 1)
        self.assertEqual(
            MessageReaction.objects.filter(message=msg, user=self.student, emoji_string="👍").count(), 1
        )

    def test_reaction_toggle_removes_existing(self):
        from apps.chat.models import MessageReaction
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="react to me twice")
        url = reverse("group-messages-react", kwargs={"group_pk": self.group.id, "pk": msg.id})
        self.client_student.post(url, {"emoji_string": "❤️"}, format="json")
        self.assertEqual(
            MessageReaction.objects.filter(message=msg, user=self.student, emoji_string="❤️").count(), 1
        )
        resp = self.client_student.post(url, {"emoji_string": "❤️"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["reactions"].get("❤️", 0), 0)
        self.assertEqual(
            MessageReaction.objects.filter(message=msg, user=self.student, emoji_string="❤️").count(), 0
        )

    def test_ws_typing_events_broadcast_to_other_participants_only(self):
        async def scenario():
            sender_comm = await self._ws_connect_with_session(self.student)
            listener_comm = await self._ws_connect_with_session(self.mentor)
            initial_message_count = await self._message_count()
            try:
                await self._send_ws_json(sender_comm, {"type": "typing.start"})
                listener_started = await self._receive_ws_event(listener_comm, "typing.started")
                self.assertEqual(listener_started, {"type": "typing.started", "conversation_id": self.group.id, "user_id": self.student.id})
                self.assertTrue(await sender_comm.receive_nothing(timeout=0.2))
                await self._send_ws_json(sender_comm, {"type": "typing.stop"})
                listener_stopped = await self._receive_ws_event(listener_comm, "typing.stopped")
                self.assertEqual(listener_stopped, {"type": "typing.stopped", "conversation_id": self.group.id, "user_id": self.student.id})
                self.assertTrue(await sender_comm.receive_nothing(timeout=0.2))
                self.assertEqual(await self._message_count(), initial_message_count)
            finally:
                await self._disconnect_ws(sender_comm)
                await self._disconnect_ws(listener_comm)
        async_to_sync(scenario)()

    def test_ws_typing_start_is_debounced(self):
        async def scenario():
            sender_comm = await self._ws_connect_with_session(self.student)
            listener_comm = await self._ws_connect_with_session(self.mentor)
            try:
                await self._send_ws_json(sender_comm, {"type": "typing.start"})
                await self._send_ws_json(sender_comm, {"type": "typing.start"})
                listener_event = await self._receive_ws_event(listener_comm, "typing.started")
                self.assertEqual(listener_event["conversation_id"], self.group.id)
                self.assertEqual(listener_event["user_id"], self.student.id)
                self.assertTrue(await listener_comm.receive_nothing(timeout=0.2))
                self.assertTrue(await sender_comm.receive_nothing(timeout=0.2))
            finally:
                await self._disconnect_ws(sender_comm)
                await self._disconnect_ws(listener_comm)
        async_to_sync(scenario)()

    def test_ws_message_read_updates_status_and_broadcasts(self):
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.student,
            message_text="mark me read",
        )

        async def scenario():
            reader_comm = await self._ws_connect_with_session(self.mentor)
            sender_comm = await self._ws_connect_with_session(self.student)

            try:
                await self._send_ws_json(
                    reader_comm,
                    {"type": "message.read", "message_id": message.id},
                )

                reader_event = await self._receive_ws_event(reader_comm, "message.read")
                sender_event = await self._receive_ws_event(sender_comm, "message.read")

                # Both sockets should observe the same canonical payload; the consumer does not
                # maintain a separate "ack to reader" event shape for read receipts.
                self.assertEqual(reader_event, sender_event)
                self.assertEqual(
                    reader_event,
                    {
                        "type": "message.read",
                        "conversation_id": self.group.id,
                        "message_id": message.id,
                        "user_id": self.mentor.id,
                        "read_at": reader_event["read_at"],
                    },
                )

                # The websocket event must reflect committed DB state, not a transient in-memory
                # acknowledgement, so assert against the persisted MessageStatus row as well.
                status = await self._get_message_status(message, self.mentor)
                self.assertEqual(status.status, MessageStatus.StatusChoices.READ)
                self.assertIsNotNone(status.delivered_at)
                self.assertIsNotNone(status.read_at)
                self.assertEqual(status.read_at.isoformat(), reader_event["read_at"])
            finally:
                await self._disconnect_ws(reader_comm)
                await self._disconnect_ws(sender_comm)

        async_to_sync(scenario)()

    def test_ws_message_read_rejects_message_outside_conversation(self):
        other_group = Groups.objects.create(group_name="G2", track=self.track)
        other_message = Messages.objects.create(
            group=other_group,
            sender_user=self.student,
            message_text="wrong conversation",
        )

        async def scenario():
            communicator = await self._ws_connect_with_session(self.mentor)
            try:
                await self._send_ws_json(
                    communicator,
                    {"type": "message.read", "message_id": other_message.id},
                )

                event = await self._receive_ws_event(communicator, "error")
                self.assertEqual(event["error"]["code"], "not_found")
                self.assertEqual(event["error"]["detail"], "Message not found in this conversation.")
                # A rejected cross-conversation read must not leak into recipient state.
                self.assertFalse(
                    await sync_to_async(
                        MessageStatus.objects.filter(message=other_message, user=self.mentor).exists
                    )()
                )
            finally:
                await self._disconnect_ws(communicator)

        async_to_sync(scenario)()

    def test_ws_message_read_rejects_non_participant_after_membership_removed(self):
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.mentor,
            message_text="should not be readable",
        )

        async def scenario():
            communicator = await self._ws_connect_with_session(self.student)
            # The consumer re-checks membership on every inbound event, so an already-open socket
            # should lose the ability to submit read receipts once membership is revoked.
            await self._remove_participation(self.student)

            try:
                await self._send_ws_json(
                    communicator,
                    {"type": "message.read", "message_id": message.id},
                )

                event = await self._receive_ws_event(communicator, "error")
                self.assertEqual(event["error"]["code"], "not_participant")
                # No MessageStatus row should be created when the membership guard blocks the read.
                self.assertFalse(
                    await sync_to_async(
                        MessageStatus.objects.filter(message=message, user=self.student).exists
                    )()
                )
            finally:
                await self._disconnect_ws(communicator)

        async_to_sync(scenario)()

    def test_ws_send_enqueues_chat_message_side_effects(self):
        with patch("apps.chat.management.consumers.enqueue_process_chat_message_created") as mock_enqueue:
            async def scenario():
                communicator = await self._ws_connect_with_session(self.student)
                try:
                    await self._send_ws_json(communicator, {"type": "message.send", "body": "queued"})
                    event = await self._receive_ws_event(communicator, "message.created")
                    mock_enqueue.assert_called_once_with(event["message"]["id"])
                finally:
                    await self._disconnect_ws(communicator)
            async_to_sync(scenario)()

    def test_ws_send_logs_enqueue_failure_without_blocking_delivery(self):
        with patch("apps.chat.tasks.process_chat_message_created.delay", side_effect=RuntimeError("broker down")):
            with self.assertLogs("apps.chat.tasks", level="ERROR") as captured:
                async def scenario():
                    sender_comm = await self._ws_connect_with_session(self.student)
                    listener_comm = await self._ws_connect_with_session(self.mentor)
                    try:
                        await self._send_ws_json(sender_comm, {"type": "message.send", "body": "still delivered"})
                        sender_event = await self._receive_ws_event(sender_comm, "message.created")
                        listener_event = await self._receive_ws_event(listener_comm, "message.created")
                        self.assertEqual(sender_event, listener_event)
                        self.assertTrue(await self._message_exists(sender_user=self.student, message_text="still delivered"))
                    finally:
                        await self._disconnect_ws(sender_comm)
                        await self._disconnect_ws(listener_comm)
                async_to_sync(scenario)()
        self.assertTrue(any("Failed to enqueue chat message created side effects" in line for line in captured.output))

    def test_ws_send_rejects_empty_message(self):
        async def scenario():
            communicator = await self._ws_connect_with_session(self.student)
            try:
                await self._send_ws_json(communicator, {"type": "message.send", "body": "   "})
                event = await self._receive_ws_event(communicator, "error")
                self.assertEqual(event["error"]["code"], "invalid_payload")
                self.assertEqual(event["error"]["detail"], "Message body cannot be empty.")
            finally:
                await self._disconnect_ws(communicator)
        async_to_sync(scenario)()

    def test_process_chat_message_created_creates_recipient_statuses_idempotently(self):
        message = Messages.objects.create(group=self.group, sender_user=self.student, message_text="task side effects")
        first_result = process_chat_message_created(message.id)
        second_result = process_chat_message_created(message.id)
        self.assertEqual(first_result["status"], "processed")
        self.assertCountEqual(first_result["recipient_ids"], [self.mentor.id, self.supervisor.id])
        self.assertEqual(first_result["created_status_count"], 2)
        self.assertEqual(first_result["existing_status_count"], 0)
        self.assertEqual(second_result["created_status_count"], 0)
        self.assertEqual(second_result["existing_status_count"], 2)
        self.assertEqual(MessageStatus.objects.filter(message=message).count(), 2)

    def test_ws_send_rejects_non_participant_after_membership_removed(self):
        async def scenario():
            communicator = await self._ws_connect_with_session(self.student)
            await self._remove_participation(self.student)
            try:
                await self._send_ws_json(communicator, {"type": "message.send", "body": "should fail"})
                event = await self._receive_ws_event(communicator, "error")
                self.assertEqual(event["error"]["code"], "not_participant")
                self.assertFalse(await self._message_exists(sender_user=self.student, message_text="should fail"))
            finally:
                await self._disconnect_ws(communicator)
        async_to_sync(scenario)()

    def test_ws_send_rejects_malformed_json(self):
        async def scenario():
            communicator = await self._ws_connect_with_session(self.student)
            try:
                await self._send_ws_text(communicator, '{"type": "message.send", ')
                event = await self._receive_ws_event(communicator, "error")
                self.assertEqual(event["error"]["code"], "invalid_json")
                self.assertEqual(event["error"]["detail"], "Malformed JSON payload.")
            finally:
                await self._disconnect_ws(communicator)
        async_to_sync(scenario)()


class TypingRateLimitTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()

        country = Countries.objects.create(country_name="Australia2")
        state = CountryStates.objects.create(country=country, state_name="VIC")
        track = Tracks.objects.create(track_name="AUS-VIC", state=state)

        self.user = User.objects.create_user(email="ratelimit@test.com", password="pass")
        self.group = Groups.objects.create(group_name="RateGroup", track=track)
        GroupMembership.objects.create(user=self.user, group=self.group)

    @patch("apps.chat.management.consumers.GroupChatConsumer.get_redis")
    def test_rate_limit_blocks_rapid_events(self, mock_get_redis):
        """Second typing event within 2s window should be blocked."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=[True, None])
        mock_get_redis.return_value = mock_redis

        consumer = GroupChatConsumer()
        consumer.group_id = self.group.id
        consumer.room_group_name = f"group_{self.group.id}"
        consumer.scope = {"user": self.user}
        consumer.channel_layer = AsyncMock()
        consumer.channel_layer.group_send = AsyncMock()

        async def run():
            await consumer._handle_typing({"status": "started"})
            await consumer._handle_typing({"status": "started"})

        async_to_sync(run)()
        self.assertEqual(consumer.channel_layer.group_send.call_count, 1)

    @patch("apps.chat.management.consumers.GroupChatConsumer.get_redis")
    def test_rate_limit_allows_after_window(self, mock_get_redis):
        """Typing event after 2s window should be allowed."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_redis

        consumer = GroupChatConsumer()
        consumer.group_id = self.group.id
        consumer.room_group_name = f"group_{self.group.id}"
        consumer.scope = {"user": self.user}
        consumer.channel_layer = AsyncMock()
        consumer.channel_layer.group_send = AsyncMock()

        async def run():
            await consumer._handle_typing({"status": "started"})
            await consumer._handle_typing({"status": "started"})

        async_to_sync(run)()
        self.assertEqual(consumer.channel_layer.group_send.call_count, 2)

    @patch("apps.chat.management.consumers.GroupChatConsumer.get_redis")
    def test_rate_limit_rejects_invalid_status(self, mock_get_redis):
        """Unknown status values should be silently dropped."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_get_redis.return_value = mock_redis

        consumer = GroupChatConsumer()
        consumer.group_id = self.group.id
        consumer.room_group_name = f"group_{self.group.id}"
        consumer.scope = {"user": self.user}
        consumer.channel_layer = AsyncMock()
        consumer.channel_layer.group_send = AsyncMock()

        async def run():
            await consumer._handle_typing({"status": "invalid_value"})

        async_to_sync(run)()
        self.assertEqual(consumer.channel_layer.group_send.call_count, 0)
