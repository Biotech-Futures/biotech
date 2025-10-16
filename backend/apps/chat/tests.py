import contextlib
from django.test import TestCase, override_settings
from django.test import Client
import asyncio
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import connection, models
from django.conf import settings

from rest_framework.test import APIClient
from channels.testing import WebsocketCommunicator
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from config.asgi import application  # ASGI entrypoint (Channels)
from apps.chat.models import Messages
from apps.resources.models import Roles, RoleAssignmentHistory, Resources
from apps.groups.models import Groups, GroupMembers, Countries, CountryStates, Tracks


# Create your tests here.

# Use in-memory channel layer for tests
CHANNEL_TEST_SETTINGS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


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
        self.track = Tracks.objects.create(track_name="Biotech Research", state=self.state)

        # --- groups & membership ---
        self.group = Groups.objects.create(group_name="G1", track=self.track)
        GroupMembers.objects.create(user=self.student, group=self.group)
        GroupMembers.objects.create(user=self.mentor, group=self.group)
        GroupMembers.objects.create(user=self.supervisor, group=self.group)
        # admin has global access; they don't need membership
        
        # --- resources ---
        self.res1 = Resources.objects.create(
            resource_name="R1", resource_description="d1", uploader_user_id=self.admin
        )
        self.res2 = Resources.objects.create(
            resource_name="R2", resource_description="d2", uploader_user_id=self.admin
        )

        # API clients
        self.client_student = APIClient(); self.client_student.force_authenticate(user=self.student)
        self.client_mentor = APIClient(); self.client_mentor.force_authenticate(user=self.mentor)
        self.client_supervisor = APIClient(); self.client_supervisor.force_authenticate(user=self.supervisor)
        self.client_admin = APIClient(); self.client_admin.force_authenticate(user=self.admin)


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
        self.assertFalse(msg.deleted_flag)
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
        self.assertTrue(msg.deleted_flag)

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
        self.assertTrue(msg2.deleted_flag)

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
        self.assertTrue(msg3.deleted_flag)

    def test_soft_deleted_messages_are_excluded_from_list(self):
        m1 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="keep")
        m2 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="hide", deleted_flag=True)

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

    def test_ws_broadcast_on_create(self):
        # Open WS as student (group member)
        comm = self._ws_connect_with_session(self.student)

        api = APIClient()
        api.force_authenticate(self.student)
        
        try:
            # Create a message via REST (as student)
            resp = api.post(
                f"/chat/groups/{self.group.id}/messages/",
                {"message_text": "hi from test", "resources": []},
                format="json",
            )
            self.assertEqual(resp.status_code, 201, resp.content)

            async_to_sync(asyncio.sleep)(0.05)

            # Expect a broadcast
            event = async_to_sync(comm.receive_json_from)(timeout=5)
            self.assertEqual(event["payload"]["event"], "message.created")
            self.assertEqual(event["payload"]["group_id"], self.group.id)
            self.assertEqual(event["payload"]["message"]["text"], "hi from test")
            self.assertEqual(event["payload"]["message"]["sender_id"], self.student.id)
        finally:
            # Prevent CancelledError bubbling if a prior await timed out/cancelled
            with contextlib.suppress(Exception, asyncio.CancelledError):
                async_to_sync(asyncio.sleep)(0.05)
                async_to_sync(comm.disconnect)()


    def test_ws_broadcast_on_delete(self):
        # create a message to delete
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="to remove")

        # Open WS as mentor (has moderation in this group)
        comm = self._ws_connect_with_session(self.mentor)

        api = APIClient()
        api.force_authenticate(self.mentor)

        try:
            # Delete via REST (mentor)
            resp = api.delete(f"/chat/groups/{self.group.id}/messages/{msg.id}/")
            self.assertEqual(resp.status_code, 204, resp.content)

            async_to_sync(asyncio.sleep)(0.05)

            # Expect broadcast
            event = async_to_sync(comm.receive_json_from)(timeout=5)
            self.assertEqual(event["payload"]["event"], "message.deleted")
            self.assertEqual(event["payload"]["group_id"], self.group.id)
            self.assertEqual(event["payload"]["message_id"], msg.id)
        finally:
            with contextlib.suppress(Exception, asyncio.CancelledError):
                async_to_sync(asyncio.sleep)(0.05)
                async_to_sync(comm.disconnect)()