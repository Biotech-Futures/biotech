"""Messages sent through the admin interface show as "Administrator" (AM6).

A message with ``sent_as_admin`` names its real sender only to admins. Everyone
else gets ``sender_name: "Administrator"`` and no sender id, on every path that
carries a sender: REST lists and detail, quoted replies, the mentions inbox,
WebSocket frames, and mention pushes. Ordinary messages, including ones an
admin posts through the normal group chat, are unchanged.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.chat.management.consumers import GroupChatConsumer
from apps.chat.models import Messages
from apps.chat.models.message_mention import MessageMention
from apps.chat.serializers import (
    ADMIN_IDENTITY_KEY,
    MessagePublicSerializer,
    MessageSerializer,
    ReplyToSerializer,
)
from apps.chat.views import apply_mentions
from apps.common.storage import get_chat_storage
from apps.groups.models import GroupMembership, Groups
from apps.users.models import AdminScope
from tests.apps._helpers import StorageCleanupMixin

CHANNEL_TEST_SETTINGS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

#: Every payload field that carries a user id.
USER_ID_FIELDS = {"sender_user", "sender_user_id", "user_id", "deleted_by"}


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class AdminSenderTestBase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.student = User.objects.create_user(
            email="student@test.com", password="pw", first_name="Sam", last_name="Student",
        )
        self.mentor = User.objects.create_user(
            email="mentor@test.com", password="pw", first_name="Mia", last_name="Mentor",
        )
        self.supervisor = User.objects.create_user(
            email="supervisor@test.com", password="pw", first_name="Sue", last_name="Supervisor",
        )
        self.admin = User.objects.create_user(
            email="ada.admin@test.com", password="pw", first_name="Ada", last_name="Quietly",
        )
        self.other_admin = User.objects.create_user(
            email="other.admin@test.com", password="pw", first_name="Otto", last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin)
        AdminScope.objects.create(user=self.other_admin)

        self.group = Groups.objects.create(group_name="G1")
        for user, role in (
            (self.student, "student"),
            (self.mentor, "mentor"),
            (self.supervisor, "supervisor"),
        ):
            GroupMembership.objects.create(user=user, group=self.group, membership_role=role)

        self.admin_message = Messages.objects.create(
            group=self.group, sender_user=self.admin, message_text="From the team", sent_as_admin=True,
        )
        self.mentor_message = Messages.objects.create(
            group=self.group, sender_user=self.mentor, message_text="Hi all",
        )

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def assert_no_real_identity(self, data):
        """The admin's name, email and id appear nowhere in ``data``."""
        text = json.dumps(data, default=str)
        self.assertNotIn("Ada", text)
        self.assertNotIn("Quietly", text)
        self.assertNotIn("ada.admin@test.com", text)
        self.assertNotIn(ADMIN_IDENTITY_KEY, text)

    def assert_admin_id_absent(self, data):
        """No user-id field anywhere in ``data`` holds the sending admin's id."""
        found = []

        def walk(value, path):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in USER_ID_FIELDS and item == self.admin.id:
                        found.append(f"{path}.{key}")
                    walk(item, f"{path}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{path}[{index}]")

        walk(data, "")
        self.assertEqual(found, [], "admin id exposed")

    def by_id(self, items, message):
        return next(item for item in items if item["id"] == message.id)


