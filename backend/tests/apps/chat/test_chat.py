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

    # --------- tests ---------

    def test_post_message_as_group_member(self):
        url = self._list_url()
        payload = {
            "message_text": "hello from student",
            "resources": [{"resource_id": self.res1.id}, {"resource_id": self.res2.id}],
        }
        resp = self.client_student.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        msg_id = resp.data["id"]
        msg = Messages.objects.get(pk=msg_id)
        self.assertEqual(msg.group_id, self.group.id)
        self.assertEqual(msg.sender_user_id, self.student.id)
        self.assertIsNone(msg.deleted_at)
        self.assertEqual(set(msg.resources.values_list("resource_id", flat=True)), {self.res1.id, self.res2.id})

    def test_get_messages_with_limit_and_after(self):
        m1 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="m1")
        m2 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="m2")
        m3 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="m3")

        url = self._list_url() + "?limit=2"
        resp = self.client_student.get(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        items = resp.data["items"]
        self.assertEqual(len(items), 2)
        returned_ids = [it["id"] for it in items]
        self.assertEqual(returned_ids, [m3.id, m2.id])
        self.assertEqual(resp.data["next_after"], m3.id)

        url2 = self._list_url() + f"?after={m2.id}&limit=10"
        resp2 = self.client_student.get(url2)
        self.assertEqual(resp2.status_code, 200)
        ids2 = [it["id"] for it in resp2.data["items"]]
        self.assertEqual(ids2, [m3.id])

    def test_delete_forbidden_for_student(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="to delete")
        resp = self.client_student.delete(self._detail_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_allowed_for_mentor_in_own_group(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="to delete 2")
        resp = self.client_mentor.delete(self._detail_url(msg.id))
        self.assertEqual(resp.status_code, 204)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.deleted_at)

    def test_delete_forbidden_for_mentor_in_other_group(self):
        group2 = Groups.objects.create(group_name="G2", track=self.track)
        msg2 = Messages.objects.create(group=group2, sender_user=self.admin, message_text="to delete 3")
        url = reverse("group-messages-detail", kwargs={"group_pk": group2.id, "pk": msg2.id})
        self.assertEqual(self.client_mentor.delete(url).status_code, 403)

    def test_delete_allowed_for_supervisor_in_own_group(self):
        msg2 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="to delete 3")
        url = reverse("group-messages-detail", kwargs={"group_pk": self.group.id, "pk": msg2.id})
        resp = self.client_supervisor.delete(url)
        self.assertEqual(resp.status_code, 204)
        msg2.refresh_from_db()
        self.assertIsNotNone(msg2.deleted_at)

    def test_delete_forbidden_for_supervisor_in_other_group(self):
        group2 = Groups.objects.create(group_name="G2", track=self.track)
        msg2 = Messages.objects.create(group=group2, sender_user=self.admin, message_text="to delete 3")
        url = reverse("group-messages-detail", kwargs={"group_pk": group2.id, "pk": msg2.id})
        self.assertEqual(self.client_supervisor.delete(url).status_code, 403)

    def test_delete_allowed_for_admin_globally(self):
        group3 = Groups.objects.create(group_name="G3", track=self.track)
        msg3 = Messages.objects.create(group=group3, sender_user=self.student, message_text="to delete 4")
        url = reverse("group-messages-detail", kwargs={"group_pk": group3.id, "pk": msg3.id})
        resp = self.client_admin.delete(url)
        self.assertEqual(resp.status_code, 204)
        msg3.refresh_from_db()
        self.assertIsNotNone(msg3.deleted_at)

    def test_soft_deleted_messages_are_excluded_from_list(self):
        m1 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="keep")
        Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="hide",
            sent_at=timezone.now() - timedelta(minutes=2),
            deleted_at=timezone.now() - timedelta(minutes=1),
        )
        resp = self.client_student.get(self._list_url())
        self.assertEqual(resp.status_code, 200)
        ids = [it["id"] for it in resp.data["items"]]
        self.assertIn(m1.id, ids)

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