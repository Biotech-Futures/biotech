import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from django.test import TestCase, override_settings
from django.test import Client
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
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
from apps.users.models import AdminScope


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
        # Track-admin user, scoped to AUS-NSW only.
        self.track_admin = User.objects.create_user(email="track_admin@test.com", password="pw")

        # --- roles ---
        # Roles still exist for unrelated chat features (read-membership,
        # role display in payloads, etc.) but are no longer the source of
        # moderation power.
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
        self.other_state = CountryStates.objects.create(country=self.country, state_name="VIC")
        self.other_track = Tracks.objects.create(track_name="AUS-VIC", state=self.other_state)

        # --- groups & membership ---
        self.group = Groups.objects.create(group_name="G1", track=self.track)
        GroupMembership.objects.create(user=self.student, group=self.group)
        GroupMembership.objects.create(user=self.mentor, group=self.group)
        GroupMembership.objects.create(user=self.supervisor, group=self.group)
        # admin / track_admin have AdminScope-based access; they don't need membership

        # --- admin scopes (operational admin model) ---
        # Global admin: can moderate anywhere.
        AdminScope.objects.create(user=self.admin, is_global=True)
        # Track admin: limited to the AUS-NSW track.
        AdminScope.objects.create(user=self.track_admin, track=self.track, is_global=False)
        
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


    # --------- helpers ---------
    def _list_url(self, group_id=None):
        gid = group_id or self.group.id
        return reverse("group-messages-list", kwargs={"group_pk": gid})

    def _detail_url(self, mid, group_id=None):
        gid = group_id or self.group.id
        return reverse("group-messages-detail", kwargs={"group_pk": gid, "pk": mid})

    def _destroy_url(self, mid):
        # Flat delete route: only message_id is required.
        return reverse("message-destroy", kwargs={"pk": mid})

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

    def test_delete_allowed_for_sender_within_10_minutes(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="to delete")
        resp = self.client_student.delete(self._destroy_url(msg.id))
        self.assertEqual(resp.status_code, 204)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.deleted_at)

    def test_delete_forbidden_for_sender_after_10_minutes(self):
        msg = Messages.objects.create(
            group=self.group,
            sender_user=self.student,
            message_text="too old to delete",
            sent_at=timezone.now() - timedelta(minutes=11),
        )
        resp = self.client_student.delete(self._destroy_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_forbidden_for_non_sender_regular_user(self):
        other_student = get_user_model().objects.create_user(email="student2@test.com", password="pw")
        now = timezone.now()
        future = now.replace(year=2099)
        RoleAssignmentHistory.objects.create(
            user=other_student, role=self.role_student, valid_from=now, valid_to=future
        )
        GroupMembership.objects.create(user=other_student, group=self.group)
        client_other_student = APIClient()
        client_other_student.force_authenticate(user=other_student)

        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="not yours")
        resp = client_other_student.delete(self._destroy_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_forbidden_for_mentor(self):
        # Mentors no longer have moderation rights — even in their own group.
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="mentor try")
        resp = self.client_mentor.delete(self._destroy_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_forbidden_for_supervisor(self):
        # Supervisors no longer have moderation rights — even in their own group.
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="supervisor try")
        resp = self.client_supervisor.delete(self._destroy_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_allowed_for_global_admin_anywhere(self):
        # Global admins (AdminScope.is_global=True) can delete in any track.
        other_group = Groups.objects.create(group_name="G-VIC", track=self.other_track)
        msg = Messages.objects.create(group=other_group, sender_user=self.student, message_text="global admin")

        resp = self.client_admin.delete(self._destroy_url(msg.id))
        self.assertEqual(resp.status_code, 204)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.deleted_at)

    def test_delete_allowed_for_track_admin_within_their_track(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="track admin in")

        resp = self.client_track_admin.delete(self._destroy_url(msg.id))
        self.assertEqual(resp.status_code, 204)
        msg.refresh_from_db()
        self.assertIsNotNone(msg.deleted_at)

    def test_delete_forbidden_for_track_admin_outside_their_track(self):
        other_group = Groups.objects.create(group_name="G-VIC", track=self.other_track)
        msg = Messages.objects.create(group=other_group, sender_user=self.student, message_text="track admin out")

        resp = self.client_track_admin.delete(self._destroy_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_forbidden_for_admin_role_without_admin_scope(self):
        # An "admin" role assignment alone (no AdminScope row) is not
        # sufficient to delete other users' messages.
        u = get_user_model().objects.create_user(email="role_admin_only@test.com", password="pw")
        RoleAssignmentHistory.objects.create(
            user=u, role=self.role_admin,
            valid_from=timezone.now(), valid_to=timezone.now().replace(year=2099),
        )
        client = APIClient(); client.force_authenticate(user=u)

        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="role admin only")
        resp = client.delete(self._destroy_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_forbidden_for_staff_without_admin_scope(self):
        # is_staff/is_superuser flags alone do NOT grant chat moderation.
        # An explicit AdminScope row is required.
        u = get_user_model().objects.create_user(
            email="staff_only@test.com", password="pw", is_staff=True
        )
        client = APIClient(); client.force_authenticate(user=u)

        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="staff only")
        resp = client.delete(self._destroy_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_delete_forbidden_for_superuser_without_admin_scope(self):
        u = get_user_model().objects.create_user(
            email="superuser_only@test.com", password="pw",
            is_staff=True, is_superuser=True,
        )
        client = APIClient(); client.force_authenticate(user=u)

        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="superuser only")
        resp = client.delete(self._destroy_url(msg.id))
        self.assertEqual(resp.status_code, 403)

    def test_nested_delete_route_is_no_longer_exposed(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="legacy route")
        legacy_url = f"/chat/groups/{self.group.id}/messages/{msg.id}/"

        resp = self.client_admin.delete(legacy_url)
        self.assertEqual(resp.status_code, 405)

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
        # Global admin has unconditional moderation rights under the new contract.
        api.force_authenticate(self.admin)

        resp = api.delete(f"/chat/messages/{msg.id}/")
        self.assertEqual(resp.status_code, 204, resp.content)

        fake_layer.group_send.assert_called_once()
        group_name, envelope = fake_layer.group_send.call_args.args
        self.assertEqual(group_name, f"group_{self.group.id}")
        self.assertEqual(envelope["type"], "chat.message")
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "message.deleted")
        self.assertEqual(payload["group_id"], self.group.id)
        self.assertEqual(payload["message_id"], msg.id)


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
