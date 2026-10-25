"""Admins send group messages as Administrator from the admin API (AM6).

POST /api/v1/admin/group/{id}/messages/ stores the admin as the real sender
with ``sent_as_admin`` set, through the same serializer and publish path as a
member's chat message, and audits it. The admin history labels these
messages while still naming the admin.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.chat.models import Messages
from apps.chat.models.message_mention import MessageMention
from apps.chat.models.message_resource import MessageResource
from apps.chat.serializers import ADMIN_IDENTITY_KEY
from apps.chat.utils import reset_pattern_cache
from apps.admin.services.group import query_group_messages, send_group_message
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import Resources
from apps.users.models import AdminScope, MentorProfile

CHANNEL_TEST_SETTINGS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class AdminGroupMessageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="ada.admin@test.com", password="pw", first_name="Ada", last_name="Quietly",
        )
        AdminScope.objects.create(user=self.admin)
        self.student = User.objects.create_user(
            email="student@test.com", password="pw", first_name="Sam", last_name="Student",
        )
        self.mentor = User.objects.create_user(
            email="mentor@test.com", password="pw", first_name="Mia", last_name="Mentor",
        )
        MentorProfile.objects.create(user=self.mentor, institution="Uni", mentor_reason="Help")
        self.supervisor = User.objects.create_user(email="supervisor@test.com", password="pw")
        self.outsider = User.objects.create_user(email="outsider@test.com", password="pw")

        self.group = Groups.objects.create(group_name="G1")
        GroupMembership.objects.create(user=self.student, group=self.group, membership_role="student")
        GroupMembership.objects.create(user=self.mentor, group=self.group, membership_role="mentor")
        GroupMembership.objects.create(user=self.supervisor, group=self.group, membership_role="supervisor")

        self.url = f"/api/v1/admin/group/{self.group.id}/messages/"

    def client_for(self, user):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def send(self, payload, user=None, url=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client_for(user or self.admin).post(url or self.url, payload, format="json")

    def sent_messages(self):
        return Messages.objects.filter(group=self.group, sent_as_admin=True)

    # -- Permissions ---------------------------------------------------------

    def test_only_admins_can_send(self):
        for user in (self.student, self.mentor, self.supervisor, self.outsider, None):
            with self.subTest(user=getattr(user, "email", "anonymous")):
                response = self.client_for(user).post(self.url, {"text": "hi"}, format="json")
                self.assertIn(response.status_code, (401, 403))
        self.assertFalse(Messages.objects.exists())
        self.assertFalse(AuditLog.objects.filter(entity_type="message").exists())

    # -- Validation ----------------------------------------------------------

    def test_rejects_missing_empty_or_non_text_messages(self):
        for payload in ({}, {"text": ""}, {"text": "   \n\t "}, {"text": None}, {"text": 42}, {"text": ["hi"]}):
            with self.subTest(payload=payload):
                response = self.send(payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["msg"], "Message cannot be empty")
        self.assertFalse(Messages.objects.exists())
        self.assertFalse(AuditLog.objects.filter(entity_type="message").exists())

    def test_missing_deleted_or_malformed_groups_are_not_found(self):
        deleted = Groups.objects.create(group_name="Gone")
        Groups.objects.filter(pk=deleted.pk).update(deleted_at=timezone.now())
        for url in (
            "/api/v1/admin/group/999999/messages/",
            f"/api/v1/admin/group/{deleted.id}/messages/",
            "/api/v1/admin/group/abc/messages/",
        ):
            with self.subTest(url=url):
                response = self.send({"text": "hi"}, url=url)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.data["msg"], "Group not found")
        self.assertFalse(Messages.objects.exists())

    # -- Persistence ---------------------------------------------------------

    def test_stores_the_admin_as_sender_with_the_flag(self):
        response = self.send({"text": "Reminder: posters are due Friday."})

        self.assertEqual(response.status_code, 201, response.data)
        message = self.sent_messages().get()
        self.assertEqual(message.sender_user, self.admin)
        self.assertTrue(message.sent_as_admin)
        self.assertEqual(message.message_type, "text")
        self.assertEqual(message.message_text, "Reminder: posters are due Friday.")
        # Admins get the real sender back, labelled as an admin message.
        self.assertEqual(response.data["data"]["id"], str(message.id))
        self.assertTrue(response.data["data"]["sent_as_admin"])
        self.assertEqual(response.data["data"]["sender"], {
            "id": str(self.admin.id), "name": "Ada Quietly", "email": "ada.admin@test.com", "role": "admin",
        })

    def test_text_only_extra_fields_are_ignored(self):
        resource = Resources.objects.create(name="R", description="d", uploaded_by=self.admin, group=self.group)
        response = self.send({"text": "See this", "resources": [{"resource": resource.id}], "sent_as_admin": False})
        self.assertEqual(response.status_code, 201, response.data)
        message = self.sent_messages().get()
        self.assertTrue(message.sent_as_admin)
        self.assertFalse(MessageResource.objects.filter(message=message).exists())

    def test_members_then_see_it_from_administrator(self):
        self.send({"text": "Hello team"})
        member_view = self.client_for(self.student).get(f"/chat/groups/{self.group.id}/messages/")
        [item] = member_view.data["items"]
        self.assertEqual(item["sender_name"], "Administrator")
        self.assertNotIn("Quietly", str(member_view.data))

    # -- Sanitisation --------------------------------------------------------

    @override_settings(CHAT_SANITIZER_BLACKLIST=["badword*"], CHAT_SANITIZER_REPLACEMENT="***")
    def test_blocked_text_is_refused_like_a_member_message(self):
        # Posting as Administrator is held to the group's own rules: blocked
        # words are refused outright rather than written and masked, and the
        # admin path answers exactly as the member path does.
        reset_pattern_cache()
        self.addCleanup(reset_pattern_cache)
        text = "this is badwording stuff"

        admin = self.send({"text": text})
        with self.captureOnCommitCallbacks(execute=True):
            member = self.client_for(self.student).post(
                f"/chat/groups/{self.group.id}/messages/", {"message_text": text}, format="json",
            )

        self.assertEqual(admin.status_code, 400, admin.data)
        self.assertEqual(member.status_code, 400, member.data)
        # Neither was stored.
        self.assertFalse(self.sent_messages().exists())
        self.assertFalse(Messages.objects.filter(message_text__icontains="badword").exists())

    # -- Mentions, broadcast and link previews -------------------------------

    @patch("apps.chat.views.get_channel_layer")
    def test_broadcast_and_mention_push_are_masked(self, get_layer):
        layer = MagicMock()
        layer.group_send = AsyncMock()
        get_layer.return_value = layer

        response = self.send({"text": f"<@{self.student.id}> <@{self.outsider.id}> please check in"})
        self.assertEqual(response.status_code, 201, response.data)
        message = self.sent_messages().get()

        # Only group members can be mentioned.
        self.assertEqual(
            list(MessageMention.objects.filter(message=message).values_list("mentioned_user_id", flat=True)),
            [self.student.id],
        )
        sends = {channel: envelope["payload"] for channel, envelope in
                 (call.args for call in layer.group_send.call_args_list)}
        self.assertEqual(set(sends), {f"group_{self.group.id}", f"user_{self.student.id}"})

        created = sends[f"group_{self.group.id}"]
        self.assertEqual(created["event"], "message.created")
        self.assertEqual((created["message"]["sender_name"], created["message"]["sender_user"]), ("Administrator", None))
        self.assertTrue(created["message"]["sent_as_admin"])
        self.assertEqual(created[ADMIN_IDENTITY_KEY]["message"]["sender_user"], self.admin.id)

        mention = sends[f"user_{self.student.id}"]
        self.assertEqual((mention["sender_name"], mention["sender_user_id"]), ("Administrator", None))

    @patch("apps.chat.views.dispatch_og")
    def test_link_previews_are_dispatched_after_commit(self, dispatch_og):
        self.send({"text": "Agenda: https://example.com/agenda"})
        message = self.sent_messages().get()
        dispatch_og.assert_called_once_with(message.id, "https://example.com/agenda")

    # -- Audit ---------------------------------------------------------------

    def test_each_send_is_audited(self):
        self.send({"text": "First"})
        self.send({"text": "Second"})

        audits = AuditLog.objects.filter(entity_type="message", action="create").order_by("id")
        self.assertEqual(audits.count(), 2)
        message = self.sent_messages().order_by("id").last()
        audit = audits.last()
        self.assertEqual(audit.actor_user, self.admin)
        self.assertEqual(audit.entity_id, message.id)
        self.assertEqual(audit.after_state["senderUserId"], self.admin.id)
        self.assertEqual(audit.after_state["groupId"], self.group.id)
        self.assertTrue(audit.after_state["sentAsAdmin"])
        self.assertEqual(audit.after_state["messageText"], "Second")

    @patch("apps.chat.views.get_channel_layer")
    def test_a_failed_audit_rolls_back_the_message_and_its_broadcast(self, get_layer):
        layer = MagicMock()
        layer.group_send = AsyncMock()
        get_layer.return_value = layer

        with patch("apps.admin.services.group.log_audit_event", side_effect=RuntimeError("audit down")):
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(RuntimeError):
                    send_group_message(str(self.group.id), "hi", initiated_by=self.admin)

        self.assertFalse(Messages.objects.exists())
        layer.group_send.assert_not_called()

    # -- History -------------------------------------------------------------

    def test_history_labels_admin_messages_and_keeps_the_real_sender(self):
        Messages.objects.create(group=self.group, sender_user=self.mentor, message_text="Hi all")
        self.send({"text": "From the team"})

        response = self.client_for(self.admin).get(self.url)
        self.assertEqual(response.status_code, 200)
        mentor_item, admin_item = response.data["data"]["items"]
        self.assertFalse(mentor_item["sent_as_admin"])
        self.assertEqual(mentor_item["sender"]["role"], "mentor")
        self.assertTrue(admin_item["sent_as_admin"])
        self.assertEqual(admin_item["sender"]["role"], "admin")
        self.assertEqual(admin_item["sender"]["name"], "Ada Quietly")

    def test_admin_posting_in_group_chat_is_not_labelled(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.admin).post(
                f"/chat/groups/{self.group.id}/messages/", {"message_text": "as myself"}, format="json",
            )
        [item] = query_group_messages(str(self.group.id))["data"]["items"]
        self.assertFalse(item["sent_as_admin"])
        self.assertIsNone(item["sender"]["role"])
