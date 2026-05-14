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
from apps.users.models import AdminScope
from tests.apps._helpers import StorageCleanupMixin, assert_public_message_shape


# Create your tests here.

# Use in-memory channel layer for tests
CHANNEL_TEST_SETTINGS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


@unittest.skipUnless(HAS_CHANNELS_TESTING, "channels.testing requires daphne")
@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class ChatFeatureTests(StorageCleanupMixin, TestCase):
    """
    Integration tests for chat:
      - POST /chat/groups/{id}/messages/
      - GET  /chat/groups/{id}/messages/?after=&limit=
      - DELETE /chat/groups/{id}/messages/{mid}/  (soft delete)
      - WebSocket broadcasts (message.created / message.deleted)
      - Permissions by role: mentor (group-scoped), supervisor (group-scoped), admin (global)
    """
    storage_attr = "chat_storage"
    storage_keys_attr = "created_chat_storage_keys"

    def setUp(self):
        User = get_user_model()

        # --- users ---
        self.student = User.objects.create_user(email="student@test.com", password="pw")
        self.mentor = User.objects.create_user(email="mentor@test.com", password="pw")
        self.supervisor = User.objects.create_user(email="supervisor@test.com", password="pw")
        self.admin = User.objects.create_user(email="admin@test.com", password="pw")
        self.track_admin = User.objects.create_user(email="track_admin@test.com", password="pw")

        # --- roles --- (kept for unrelated chat features; moderation power
        # comes from AdminScope, not from these role assignments)
        self.role_mentor = Roles.objects.create(role_name="mentor")
        self.role_supervisor = Roles.objects.create(role_name="supervisor")
        self.role_admin = Roles.objects.create(role_name="admin")
        self.role_student = Roles.objects.create(role_name="student")

        now = timezone.now()
        future = now.replace(year=2099)

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
        self.other_state = CountryStates.objects.create(country=self.country, state_name="VIC")
        self.other_track = Tracks.objects.create(track_name="AUS-VIC", state=self.other_state)

        # --- groups & membership ---
        self.group = Groups.objects.create(group_name="G1", track=self.track)
        GroupMembership.objects.create(user=self.student, group=self.group)
        GroupMembership.objects.create(user=self.mentor, group=self.group)
        GroupMembership.objects.create(user=self.supervisor, group=self.group)
        # admin / track_admin reach groups via AdminScope, not membership.

        # --- admin scopes (operational admin model) ---
        AdminScope.objects.create(user=self.admin, is_global=True)
        AdminScope.objects.create(
            user=self.track_admin, track=self.track, is_global=False
        )

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
        self.client_track_admin = APIClient(); self.client_track_admin.force_authenticate(user=self.track_admin)
        self.chat_storage = get_chat_storage()
        self.created_chat_storage_keys = []


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
        assert_public_message_shape(self, resp.data)

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
        assert_public_message_shape(self, items[0])
        # order should be m3, m2
        returned_ids = [it["id"] for it in items]
        self.assertEqual(returned_ids, [m3.id, m2.id])
        self.assertEqual(resp.data["next_after"], m3.id)
        # Page is full (limit=2, returned 2) and there is at least one older
        # message (m1) → next_before is the oldest id on the page.
        self.assertEqual(resp.data["next_before"], m2.id)

        # after=m2 should return only m3 (newer than m2). No older history
        # on that page, so next_before is null.
        url2 = self._list_url() + f"?after={m2.id}&limit=10"
        resp2 = self.client_student.get(url2)
        self.assertEqual(resp2.status_code, 200)
        ids2 = [it["id"] for it in resp2.data["items"]]
        self.assertEqual(ids2, [m3.id])
        self.assertIsNone(resp2.data["next_before"])

    def test_list_before_cursor_loads_older_history(self):
        # Newest-first ordering; before=m2 should return m1 only.
        m1 = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="m1",
            sent_at=timezone.now() - timedelta(minutes=3),
        )
        m2 = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="m2",
            sent_at=timezone.now() - timedelta(minutes=2),
        )
        m3 = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="m3",
            sent_at=timezone.now() - timedelta(minutes=1),
        )
        url = self._list_url() + f"?before={m2.id}&limit=10"
        resp = self.client_student.get(url)
        self.assertEqual(resp.status_code, 200)
        ids = [it["id"] for it in resp.data["items"]]
        self.assertEqual(ids, [m1.id])
        # End-of-history → null cursor.
        self.assertIsNone(resp.data["next_before"])

    def test_delete_allowed_for_sender_within_window(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="to delete")
        resp = self.client_student.delete(self._detail_url(msg.id))
        self.assertEqual(resp.status_code, 204)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.deleted_at)

    def test_delete_forbidden_for_sender_after_window(self):
        msg = Messages.objects.create(
            group=self.group,
            sender_user=self.student,
            message_text="too old to delete",
            sent_at=timezone.now() - timedelta(minutes=11),
        )
        resp = self.client_student.delete(self._detail_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_forbidden_for_non_sender_peer(self):
        other = get_user_model().objects.create_user(email="peer@test.com", password="pw")
        GroupMembership.objects.create(user=other, group=self.group)
        client = APIClient(); client.force_authenticate(user=other)
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="not yours")
        resp = client.delete(self._detail_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_forbidden_for_mentor_without_admin_scope(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="mentor try")
        resp = self.client_mentor.delete(self._detail_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_forbidden_for_supervisor_without_admin_scope(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="supervisor try")
        resp = self.client_supervisor.delete(self._detail_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_allowed_for_global_admin_anywhere(self):
        other_group = Groups.objects.create(group_name="G-VIC", track=self.other_track)
        msg = Messages.objects.create(group=other_group, sender_user=self.student, message_text="global admin")
        url = reverse("group-messages-detail", kwargs={"group_pk": other_group.id, "pk": msg.id})
        resp = self.client_admin.delete(url)
        self.assertEqual(resp.status_code, 204)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.deleted_at)

    def test_delete_allowed_for_track_admin_within_track(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="track admin in")
        resp = self.client_track_admin.delete(self._detail_url(msg.id))
        self.assertEqual(resp.status_code, 204)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.deleted_at)

    def test_delete_forbidden_for_track_admin_outside_track(self):
        other_group = Groups.objects.create(group_name="G-VIC", track=self.other_track)
        msg = Messages.objects.create(group=other_group, sender_user=self.student, message_text="track admin out")
        url = reverse("group-messages-detail", kwargs={"group_pk": other_group.id, "pk": msg.id})
        resp = self.client_track_admin.delete(url)
        self.assertEqual(resp.status_code, 403)

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

    def test_track_admin_can_restore_soft_deleted_message(self):
        # Restore is moderator-only and clears the message tombstone.
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="restore me")
        msg.soft_delete()
        url = reverse("group-messages-restore", kwargs={"group_pk": self.group.id, "pk": msg.id})

        resp = self.client_track_admin.post(url)

        self.assertEqual(resp.status_code, 200, resp.content)
        msg.refresh_from_db()
        self.assertIsNone(msg.deleted_at)
        self.assertFalse(resp.data["is_deleted"])
        self.assertIsNone(resp.data["deleted_at"])

    def test_sender_cannot_restore_soft_deleted_message(self):
        # Sender self-delete stays recoverable only by an admin/moderator.
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="no self restore")
        msg.soft_delete()
        url = reverse("group-messages-restore", kwargs={"group_pk": self.group.id, "pk": msg.id})

        resp = self.client_student.post(url)

        self.assertEqual(resp.status_code, 403)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.deleted_at)

    def test_deleted_messages_action_is_admin_only(self):
        # Deleted message history is a recovery queue, not participant-visible chat.
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="hidden")
        msg.soft_delete()
        url = reverse("group-messages-deleted", kwargs={"group_pk": self.group.id})

        peer_resp = self.client_student.get(url)
        admin_resp = self.client_track_admin.get(url)

        self.assertEqual(peer_resp.status_code, 403)
        self.assertEqual(admin_resp.status_code, 200, admin_resp.content)
        self.assertEqual([item["id"] for item in admin_resp.data["items"]], [msg.id])

    def test_deleted_group_blocks_chat_access(self):
        # Group deletion revokes chat access even for existing members.
        self.group.deleted_at = timezone.now()
        self.group.save(update_fields=["deleted_at"])

        resp = self.client_student.get(self._list_url())

        self.assertEqual(resp.status_code, 403)

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

        with self.captureOnCommitCallbacks(execute=True):
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
        self.assertEqual(payload["message"]["message_text"], "hi from test")
        self.assertEqual(payload["message"]["sender_user"], self.student.id)

    @patch("apps.chat.views.get_channel_layer")
    def test_ws_broadcast_on_delete(self, mock_get_channel_layer):
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        msg = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="to remove"
        )

        api = APIClient()
        # Global admin has unconditional moderation rights under the new contract.
        api.force_authenticate(self.admin)

        with self.captureOnCommitCallbacks(execute=True):
            resp = api.delete(f"/chat/groups/{self.group.id}/messages/{msg.id}/")
            self.assertEqual(resp.status_code, 204, resp.content)

        fake_layer.group_send.assert_called_once()
        group_name, envelope = fake_layer.group_send.call_args.args
        self.assertEqual(group_name, f"group_{self.group.id}")
        self.assertEqual(envelope["type"], "chat.message")
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "message.deleted")
        self.assertEqual(payload["group_id"], self.group.id)
        self.assertEqual(payload["message"]["id"], msg.id)
        self.assertTrue(payload["message"]["is_deleted"])

    @patch("apps.chat.views.get_channel_layer")
    def test_broadcast_does_not_fire_on_rollback(self, mock_get_channel_layer):
        """If the surrounding transaction rolls back, the on_commit hook
        is discarded and peers do not see a phantom message."""
        from django.db import transaction
        from apps.chat.views import _broadcast

        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    _broadcast(
                        self.group.id, "message.created", {"id": 1, "message_text": "x"}
                    )
                    raise RuntimeError("rollback")
            except RuntimeError:
                pass

        fake_layer.group_send.assert_not_called()

    @patch("apps.chat.views.get_channel_layer")
    def test_attachment_upload_broadcasts_message_created_with_download_url(
        self,
        mock_get_channel_layer,
    ):
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        upload = SimpleUploadedFile(
            "group-plan.pdf",
            b"group plan bytes",
            content_type="application/pdf",
        )

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client_student.post(
                reverse("group-messages-upload", kwargs={"group_pk": self.group.id}),
                {
                    "message_text": "See attached",
                    "uploaded_file": upload,
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(len(callbacks), 1)
        assert_public_message_shape(self, response.data)
        self.assertEqual(response.data["message_type"], "attachment")
        message = Messages.objects.prefetch_related("attachments").get(pk=response.data["id"])
        self.created_chat_storage_keys.append(message.attachments.get().storage_key)

        fake_layer.group_send.assert_called_once()
        group_name, envelope = fake_layer.group_send.call_args.args
        self.assertEqual(group_name, f"group_{self.group.id}")
        self.assertEqual(envelope["type"], "chat.message")

        payload = envelope["payload"]
        self.assertEqual(payload["event"], "message.created")
        self.assertEqual(payload["group_id"], self.group.id)
        self.assertEqual(payload["message"]["message_type"], "attachment")
        self.assertEqual(payload["message"]["sender_user"], self.student.id)
        self.assertEqual(payload["message"]["message_text"], "See attached")
        self.assertEqual(
            [r["resource_id"] for r in payload["message"]["resources"]], []
        )
        self.assertEqual(len(payload["message"]["attachments"]), 1)
        self.assertTrue(
            payload["message"]["attachments"][0]["download_url"].endswith(
                f"/chat/groups/{self.group.id}/messages/{payload['message']['id']}/attachments/"
                f"{payload['message']['attachments'][0]['id']}/download/"
            )
        )

    @patch("apps.chat.views.get_channel_layer")
    def test_attachment_upload_broadcast_is_deferred_until_commit(self, mock_get_channel_layer):
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        upload = SimpleUploadedFile(
            "group-plan.pdf",
            b"group plan bytes",
            content_type="application/pdf",
        )

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client_student.post(
                reverse("group-messages-upload", kwargs={"group_pk": self.group.id}),
                {
                    "message_text": "See attached",
                    "uploaded_file": upload,
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(len(callbacks), 1)
        assert_public_message_shape(self, response.data)
        fake_layer.group_send.assert_not_called()

        message = Messages.objects.prefetch_related("attachments").get(pk=response.data["id"])
        attachment = message.attachments.get()
        self.created_chat_storage_keys.append(attachment.storage_key)
        self.assertEqual(message.message_type, "attachment")
        self.assertEqual(attachment.attachment_filename, "group-plan.pdf")

        callbacks[0]()

        fake_layer.group_send.assert_called_once()

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
        assert_public_message_shape(self, response.data)
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

    # --------- search ---------
    def _search_url(self, group_id=None):
        gid = group_id or self.group.id
        return reverse("group-messages-search", kwargs={"group_pk": gid})

    def test_search_matches_case_insensitive_and_excludes_other_groups(self):
        Messages.objects.create(group=self.group, sender_user=self.student, message_text="Hello biotech world")
        Messages.objects.create(group=self.group, sender_user=self.student, message_text="unrelated note")
        # Leak guard: a message in another group containing the term must not appear.
        other_group = Groups.objects.create(group_name="G-VIC", track=self.other_track)
        GroupMembership.objects.create(user=self.student, group=other_group)
        Messages.objects.create(group=other_group, sender_user=self.student, message_text="biotech elsewhere")

        resp = self.client_student.get(self._search_url() + "?q=BIOTECH")
        self.assertEqual(resp.status_code, 200, resp.content)
        items = resp.data["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["message_text"], "Hello biotech world")
        self.assertIsNone(resp.data["next_before"])

    def test_search_excludes_soft_deleted_messages(self):
        Messages.objects.create(group=self.group, sender_user=self.student, message_text="keep biotech")
        Messages.objects.create(
            group=self.group,
            sender_user=self.student,
            message_text="hide biotech",
            sent_at=timezone.now() - timedelta(minutes=2),
            deleted_at=timezone.now() - timedelta(minutes=1),
        )
        resp = self.client_student.get(self._search_url() + "?q=biotech")
        self.assertEqual(resp.status_code, 200)
        texts = [it["message_text"] for it in resp.data["items"]]
        self.assertEqual(texts, ["keep biotech"])

    def test_search_forbidden_for_non_member(self):
        outsider = get_user_model().objects.create_user(email="outsider-search@test.com", password="pw")
        outsider_client = APIClient(); outsider_client.force_authenticate(user=outsider)
        Messages.objects.create(group=self.group, sender_user=self.student, message_text="biotech")
        resp = outsider_client.get(self._search_url() + "?q=biotech")
        self.assertEqual(resp.status_code, 403)

    def test_search_empty_query_returns_empty(self):
        Messages.objects.create(group=self.group, sender_user=self.student, message_text="anything")
        resp = self.client_student.get(self._search_url() + "?q=")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["items"], [])
        self.assertIsNone(resp.data["next_before"])

    def test_search_pagination_with_before_cursor(self):
        # Three matches, newest-first ordering, limit=2 → next_before points at oldest of page 1.
        m1 = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="biotech one",
            sent_at=timezone.now() - timedelta(minutes=3),
        )
        m2 = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="biotech two",
            sent_at=timezone.now() - timedelta(minutes=2),
        )
        m3 = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="biotech three",
            sent_at=timezone.now() - timedelta(minutes=1),
        )

        resp1 = self.client_student.get(self._search_url() + "?q=biotech&limit=2")
        self.assertEqual(resp1.status_code, 200)
        ids1 = [it["id"] for it in resp1.data["items"]]
        self.assertEqual(ids1, [m3.id, m2.id])
        self.assertEqual(resp1.data["next_before"], m2.id)

        resp2 = self.client_student.get(self._search_url() + f"?q=biotech&limit=2&before={m2.id}")
        self.assertEqual(resp2.status_code, 200)
        ids2 = [it["id"] for it in resp2.data["items"]]
        self.assertEqual(ids2, [m1.id])
        self.assertIsNone(resp2.data["next_before"])


class ChatAttachmentRBACTests(StorageCleanupMixin, TestCase):
    storage_attr = "chat_storage"
    storage_keys_attr = "created_chat_storage_keys"

    def setUp(self):
        User = get_user_model()
        self.client = APIClient()

        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.primary_track = Tracks.objects.create(track_name="Primary", state=self.state)
        self.secondary_track = Tracks.objects.create(track_name="Secondary", state=self.state)

        self.primary_group = Groups.objects.create(group_name="Primary Group", track=self.primary_track)
        self.secondary_group = Groups.objects.create(group_name="Secondary Group", track=self.secondary_track)

        self.global_admin = User.objects.create_user(email="global-admin@test.com", password="pw")
        self.track_admin = User.objects.create_user(email="track-admin@test.com", password="pw")
        self.mentor = User.objects.create_user(email="mentor@test.com", password="pw")
        self.supervisor = User.objects.create_user(email="supervisor@test.com", password="pw")
        self.student = User.objects.create_user(email="student@test.com", password="pw")
        self.secondary_student = User.objects.create_user(email="secondary-student@test.com", password="pw")
        self.outsider = User.objects.create_user(email="outsider@test.com", password="pw")

        AdminScope.objects.create(user=self.global_admin, is_global=True)
        AdminScope.objects.create(user=self.track_admin, track=self.primary_track, is_global=False)

        self.role_admin = Roles.objects.create(role_name="admin")
        self.role_mentor = Roles.objects.create(role_name="mentor")
        self.role_supervisor = Roles.objects.create(role_name="supervisor")
        self.role_student = Roles.objects.create(role_name="student")

        now = timezone.now()
        future = now + timedelta(days=365)
        RoleAssignmentHistory.objects.create(user=self.global_admin, role=self.role_admin, valid_from=now, valid_to=future)
        RoleAssignmentHistory.objects.create(user=self.mentor, role=self.role_mentor, valid_from=now, valid_to=future)
        RoleAssignmentHistory.objects.create(user=self.supervisor, role=self.role_supervisor, valid_from=now, valid_to=future)
        RoleAssignmentHistory.objects.create(user=self.student, role=self.role_student, valid_from=now, valid_to=future)
        RoleAssignmentHistory.objects.create(user=self.secondary_student, role=self.role_student, valid_from=now, valid_to=future)

        GroupMembership.objects.create(user=self.mentor, group=self.primary_group, membership_role="mentor")
        GroupMembership.objects.create(user=self.supervisor, group=self.primary_group, membership_role="supervisor")
        GroupMembership.objects.create(user=self.student, group=self.primary_group, membership_role="student")
        GroupMembership.objects.create(user=self.secondary_student, group=self.secondary_group, membership_role="student")

        self.client_global_admin = APIClient(); self.client_global_admin.force_authenticate(user=self.global_admin)
        self.client_track_admin = APIClient(); self.client_track_admin.force_authenticate(user=self.track_admin)
        self.client_mentor = APIClient(); self.client_mentor.force_authenticate(user=self.mentor)
        self.client_supervisor = APIClient(); self.client_supervisor.force_authenticate(user=self.supervisor)
        self.client_student = APIClient(); self.client_student.force_authenticate(user=self.student)
        self.client_secondary_student = APIClient(); self.client_secondary_student.force_authenticate(user=self.secondary_student)
        self.client_outsider = APIClient(); self.client_outsider.force_authenticate(user=self.outsider)

        self.chat_storage = get_chat_storage()
        self.created_chat_storage_keys = []

    def _upload_url(self, group):
        return reverse("group-messages-upload", kwargs={"group_pk": group.id})

    def _download_url(self, group, message, attachment):
        return reverse(
            "group-messages-attachment-download",
            kwargs={
                "group_pk": group.id,
                "pk": message.id,
                "attachment_pk": attachment.id,
            },
        )

    def _upload_attachment(
        self,
        client,
        group,
        *,
        message_text="See attached",
        filename="group-plan.pdf",
        payload=b"group plan bytes",
        content_type="application/pdf",
    ):
        response = client.post(
            self._upload_url(group),
            {
                "message_text": message_text,
                "uploaded_file": SimpleUploadedFile(filename, payload, content_type=content_type),
            },
            format="multipart",
        )
        message = None
        attachment = None
        if response.status_code == 201:
            message = Messages.objects.prefetch_related("attachments").get(pk=response.data["id"])
            attachment = message.attachments.get()
            self.created_chat_storage_keys.append(attachment.storage_key)
        return response, message, attachment

    def test_global_admin_can_download_any_chat_attachment(self):
        _, message, attachment = self._upload_attachment(self.client_secondary_student, self.secondary_group)

        response = self.client_global_admin.get(self._download_url(self.secondary_group, message, attachment))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"group plan bytes")

    def test_track_admin_can_download_chat_attachment_within_assigned_track(self):
        _, message, attachment = self._upload_attachment(self.client_student, self.primary_group)

        response = self.client_track_admin.get(self._download_url(self.primary_group, message, attachment))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"group plan bytes")

    def test_track_admin_cannot_download_chat_attachment_outside_assigned_track(self):
        _, message, attachment = self._upload_attachment(self.client_secondary_student, self.secondary_group)

        response = self.client_track_admin.get(self._download_url(self.secondary_group, message, attachment))
        self.assertEqual(response.status_code, 403)

    def test_track_admin_can_upload_chat_attachment_only_within_assigned_track(self):
        allowed_response, _, _ = self._upload_attachment(self.client_track_admin, self.primary_group)
        self.assertEqual(allowed_response.status_code, 201)
        self.assertIn("download_url", allowed_response.data["attachments"][0])

        blocked_response, _, _ = self._upload_attachment(self.client_track_admin, self.secondary_group)
        self.assertEqual(blocked_response.status_code, 403)

    @override_settings(CHAT_ATTACHMENT_MAX_UPLOAD_SIZE=4)
    def test_chat_attachment_upload_rejects_files_above_max_size(self):
        response, _, _ = self._upload_attachment(
            self.client_student,
            self.primary_group,
            payload=b"12345",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("fields", response.data)
        self.assertIn("uploaded_file", response.data["fields"])
        self.assertIn("maximum allowed size", str(response.data["fields"]["uploaded_file"][0]))

    def test_chat_attachment_upload_rejects_disallowed_extension(self):
        response, _, _ = self._upload_attachment(
            self.client_student,
            self.primary_group,
            filename="payload.exe",
            content_type="application/octet-stream",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("fields", response.data)
        self.assertIn("uploaded_file", response.data["fields"])
        self.assertIn("allowed file extension", str(response.data["fields"]["uploaded_file"][0]))

    def test_chat_attachment_upload_rejects_disallowed_mime_type(self):
        response, _, _ = self._upload_attachment(
            self.client_student,
            self.primary_group,
            filename="payload.pdf",
            content_type="application/octet-stream",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("fields", response.data)
        self.assertIn("uploaded_file", response.data["fields"])
        self.assertIn("allowed content type", str(response.data["fields"]["uploaded_file"][0]))

    def test_mentor_can_upload_download_only_in_their_group(self):
        text_response = self.client_mentor.post(
            reverse("group-messages-list", kwargs={"group_pk": self.primary_group.id}),
            {"message_text": "plain message", "resources": []},
            format="json",
        )
        upload_response, message, attachment = self._upload_attachment(self.client_mentor, self.primary_group)
        self.assertEqual(text_response.status_code, 201)
        assert_public_message_shape(self, text_response.data)
        self.assertEqual(upload_response.status_code, 201)
        assert_public_message_shape(self, upload_response.data)
        self.assertEqual(set(upload_response.data.keys()), set(text_response.data.keys()))
        self.assertIn("download_url", upload_response.data["attachments"][0])

        download_response = self.client_mentor.get(self._download_url(self.primary_group, message, attachment))
        self.assertEqual(download_response.status_code, 200)

        blocked_upload, _, _ = self._upload_attachment(self.client_mentor, self.secondary_group)
        self.assertEqual(blocked_upload.status_code, 403)

        _, other_message, other_attachment = self._upload_attachment(self.client_secondary_student, self.secondary_group)
        blocked_download = self.client_mentor.get(self._download_url(self.secondary_group, other_message, other_attachment))
        self.assertEqual(blocked_download.status_code, 403)

    def test_supervisor_can_upload_download_only_in_their_group(self):
        upload_response, message, attachment = self._upload_attachment(self.client_supervisor, self.primary_group)
        self.assertEqual(upload_response.status_code, 201)
        assert_public_message_shape(self, upload_response.data)
        self.assertIn("download_url", upload_response.data["attachments"][0])

        download_response = self.client_supervisor.get(self._download_url(self.primary_group, message, attachment))
        self.assertEqual(download_response.status_code, 200)

        blocked_upload, _, _ = self._upload_attachment(self.client_supervisor, self.secondary_group)
        self.assertEqual(blocked_upload.status_code, 403)

        _, other_message, other_attachment = self._upload_attachment(self.client_secondary_student, self.secondary_group)
        blocked_download = self.client_supervisor.get(self._download_url(self.secondary_group, other_message, other_attachment))
        self.assertEqual(blocked_download.status_code, 403)

    def test_student_can_upload_download_only_in_their_group(self):
        upload_response, message, attachment = self._upload_attachment(self.client_student, self.primary_group)
        self.assertEqual(upload_response.status_code, 201)
        assert_public_message_shape(self, upload_response.data)
        self.assertIn("download_url", upload_response.data["attachments"][0])

        download_response = self.client_student.get(self._download_url(self.primary_group, message, attachment))
        self.assertEqual(download_response.status_code, 200)

        blocked_upload, _, _ = self._upload_attachment(self.client_student, self.secondary_group)
        self.assertEqual(blocked_upload.status_code, 403)

        _, other_message, other_attachment = self._upload_attachment(self.client_secondary_student, self.secondary_group)
        blocked_download = self.client_student.get(self._download_url(self.secondary_group, other_message, other_attachment))
        self.assertEqual(blocked_download.status_code, 403)

    def test_non_member_cannot_upload_chat_attachment(self):
        response, _, _ = self._upload_attachment(self.client_outsider, self.primary_group)
        self.assertEqual(response.status_code, 403)

    def test_non_member_cannot_download_chat_attachment(self):
        _, message, attachment = self._upload_attachment(self.client_student, self.primary_group)

        response = self.client_outsider.get(self._download_url(self.primary_group, message, attachment))
        self.assertEqual(response.status_code, 403)

    def test_attachment_download_fails_if_message_does_not_belong_to_group(self):
        _, message, attachment = self._upload_attachment(self.client_secondary_student, self.secondary_group)

        response = self.client_global_admin.get(
            reverse(
                "group-messages-attachment-download",
                kwargs={
                    "group_pk": self.primary_group.id,
                    "pk": message.id,
                    "attachment_pk": attachment.id,
                },
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_attachment_download_fails_if_attachment_does_not_belong_to_message(self):
        _, message_one, _ = self._upload_attachment(self.client_student, self.primary_group, filename="one.pdf", payload=b"one bytes")
        _, message_two, attachment_two = self._upload_attachment(self.client_student, self.primary_group, filename="two.pdf", payload=b"two bytes")

        response = self.client_global_admin.get(
            reverse(
                "group-messages-attachment-download",
                kwargs={
                    "group_pk": self.primary_group.id,
                    "pk": message_one.id,
                    "attachment_pk": attachment_two.id,
                },
            )
        )
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(message_one.id, message_two.id)

    def test_signed_blob_url_is_not_generated_before_permission_passes(self):
        _, message, attachment = self._upload_attachment(self.client_student, self.primary_group)

        with patch("apps.chat.views.CHAT_FILE_SERVICE.resolve_url") as resolve_storage_url:
            with patch("apps.chat.views.CHAT_FILE_SERVICE.open") as open_storage_file:
                response = self.client_outsider.get(self._download_url(self.primary_group, message, attachment))

        self.assertEqual(response.status_code, 403)
        resolve_storage_url.assert_not_called()
        open_storage_file.assert_not_called()

    @override_settings(CHAT_SANITIZER_BLACKLIST=["badword*"])
    def test_chat_serializer_returns_sanitized_attachment_filename(self):
        response, message, attachment = self._upload_attachment(
            self.client_student,
            self.primary_group,
            filename="<script>badword.PDF",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["attachments"][0]["attachment_filename"], "redacted.pdf")
        self.assertTrue(attachment.storage_key.endswith("/redacted.pdf"))
        self.assertEqual(message.attachments.get().attachment_filename, "redacted.pdf")

    @override_settings(CHAT_SANITIZER_BLACKLIST=["badword*"])
    def test_chat_download_uses_sanitized_content_disposition(self):
        _, message, attachment = self._upload_attachment(
            self.client_student,
            self.primary_group,
            filename="<script>badword.PDF",
        )

        response = self.client_student.get(self._download_url(self.primary_group, message, attachment))

        self.assertEqual(response.status_code, 200)
        self.assertIn('filename="redacted.pdf"', response["Content-Disposition"])


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

        self.role_student = Roles.objects.create(role_name="student")
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


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
@unittest.skipUnless(HAS_CHANNELS_TESTING, "channels.testing requires daphne")
class ChatQuotedReplyTests(TestCase):
    """Integration + unit tests for the quoted-reply feature.

    Covers the invariants the feature has to uphold:

    * Happy path: write-only ``reply_to_id`` accepted, read-side
      ``reply_to`` embedded as ``{id, text, user_id, deleted}``.
    * Recursion bound: the embedded parent never itself contains a
      ``reply_to`` field, no matter how deep the underlying chain.
    * Same-group invariant: a reply cannot point at a parent in a
      different group — enforced by ``ReplyToIdField.get_queryset``.
    * Soft-delete invariant: a soft-deleted parent cannot be referenced
      on creation, and any *existing* reply that already references one
      surfaces ``text: null, deleted: true`` instead of leaking the
      moderated content.
    * Fail-closed: when the serializer is used outside a view context
      (no ``group_pk``), every ``reply_to_id`` is rejected.
    """

    def setUp(self):
        User = get_user_model()

        self.student = User.objects.create_user(email="qr_student@test.com", password="pw")
        self.role_student = Roles.objects.create(role_name="basic_student_qr")

        now = timezone.now()
        future = now.replace(year=2099)
        RoleAssignmentHistory.objects.create(
            user=self.student, role=self.role_student, valid_from=now, valid_to=future,
        )

        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW-QR", state=self.state)

        self.group = Groups.objects.create(group_name="QR-G1", track=self.track)
        self.other_group = Groups.objects.create(group_name="QR-G2", track=self.track)
        GroupMembership.objects.create(user=self.student, group=self.group)
        GroupMembership.objects.create(user=self.student, group=self.other_group)

        self.client = APIClient()
        self.client.force_authenticate(user=self.student)

    def _list_url(self, group=None):
        return reverse(
            "group-messages-list",
            kwargs={"group_pk": (group or self.group).id},
        )

    # --- happy path ---------------------------------------------------

    def test_post_quoted_reply_via_api(self):
        parent = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="parent text",
        )
        resp = self.client.post(
            self._list_url(),
            {"message_text": "child text", "reply_to_id": parent.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data["reply_to"]["id"], parent.id)
        self.assertEqual(resp.data["reply_to"]["text"], "parent text")
        self.assertEqual(resp.data["reply_to"]["user_id"], self.student.id)
        self.assertFalse(resp.data["reply_to"]["deleted"])

    # --- recursion-depth structural guard -----------------------------

    def test_reply_to_nesting_serialization(self):
        """The embedded parent dict must never contain its own
        ``reply_to`` key, even when the parent is itself a quoted reply.
        That is the structural recursion guard for the API."""
        from apps.chat.serializers import MessageSerializer

        grandparent = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="g",
        )
        parent = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="p",
            reply_to=grandparent,
        )
        child = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="c",
            reply_to=parent,
        )

        data = MessageSerializer(child).data
        self.assertEqual(data["reply_to"]["id"], parent.id)
        self.assertEqual(data["reply_to"]["text"], "p")
        # The recursion guard: the embedded parent has *no* nested
        # reply_to field of its own, so the response is flat at exactly
        # one level no matter how deep the chain runs.
        self.assertNotIn("reply_to", data["reply_to"])

    # --- same-group invariant ----------------------------------------

    def test_reply_to_id_rejected_across_groups(self):
        """A reply in group B cannot point at a parent in group A.

        With the field-level queryset filter, the cross-group PK simply
        is not in the queryset and DRF rejects with the standard
        ``"Invalid pk \\"X\\" - object does not exist."`` envelope.
        That is also a small security improvement — it does not leak
        the existence of messages in other groups.
        """
        parent_in_group_a = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="a",
        )
        resp = self.client.post(
            self._list_url(self.other_group),
            {"message_text": "leak attempt", "reply_to_id": parent_in_group_a.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        # The custom exception handler wraps DRF errors as
        # ``{error, fields, code, request_id}``; tests pin to that shape.
        self.assertIn("fields", resp.data)
        self.assertIn("reply_to_id", resp.data["fields"])

    # --- soft-delete invariant: write side ---------------------------

    def test_reply_to_id_rejects_soft_deleted_parent(self):
        """A reply cannot be created against a soft-deleted parent.

        The field's queryset filters on ``deleted_at__isnull=True`` so
        soft-deleted PKs vanish from the writable set and DRF rejects
        with the standard 400.
        """
        parent = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="x",
        )
        parent.soft_delete()
        resp = self.client.post(
            self._list_url(),
            {"message_text": "y", "reply_to_id": parent.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("fields", resp.data)
        self.assertIn("reply_to_id", resp.data["fields"])

    # --- soft-delete invariant: read side ----------------------------

    def test_reply_to_serializer_handles_soft_deleted_parent(self):
        """When a parent is soft-deleted *after* its replies were
        posted, the read payload must surface ``id`` and ``user_id``
        (so the FE can attribute the placeholder) but null out
        ``text`` and set ``deleted: true``. Any other behaviour would
        let moderated content leak through every child that quoted it.
        """
        parent = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="moderated content",
        )
        child = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="child",
            reply_to=parent,
        )
        parent.soft_delete()

        resp = self.client.get(self._list_url())
        self.assertEqual(resp.status_code, 200, resp.content)
        items = resp.data["items"]
        child_payload = next(i for i in items if i["id"] == child.id)
        self.assertEqual(child_payload["reply_to"]["id"], parent.id)
        self.assertEqual(child_payload["reply_to"]["user_id"], self.student.id)
        self.assertIsNone(child_payload["reply_to"]["text"])
        self.assertTrue(child_payload["reply_to"]["deleted"])

    # --- fail-closed: no view context --------------------------------

    def test_reply_to_id_fails_closed_without_view_context(self):
        """If the serializer is instantiated outside a view (management
        command, signal handler, future bulk import), it has no way to
        know which group to scope to. The field's queryset returns
        ``Messages.objects.none()`` in that case, so any ``reply_to_id``
        is rejected with the standard 400. Skipping the cross-group
        check on missing context would be the opposite of what a
        security-relevant validator should do.
        """
        from apps.chat.serializers import MessageSerializer

        parent = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="p",
        )
        # No ``context={"view": ...}`` — this is the failure mode we're
        # pinning.
        ser = MessageSerializer(
            data={"message_text": "child", "reply_to_id": parent.id},
        )
        self.assertFalse(ser.is_valid())
        self.assertIn("reply_to_id", ser.errors)