class RestMaskingTests(AdminSenderTestBase):
    def list_items(self, user):
        response = self.client_for(user).get(f"/chat/groups/{self.group.id}/messages/")
        self.assertEqual(response.status_code, 200, response.content)
        return response.data["items"]

    def test_members_see_administrator_and_nothing_identifying(self):
        for viewer in (self.student, self.mentor, self.supervisor):
            with self.subTest(viewer=viewer.email):
                items = self.list_items(viewer)
                item = self.by_id(items, self.admin_message)
                self.assertEqual(item["sender_name"], "Administrator")
                self.assertTrue(item["sent_as_admin"])
                self.assert_no_real_identity(items)

    def test_admins_see_the_real_sender(self):
        for viewer in (self.other_admin, self.admin):
            with self.subTest(viewer=viewer.email):
                item = self.by_id(self.list_items(viewer), self.admin_message)
                self.assertEqual(item["sender_name"], "Ada Quietly")
                self.assertTrue(item["sent_as_admin"])

    def test_detail_view_is_masked_for_members(self):
        url = f"/chat/groups/{self.group.id}/messages/{self.admin_message.id}/"
        member = self.client_for(self.student).get(url)
        self.assertEqual(member.status_code, 200, member.content)
        self.assertEqual(member.data["sender_name"], "Administrator")
        self.assert_no_real_identity(member.data)
        admin = self.client_for(self.other_admin).get(url)
        self.assertEqual(admin.data["sender_name"], "Ada Quietly")

    def test_other_messages_are_unchanged_for_every_viewer(self):
        for viewer in (self.student, self.mentor, self.supervisor, self.other_admin):
            with self.subTest(viewer=viewer.email):
                item = self.by_id(self.list_items(viewer), self.mentor_message)
                self.assertEqual(item["sender_name"], "Mia Mentor")
                self.assertFalse(item["sent_as_admin"])

    def test_quoted_reply_hides_the_admin_from_members(self):
        reply = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="Thanks!", reply_to=self.admin_message,
        )
        member_item = self.by_id(self.list_items(self.mentor), reply)
        self.assertEqual(member_item["reply_to"]["user_name"], "Administrator")
        self.assertIsNone(member_item["reply_to"]["user_id"])
        self.assertEqual(member_item["sender_name"], "Sam Student")

        admin_item = self.by_id(self.list_items(self.other_admin), reply)
        self.assertEqual(admin_item["reply_to"]["user_name"], "Ada Quietly")
        self.assertEqual(admin_item["reply_to"]["user_id"], self.admin.id)

    def test_mentions_inbox_hides_the_admin_from_members(self):
        MessageMention.objects.create(message=self.admin_message, mentioned_user=self.student)
        MessageMention.objects.create(message=self.admin_message, mentioned_user=self.other_admin)

        member = self.client_for(self.student).get("/chat/mentions/")
        self.assertEqual(member.status_code, 200, member.content)
        [row] = member.data["items"]
        self.assertEqual(row["sender_name"], "Administrator")
        self.assertIsNone(row["sender_user_id"])
        self.assert_no_real_identity(member.data)

        admin = self.client_for(self.other_admin).get("/chat/mentions/")
        [row] = admin.data["items"]
        self.assertEqual((row["sender_name"], row["sender_user_id"]), ("Ada Quietly", self.admin.id))

    def test_mark_read_response_is_masked_too(self):
        mention = MessageMention.objects.create(message=self.admin_message, mentioned_user=self.student)
        response = self.client_for(self.student).post(f"/chat/mentions/{mention.id}/read/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["sender_name"], "Administrator")
        self.assertIsNone(response.data["sender_user_id"])

    def test_serializers_fail_closed_without_a_request(self):
        full = MessageSerializer(self.admin_message).data
        self.assertEqual((full["sender_name"], full["sender_user"]), ("Administrator", None))
        self.assertEqual(MessagePublicSerializer(self.admin_message).data["sender_name"], "Administrator")
        quote = ReplyToSerializer(self.admin_message).data
        self.assertEqual((quote["user_name"], quote["user_id"]), ("Administrator", None))


class ChatInputCannotClaimAdminTests(AdminSenderTestBase):
    def post(self, user, payload):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client_for(user).post(
                f"/chat/groups/{self.group.id}/messages/", payload, format="json",
            )

    def test_member_cannot_set_sent_as_admin(self):
        response = self.post(self.student, {"message_text": "sneaky", "sent_as_admin": True})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertFalse(Messages.objects.get(pk=response.data["id"]).sent_as_admin)
        self.assertEqual(response.data["sender_name"], "Sam Student")

    def test_admin_posting_in_group_chat_stays_themselves(self):
        # Only the admin interface sends as Administrator (decision 1).
        response = self.post(self.admin, {"message_text": "hello", "sent_as_admin": True})
        self.assertEqual(response.status_code, 201, response.content)
        message = Messages.objects.get(pk=response.data["id"])
        self.assertFalse(message.sent_as_admin)
        item = self.by_id(
            self.client_for(self.student).get(f"/chat/groups/{self.group.id}/messages/").data["items"],
            message,
        )
        self.assertEqual(item["sender_name"], "Ada Quietly")


@patch("apps.chat.views.get_channel_layer")
class BroadcastTests(AdminSenderTestBase):
    def sent(self, layer):
        return [call.args for call in layer.group_send.call_args_list]

    def fake_layer(self, get_layer):
        layer = MagicMock()
        layer.group_send = AsyncMock()
        get_layer.return_value = layer
        return layer

    def test_admin_message_broadcast_is_masked_with_identity_kept_server_side(self, get_layer):
        layer = self.fake_layer(get_layer)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client_for(self.admin).patch(
                f"/chat/groups/{self.group.id}/messages/{self.admin_message.id}/",
                {"message_text": "From the team (edited)"},
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.content)

        [(group_name, envelope)] = self.sent(layer)
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "message.edited")
        message = payload["message"]
        self.assertEqual((message["sender_name"], message["sender_user"]), ("Administrator", None))
        self.assert_no_real_identity(message)
        self.assertEqual(
            payload[ADMIN_IDENTITY_KEY],
            {"message": {"sender_user": self.admin.id, "sender_name": "Ada Quietly"}},
        )

    def test_reply_broadcast_masks_the_quoted_admin(self, get_layer):
        layer = self.fake_layer(get_layer)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client_for(self.student).post(
                f"/chat/groups/{self.group.id}/messages/",
                {"message_text": "Got it", "reply_to_id": self.admin_message.id},
                format="json",
            )
        self.assertEqual(response.status_code, 201, response.content)

        [(_, envelope)] = self.sent(layer)
        message = envelope["payload"]["message"]
        self.assertEqual(message["sender_name"], "Sam Student")
        self.assertEqual(message["sender_user"], self.student.id)
        self.assertEqual((message["reply_to"]["user_name"], message["reply_to"]["user_id"]), ("Administrator", None))
        self.assertEqual(
            envelope["payload"][ADMIN_IDENTITY_KEY],
            {"reply_to": {"user_id": self.admin.id, "user_name": "Ada Quietly"}},
        )

    def test_ordinary_broadcast_carries_no_identity_key(self, get_layer):
        layer = self.fake_layer(get_layer)
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.mentor).post(
                f"/chat/groups/{self.group.id}/messages/", {"message_text": "plain"}, format="json",
            )
        [(_, envelope)] = self.sent(layer)
        self.assertNotIn(ADMIN_IDENTITY_KEY, envelope["payload"])
        self.assertEqual(envelope["payload"]["message"]["sender_user"], self.mentor.id)
        self.assertEqual(envelope["payload"]["message"]["sender_name"], "Mia Mentor")

    def test_mention_push_from_admin_message_is_masked(self, get_layer):
        layer = self.fake_layer(get_layer)
        message = Messages.objects.create(
            group=self.group, sender_user=self.admin, message_text=f"<@{self.student.id}> please check",
            sent_as_admin=True,
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(apply_mentions(message), [self.student.id])

        [(channel, envelope)] = self.sent(layer)
        self.assertEqual(channel, f"user_{self.student.id}")
        payload = envelope["payload"]
        self.assertEqual((payload["sender_name"], payload["sender_user_id"]), ("Administrator", None))
        self.assertEqual(
            payload[ADMIN_IDENTITY_KEY],
            {"payload": {"sender_user_id": self.admin.id, "sender_name": "Ada Quietly"}},
        )

    def test_mention_push_from_member_is_unchanged(self, get_layer):
        layer = self.fake_layer(get_layer)
        message = Messages.objects.create(
            group=self.group, sender_user=self.mentor, message_text=f"<@{self.student.id}> hi",
        )
        with self.captureOnCommitCallbacks(execute=True):
            apply_mentions(message)
        [(_, envelope)] = self.sent(layer)
        self.assertEqual(envelope["payload"]["sender_user_id"], self.mentor.id)
        self.assertNotIn("sender_name", envelope["payload"])
        self.assertNotIn(ADMIN_IDENTITY_KEY, envelope["payload"])


class ConsumerTests(AdminSenderTestBase):
    """GroupChatConsumer.chat_message, driven directly as in test_typing.py."""

    def consumer_for(self, user):
        consumer = GroupChatConsumer()
        consumer.scope = {"user": user}
        consumer.group_id = self.group.id
        consumer.send_json = AsyncMock()
        consumer._mark_one_delivered = AsyncMock()
        return consumer

    def admin_frame(self, event="message.created"):
        return {
            "type": "chat.message",
            "payload": {
                "event": event,
                "type": event,
                "group_id": self.group.id,
                "message_id": self.admin_message.id,
                "message": {
                    "id": self.admin_message.id,
                    "sender_user": None,
                    "sender_name": "Administrator",
                    "sent_as_admin": True,
                    "message_text": "From the team",
                    "reply_to": None,
                },
                ADMIN_IDENTITY_KEY: {
                    "message": {"sender_user": self.admin.id, "sender_name": "Ada Quietly"},
                },
            },
        }

    def deliver(self, consumer, frame):
        async_to_sync(consumer.chat_message)(frame)
        consumer.send_json.assert_awaited_once()
        return consumer.send_json.await_args.args[0]

    def test_member_socket_gets_the_masked_frame_without_the_private_key(self):
        for viewer in (self.student, self.mentor, self.supervisor):
            with self.subTest(viewer=viewer.email):
                sent = self.deliver(self.consumer_for(viewer), self.admin_frame())
                self.assertEqual(sent["message"]["sender_name"], "Administrator")
                self.assertIsNone(sent["message"]["sender_user"])
                self.assert_no_real_identity(sent)

    def test_admin_socket_gets_the_real_sender_without_the_private_key(self):
        sent = self.deliver(self.consumer_for(self.other_admin), self.admin_frame())
        self.assertEqual(sent["message"]["sender_name"], "Ada Quietly")
        self.assertEqual(sent["message"]["sender_user"], self.admin.id)
        self.assertNotIn(ADMIN_IDENTITY_KEY, sent)

    def test_revoked_admin_stops_seeing_identities_on_the_next_frame(self):
        consumer = self.consumer_for(self.other_admin)
        self.assertEqual(self.deliver(consumer, self.admin_frame())["message"]["sender_name"], "Ada Quietly")

        AdminScope.objects.filter(user=self.other_admin).delete()
        consumer.send_json.reset_mock()
        sent = self.deliver(consumer, self.admin_frame("message.edited"))
        self.assertEqual(sent["message"]["sender_name"], "Administrator")
        self.assert_no_real_identity(sent)

    def test_an_error_checking_admin_status_masks(self):
        consumer = self.consumer_for(self.other_admin)
        with patch("apps.chat.management.consumers.is_admin", side_effect=RuntimeError("db down")):
            sent = self.deliver(consumer, self.admin_frame())
        self.assertEqual(sent["message"]["sender_name"], "Administrator")
        self.assert_no_real_identity(sent)

    def test_shared_frame_is_not_mutated_between_sockets(self):
        frame = self.admin_frame()
        self.deliver(self.consumer_for(self.other_admin), frame)
        sent = self.deliver(self.consumer_for(self.student), frame)
        self.assert_no_real_identity(sent)
        self.assertIn(ADMIN_IDENTITY_KEY, frame["payload"])

    def test_delivered_receipts_use_the_real_sender(self):
        member = self.consumer_for(self.student)
        self.deliver(member, self.admin_frame())
        member._mark_one_delivered.assert_awaited_once()

        sender = self.consumer_for(self.admin)
        self.deliver(sender, self.admin_frame())
        sender._mark_one_delivered.assert_not_awaited()

    def test_quoted_admin_in_a_reply_frame(self):
        frame = {
            "type": "chat.message",
            "payload": {
                "event": "message.created",
                "type": "message.created",
                "group_id": self.group.id,
                "message": {
                    "id": 999,
                    "sender_user": self.student.id,
                    "sender_name": "Sam Student",
                    "reply_to": {"id": self.admin_message.id, "user_id": None, "user_name": "Administrator"},
                },
                ADMIN_IDENTITY_KEY: {"reply_to": {"user_id": self.admin.id, "user_name": "Ada Quietly"}},
            },
        }
        member = self.deliver(self.consumer_for(self.mentor), frame)
        self.assertEqual(member["message"]["reply_to"]["user_name"], "Administrator")
        self.assert_no_real_identity(member)

        admin = self.deliver(self.consumer_for(self.other_admin), frame)
        self.assertEqual(admin["message"]["reply_to"], {
            "id": self.admin_message.id, "user_id": self.admin.id, "user_name": "Ada Quietly",
        })
        self.assertEqual(admin["message"]["sender_name"], "Sam Student")

    def test_mention_frame(self):
        frame = {
            "type": "chat.message",
            "payload": {
                "event": "mention.created",
                "type": "mention.created",
                "group_id": self.group.id,
                "message_id": self.admin_message.id,
                "sender_user_id": None,
                "sender_name": "Administrator",
                "preview": "From the team",
                ADMIN_IDENTITY_KEY: {"payload": {"sender_user_id": self.admin.id, "sender_name": "Ada Quietly"}},
            },
        }
        member = self.deliver(self.consumer_for(self.student), frame)
        self.assertEqual((member["sender_name"], member["sender_user_id"]), ("Administrator", None))
        self.assert_no_real_identity(member)

        admin = self.deliver(self.consumer_for(self.other_admin), frame)
        self.assertEqual((admin["sender_name"], admin["sender_user_id"]), ("Ada Quietly", self.admin.id))
        self.assertNotIn(ADMIN_IDENTITY_KEY, admin)

    def test_consumer_reveals_the_deleter_only_to_admins(self):
        frame = {
            "type": "chat.message",
            "payload": {
                "event": "message.deleted",
                "type": "message.deleted",
                "group_id": self.group.id,
                "message_id": self.admin_message.id,
                "message": {
                    "id": self.admin_message.id,
                    "sender_user": None,
                    "sender_name": "Administrator",
                    "sent_as_admin": True,
                    "is_deleted": True,
                    "deleted_by": None,
                    "deleted_by_name": "Admin",
                    "deleted_by_is_admin": True,
                },
                ADMIN_IDENTITY_KEY: {
                    "message": {"sender_user": self.admin.id, "sender_name": "Ada Quietly", "deleted_by": self.admin.id},
                },
            },
        }
        for viewer in (self.student, self.mentor, self.supervisor):
            with self.subTest(viewer=viewer.email):
                sent = self.deliver(self.consumer_for(viewer), frame)
                self.assertIsNone(sent["message"]["deleted_by"])
                self.assert_admin_id_absent(sent)
                self.assert_no_real_identity(sent)

        sent = self.deliver(self.consumer_for(self.other_admin), frame)
        self.assertEqual(sent["message"]["deleted_by"], self.admin.id)
        self.assertNotIn(ADMIN_IDENTITY_KEY, sent)

    def test_ordinary_frames_pass_through_untouched_without_an_admin_check(self):
        frame = {
            "type": "chat.message",
            "payload": {
                "event": "message.created",
                "type": "message.created",
                "group_id": self.group.id,
                "message": {"id": self.mentor_message.id, "sender_user": self.mentor.id, "sender_name": "Mia Mentor"},
            },
        }
        consumer = self.consumer_for(self.student)
        with patch("apps.chat.management.consumers.is_admin") as check:
            sent = self.deliver(consumer, frame)
        check.assert_not_called()
        self.assertEqual(sent, frame["payload"])


class DeletionMaskingTests(AdminSenderTestBase):
    """Deleting an admin-sent message must not reveal the admin via deleted_by."""

    def remove_from_admin_panel(self, message):
        response = self.client_for(self.admin).delete(
            f"/api/v1/admin/group/{self.group.id}/messages/{message.id}/"
        )
        self.assertEqual(response.status_code, 200, response.data)

    def history(self, viewer):
        # The member list keeps soft-deleted rows as placeholders.
        return self.client_for(viewer).get(f"/chat/groups/{self.group.id}/messages/").data["items"]

    def test_members_cannot_see_who_deleted_an_admin_message(self):
        self.remove_from_admin_panel(self.admin_message)
        for viewer in (self.student, self.mentor, self.supervisor):
            with self.subTest(viewer=viewer.email):
                items = self.history(viewer)
                item = self.by_id(items, self.admin_message)
                self.assertTrue(item["is_deleted"])
                self.assertIsNone(item["deleted_by"])
                # Generic deletion metadata stays: it names no one.
                self.assertEqual(item["deleted_by_name"], "Admin")
                self.assertTrue(item["deleted_by_is_admin"])
                self.assertEqual(item["sender_name"], "Administrator")
                self.assert_admin_id_absent(items)
                self.assert_no_real_identity(items)

    def test_admins_still_see_who_deleted_it(self):
        self.remove_from_admin_panel(self.admin_message)
        item = self.by_id(self.history(self.other_admin), self.admin_message)
        self.assertEqual(item["deleted_by"], self.admin.id)
        self.assertEqual(item["sender_name"], "Ada Quietly")

    def test_detail_of_a_deleted_admin_message_reveals_nothing(self):
        self.remove_from_admin_panel(self.admin_message)
        response = self.client_for(self.student).get(
            f"/chat/groups/{self.group.id}/messages/{self.admin_message.id}/"
        )
        self.assertIn(response.status_code, (200, 404))
        self.assert_admin_id_absent(response.data)
        self.assert_no_real_identity(response.data)

    def test_ordinary_deletions_are_unchanged(self):
        # A member deleting their own message, and an admin moderating a member's
        # message, keep reporting the deleter exactly as before.
        own = Messages.objects.create(group=self.group, sender_user=self.mentor, message_text="oops")
        moderated = Messages.objects.create(group=self.group, sender_user=self.student, message_text="off-topic")
        self.assertEqual(
            self.client_for(self.mentor).delete(f"/chat/groups/{self.group.id}/messages/{own.id}/").status_code, 204,
        )
        self.remove_from_admin_panel(moderated)

        items = self.history(self.student)
        own_item = self.by_id(items, own)
        self.assertEqual((own_item["deleted_by"], own_item["sender_name"]), (self.mentor.id, "Mia Mentor"))
        moderated_item = self.by_id(items, moderated)
        self.assertEqual(moderated_item["deleted_by"], self.admin.id)
        self.assertEqual(moderated_item["sender_name"], "Sam Student")
        self.assertFalse(moderated_item["sent_as_admin"])

    @patch("apps.chat.views.get_channel_layer")
    def test_deletion_broadcast_hides_the_deleter_and_keeps_it_server_side(self, get_layer):
        layer = MagicMock()
        layer.group_send = AsyncMock()
        get_layer.return_value = layer
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client_for(self.admin).delete(
                f"/chat/groups/{self.group.id}/messages/{self.admin_message.id}/"
            )
        self.assertEqual(response.status_code, 204)

        [(_, envelope)] = [call.args for call in layer.group_send.call_args_list]
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "message.deleted")
        self.assertIsNone(payload["message"]["deleted_by"])
        self.assertIsNone(payload["message"]["sender_user"])
        self.assert_admin_id_absent(payload["message"])
        self.assertEqual(payload[ADMIN_IDENTITY_KEY], {
            "message": {"sender_user": self.admin.id, "sender_name": "Ada Quietly", "deleted_by": self.admin.id},
        })

    @patch("apps.chat.views.get_channel_layer")
    def test_member_message_deletion_broadcast_is_unchanged(self, get_layer):
        layer = MagicMock()
        layer.group_send = AsyncMock()
        get_layer.return_value = layer
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.admin).delete(f"/chat/groups/{self.group.id}/messages/{self.mentor_message.id}/")

        [(_, envelope)] = [call.args for call in layer.group_send.call_args_list]
        self.assertNotIn(ADMIN_IDENTITY_KEY, envelope["payload"])
        self.assertEqual(envelope["payload"]["message"]["deleted_by"], self.admin.id)
        self.assertEqual(envelope["payload"]["message"]["sender_user"], self.mentor.id)


