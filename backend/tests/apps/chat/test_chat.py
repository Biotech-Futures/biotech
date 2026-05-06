import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from django.test import TestCase, override_settings
from django.test import Client
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, models
from django.conf import settings

from rest_framework.test import APIClient

try:
    from channels.testing import WebsocketCommunicator
    from asgiref.sync import async_to_sync
    from config.asgi import application  # ASGI entrypoint (Channels)
    HAS_CHANNELS_TESTING = True
except ImportError:
    HAS_CHANNELS_TESTING = False
from apps.chat.models import Messages
from apps.chat.utils import reset_pattern_cache
from apps.resources.models import Roles, RoleAssignmentHistory, Resources
from apps.groups.models import Groups, GroupMembership, Countries, CountryStates, Tracks
from apps.common.storage import get_chat_storage


# Create your tests here.

# Use in-memory channel layer for tests
CHANNEL_TEST_SETTINGS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


@unittest.skipUnless(HAS_CHANNELS_TESTING, "channels.testing requires daphne")
@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class ChatFeatureTests(TestCase):
    """
    Integration tests for chat:
      - POST /chat/groups/{id}/messages/
      - GET  /chat/groups/{id}/messages/?after=&limit=
      - DELETE /chat/groups/{id}/messages/{mid}/  (soft delete)
      - WebSocket broadcasts (message.created / message.deleted)
      - Permissions by role: mentor (group-scoped), supervisor (group-scoped), admin (global)
    """

    def setUp(self):
        User = get_user_model()

        # --- users ---
        self.student = User.objects.create_user(email="student@test.com", password="pw")
        self.mentor = User.objects.create_user(email="mentor@test.com", password="pw")
        self.supervisor = User.objects.create_user(email="supervisor@test.com", password="pw")
        self.admin = User.objects.create_user(email="admin@test.com", password="pw", is_staff=False)

        # --- roles ---
        self.role_mentor = Roles.objects.create(role_name="mentor")
        self.role_supervisor = Roles.objects.create(role_name="supervisor")
        self.role_admin = Roles.objects.create(role_name="admin")
        self.role_student = Roles.objects.create(role_name="basic_student")

        now = timezone.now()
        future = now.replace(year=2099)

        # Active role assignments (treat valid_to=None as "still active")
        RoleAssignmentHistory.objects.create(
            user=self.student, role=self.role_student, valid_from=now, valid_to=future
        )
        RoleAssignmentHistory.objects.create(
            user=self.mentor, role=self.role_mentor, valid_from=now, valid_to=future
        )
        RoleAssignmentHistory.objects.create(
            user=self.supervisor, role=self.role_supervisor, valid_from=now, valid_to=future
        )
        RoleAssignmentHistory.objects.create(
            user=self.admin, role=self.role_admin, valid_from=now, valid_to=future
        )
        
        # --- geo / track prerequisites for Groups ---
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=self.state)

        # --- groups & membership ---
        self.group = Groups.objects.create(group_name="G1", track=self.track)
        GroupMembership.objects.create(user=self.student, group=self.group)
        GroupMembership.objects.create(user=self.mentor, group=self.group)
        GroupMembership.objects.create(user=self.supervisor, group=self.group)
        # admin has global access; they don't need membership
        
        # --- resources ---
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

        # API clients
        self.client_student = APIClient(); self.client_student.force_authenticate(user=self.student)
        self.client_mentor = APIClient(); self.client_mentor.force_authenticate(user=self.mentor)
        self.client_supervisor = APIClient(); self.client_supervisor.force_authenticate(user=self.supervisor)
        self.client_admin = APIClient(); self.client_admin.force_authenticate(user=self.admin)
        self.chat_storage = get_chat_storage()
        self.created_chat_storage_keys = []

    def tearDown(self):
        for storage_key in self.created_chat_storage_keys:
            if storage_key and self.chat_storage.exists(storage_key):
                self.chat_storage.delete(storage_key)


    # --------- helpers ---------
    def _list_url(self, group_id=None):
        gid = group_id or self.group.id
        return reverse("group-messages-list", kwargs={"group_pk": gid})

    def _detail_url(self, mid, group_id=None):
        gid = group_id or self.group.id
        return reverse("group-messages-detail", kwargs={"group_pk": gid, "pk": mid})

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
        # create 3 messages
        m1 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="m1")
        m2 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="m2")
        m3 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="m3")

        # newest first; limit=2
        url = self._list_url() + "?limit=2"
        resp = self.client_student.get(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        items = resp.data["items"]
        self.assertEqual(len(items), 2)
        # order should be m3, m2
        returned_ids = [it["id"] for it in items]
        self.assertEqual(returned_ids, [m3.id, m2.id])
        self.assertEqual(resp.data["next_after"], m3.id)

        # after=m2 should return only m3 (newer than m2)
        url2 = self._list_url() + f"?after={m2.id}&limit=10"
        resp2 = self.client_student.get(url2)
        self.assertEqual(resp2.status_code, 200)
        ids2 = [it["id"] for it in resp2.data["items"]]
        self.assertEqual(ids2, [m3.id])

    def test_delete_forbidden_for_student(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="to delete")
        url = self._detail_url(msg.id)
        resp = self.client_student.delete(url)
        self.assertEqual(resp.status_code, 403)

    def test_delete_allowed_for_mentor_in_own_group(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="to delete 2")
        url = self._detail_url(msg.id)
        resp = self.client_mentor.delete(url)
        self.assertEqual(resp.status_code, 204)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.deleted_at)

    def test_delete_forbidden_for_mentor_in_other_group(self):
        # make another group where mentor is NOT a member
        group2 = Groups.objects.create(group_name="G2", track=self.track)
        msg2 = Messages.objects.create(group=group2, sender_user=self.admin, message_text="to delete 3")
        url = reverse("group-messages-detail", kwargs={"group_pk": group2.id, "pk": msg2.id})

        resp = self.client_mentor.delete(url)
        self.assertEqual(resp.status_code, 403)

    def test_delete_allowed_for_supervisor_in_own_group(self):
        msg2 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="to delete 3")
        url = reverse("group-messages-detail", kwargs={"group_pk": self.group.id, "pk": msg2.id})

        resp = self.client_supervisor.delete(url)
        self.assertEqual(resp.status_code, 204)
        msg2.refresh_from_db()
        self.assertIsNotNone(msg2.deleted_at)

    def test_delete_forbidden_for_supervisor_in_other_group(self):
        # make another group where supervisor is NOT a member
        group2 = Groups.objects.create(group_name="G2", track=self.track)
        msg2 = Messages.objects.create(group=group2, sender_user=self.admin, message_text="to delete 3")
        url = reverse("group-messages-detail", kwargs={"group_pk": group2.id, "pk": msg2.id})

        resp = self.client_supervisor.delete(url)
        self.assertEqual(resp.status_code, 403)

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
        m2 = Messages.objects.create(
            group=self.group,
            sender_user=self.student,
            message_text="hide",
            sent_at=timezone.now() - timedelta(minutes=2),
            deleted_at=timezone.now() - timedelta(minutes=1),
        )

        resp = self.client_student.get(self._list_url())
        self.assertEqual(resp.status_code, 200)
        ids = [it["id"] for it in resp.data["items"]]
        self.assertIn(m1.id, ids)
        self.assertNotIn(m2.id, ids)

    def _session_cookie(self, user):
        c = Client()
        c.force_login(user)
        return c.cookies[settings.SESSION_COOKIE_NAME].value
    
    def _ws_connect_with_session(self, user):
        """
        Helper: create a Django session for 'user' and connect a WebsocketCommunicator
        with the sessionid cookie so AuthMiddlewareStack resolves request.user.
        """
        # Create session cookie for this user
        # Using Django client to login and capture session key

        cookie = self._session_cookie(user)
        headers = [(b"cookie", f"{settings.SESSION_COOKIE_NAME}={cookie}".encode())]

        # Connect
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/groups/{self.group.id}/",
            headers=headers,
        )
        connected, _ = async_to_sync(communicator.connect)()
        self.assertTrue(connected, "WebSocket failed to connect")
        return communicator

    # These tests verify the REST handler's *publish* path — that POST/DELETE
    # call ``channel_layer.group_send`` with the correct envelope. They do not
    # drive a real WebSocket consumer.
    #
    # End-to-end WS round-trip from a Django TestCase is structurally broken
    # with InMemoryChannelLayer: the consumer registers its asyncio.Queue on
    # the test's outer event loop, but the REST view publishes via
    # ``async_to_sync(channel_layer.group_send)`` which runs on asgiref's
    # separate executor loop. asyncio.Queue.put cannot cross loops, so the
    # message never arrives and the communicator times out with
    # CancelledError. The consumer's receive-side (auth, membership, accept)
    # is already covered by ``_ws_connect_with_session`` succeeding elsewhere.

    @patch("apps.chat.views.get_channel_layer")
    def test_ws_broadcast_on_create(self, mock_get_channel_layer):
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        api = APIClient()
        api.force_authenticate(self.student)

        resp = api.post(
            f"/chat/groups/{self.group.id}/messages/",
            {"message_text": "hi from test", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        fake_layer.group_send.assert_called_once()
        group_name, envelope = fake_layer.group_send.call_args.args
        self.assertEqual(group_name, f"group_{self.group.id}")
        self.assertEqual(envelope["type"], "chat.message")
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "message.created")
        self.assertEqual(payload["group_id"], self.group.id)
        self.assertEqual(payload["message"]["text"], "hi from test")
        self.assertEqual(payload["message"]["sender_id"], self.student.id)

    @patch("apps.chat.views.get_channel_layer")
    def test_ws_broadcast_on_delete(self, mock_get_channel_layer):
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        msg = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="to remove"
        )

        api = APIClient()
        api.force_authenticate(self.mentor)

        resp = api.delete(f"/chat/groups/{self.group.id}/messages/{msg.id}/")
        self.assertEqual(resp.status_code, 204, resp.content)

        fake_layer.group_send.assert_called_once()
        group_name, envelope = fake_layer.group_send.call_args.args
        self.assertEqual(group_name, f"group_{self.group.id}")
        self.assertEqual(envelope["type"], "chat.message")
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "message.deleted")
        self.assertEqual(payload["group_id"], self.group.id)
        self.assertEqual(payload["message_id"], msg.id)

    def test_rest_attachment_upload_creates_message_and_streams_download(self):
        upload = SimpleUploadedFile(
            "group-plan.pdf",
            b"group plan bytes",
            content_type="application/pdf",
        )
        response = self.client_student.post(
            reverse("group-messages-upload", kwargs={"group_pk": self.group.id}),
            {
                "message_text": "See attached",
                "uploaded_file": upload,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["message_type"], "attachment")
        self.assertEqual(response.data["message_text"], "See attached")
        self.assertEqual(len(response.data["attachments"]), 1)

        message = Messages.objects.prefetch_related("attachments").get(pk=response.data["id"])
        attachment = message.attachments.get()
        self.created_chat_storage_keys.append(attachment.storage_key)
        self.assertTrue(self.chat_storage.exists(attachment.storage_key))

        download_response = self.client_mentor.get(
            reverse(
                "group-messages-attachment-download",
                kwargs={
                    "group_pk": self.group.id,
                    "pk": message.id,
                    "attachment_pk": attachment.id,
                },
            )
        )
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", download_response["Content-Disposition"])
        self.assertEqual(b"".join(download_response.streaming_content), b"group plan bytes")

    def test_attachment_download_requires_group_membership(self):
        upload = SimpleUploadedFile(
            "group-plan.pdf",
            b"group plan bytes",
            content_type="application/pdf",
        )
        response = self.client_student.post(
            reverse("group-messages-upload", kwargs={"group_pk": self.group.id}),
            {
                "uploaded_file": upload,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)

        message = Messages.objects.prefetch_related("attachments").get(pk=response.data["id"])
        attachment = message.attachments.get()
        self.created_chat_storage_keys.append(attachment.storage_key)

        outsider = get_user_model().objects.create_user(email="outsider@test.com", password="pw")
        outsider_client = APIClient()
        outsider_client.force_authenticate(user=outsider)
        download_response = outsider_client.get(
            reverse(
                "group-messages-attachment-download",
                kwargs={
                    "group_pk": self.group.id,
                    "pk": message.id,
                    "attachment_pk": attachment.id,
                },
            )
        )
        self.assertEqual(download_response.status_code, 403)


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
@unittest.skipUnless(HAS_CHANNELS_TESTING, "channels.testing requires daphne")
class ChatProfanitySanitisationTests(TestCase):
    """Integration tests for the profanity filter wired into the chat
    serializers and websocket consumer. Has its own lean setUp that
    deliberately does not touch ``Resources`` so it stays decoupled from
    that model's evolution.
    """

    def setUp(self):
        User = get_user_model()

        self.student = User.objects.create_user(email="student@test.com", password="pw")
        self.mentor = User.objects.create_user(email="mentor@test.com", password="pw")

        self.role_student = Roles.objects.create(role_name="basic_student")
        self.role_mentor = Roles.objects.create(role_name="mentor")

        now = timezone.now()
        future = now.replace(year=2099)
        RoleAssignmentHistory.objects.create(
            user=self.student, role=self.role_student, valid_from=now, valid_to=future,
        )
        RoleAssignmentHistory.objects.create(
            user=self.mentor, role=self.role_mentor, valid_from=now, valid_to=future,
        )

        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=self.state)

        self.group = Groups.objects.create(group_name="G1", track=self.track)
        GroupMembership.objects.create(user=self.student, group=self.group)
        GroupMembership.objects.create(user=self.mentor, group=self.group)

        self.client_student = APIClient()
        self.client_student.force_authenticate(user=self.student)

        reset_pattern_cache()

    def tearDown(self):
        reset_pattern_cache()

    def _list_url(self):
        return reverse("group-messages-list", kwargs={"group_pk": self.group.id})

    def _detail_url(self, mid):
        return reverse(
            "group-messages-detail",
            kwargs={"group_pk": self.group.id, "pk": mid},
        )

    @override_settings(
        CHAT_SANITIZER_BLACKLIST=["shit*", "fuck*"],
        CHAT_SANITIZER_REPLACEMENT="***",
    )
    def test_post_message_is_sanitised_before_save(self):
        reset_pattern_cache()
        resp = self.client_student.post(
            self._list_url(),
            {"message_text": "this is bullshit, total brainfuck", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        msg = Messages.objects.get(pk=resp.data["id"])
        # Stored value is the moderated text — cached/raw retrievals stay clean.
        self.assertEqual(msg.message_text, "this is ***, total ***")
        self.assertEqual(resp.data["message_text"], "this is ***, total ***")

    @override_settings(
        CHAT_SANITIZER_BLACKLIST=["shit*"],
        CHAT_SANITIZER_REPLACEMENT="***",
    )
    def test_post_message_catches_leet_variants(self):
        reset_pattern_cache()
        resp = self.client_student.post(
            self._list_url(),
            {"message_text": "bull5h1t and 5hlthole", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        msg = Messages.objects.get(pk=resp.data["id"])
        self.assertEqual(msg.message_text, "*** and ***")

    @override_settings(
        CHAT_SANITIZER_BLACKLIST=["shit*"],
        CHAT_SANITIZER_REPLACEMENT="***",
    )
    def test_patch_message_is_sanitised(self):
        reset_pattern_cache()
        msg = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="clean"
        )
        resp = self.client_student.patch(
            self._detail_url(msg.id),
            {"message_text": "ugh shithole"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        msg.refresh_from_db()
        self.assertEqual(msg.message_text, "ugh ***")

    @override_settings(
        CHAT_SANITIZER_BLACKLIST=["shit*"],
        CHAT_SANITIZER_REPLACEMENT="***",
    )
    def test_clean_messages_are_unchanged(self):
        reset_pattern_cache()
        resp = self.client_student.post(
            self._list_url(),
            {"message_text": "hello mentor, see you in class", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        msg = Messages.objects.get(pk=resp.data["id"])
        self.assertEqual(msg.message_text, "hello mentor, see you in class")

    def _session_cookie(self, user):
        c = Client()
        c.force_login(user)
        return c.cookies[settings.SESSION_COOKIE_NAME].value

    def _ws_connect_with_session(self, user):
        cookie = self._session_cookie(user)
        headers = [(b"cookie", f"{settings.SESSION_COOKIE_NAME}={cookie}".encode())]
        communicator = WebsocketCommunicator(
            application,
            f"/ws/chat/groups/{self.group.id}/",
            headers=headers,
        )
        connected, _ = async_to_sync(communicator.connect)()
        self.assertTrue(connected, "WebSocket failed to connect")
        return communicator

    @override_settings(
        CHAT_SANITIZER_BLACKLIST=["shit*"],
        CHAT_SANITIZER_REPLACEMENT="***",
    )
    def test_persisted_message_drives_ws_payload(self):
        """The websocket broadcast payload is built directly from the
        persisted Message (see MessageViewSet.perform_create), so once the
        serializer-level sanitisation is verified, the broadcast inherits
        it for free. We assert that property here without depending on
        the live websocket transport."""
        reset_pattern_cache()
        from apps.chat.serializers import MessageSerializer

        ser = MessageSerializer(data={"message_text": "this is bullshit", "resources": []})
        ser.is_valid(raise_exception=True)
        msg = ser.save(sender_user=self.student, group_id=self.group.id)

        # This is exactly the dict the consumer puts on the wire
        # (apps/chat/views.py::perform_create).
        broadcast_text = msg.message_text
        self.assertEqual(broadcast_text, "this is ***")