class UploadCannotClaimAdminTests(StorageCleanupMixin, AdminSenderTestBase):
    storage_attr = "chat_storage"
    storage_keys_attr = "created_chat_storage_keys"

    def setUp(self):
        super().setUp()
        self.chat_storage = get_chat_storage()
        self.created_chat_storage_keys = []

    def upload(self, user):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client_for(user).post(
                reverse("group-messages-upload", kwargs={"group_pk": self.group.id}),
                {
                    "message_text": "See attached",
                    "uploaded_file": SimpleUploadedFile("plan.pdf", b"plan bytes", content_type="application/pdf"),
                    "sent_as_admin": "true",
                },
                format="multipart",
            )
        self.assertEqual(response.status_code, 201, response.data)
        message = Messages.objects.prefetch_related("attachments").get(pk=response.data["id"])
        self.created_chat_storage_keys.append(message.attachments.get().storage_key)
        return response, message

    def test_member_upload_cannot_set_sent_as_admin(self):
        response, message = self.upload(self.student)
        self.assertFalse(message.sent_as_admin)
        self.assertEqual(response.data["sender_name"], "Sam Student")

    def test_admin_upload_in_group_chat_is_not_flagged(self):
        _, message = self.upload(self.admin)
        self.assertFalse(message.sent_as_admin)
