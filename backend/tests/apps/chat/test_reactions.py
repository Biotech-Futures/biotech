from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.chat.models import MessageReaction, Messages
from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.users.models import AdminScope


CHANNEL_TEST_SETTINGS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


@override_settings(
    CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS,
    CHAT_REACTION_EMOJIS=("\U0001F44D", "❤️", "\U0001F389"),  # 👍 ❤️ 🎉
)
class MessageReactionTests(TestCase):
    THUMBS_UP = "\U0001F44D"
    HEART = "❤️"
    PARTY = "\U0001F389"
    UNSUPPORTED = "\U0001F4A9"

    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(
            email="alice@test.com", password="pw", first_name="Alice", last_name="Liu"
        )
        self.bob = User.objects.create_user(
            email="bob@test.com", password="pw", first_name="Bob", last_name="Lee"
        )
        self.outsider = User.objects.create_user(
            email="outsider@test.com", password="pw", first_name="Out", last_name="Sider"
        )
        self.admin = User.objects.create_user(
            email="admin@test.com", password="pw", first_name="Ad", last_name="Min"
        )

        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=state)
        self.group = Groups.objects.create(group_name="G1", track=self.track)

        GroupMembership.objects.create(user=self.alice, group=self.group)
        GroupMembership.objects.create(user=self.bob, group=self.group)
        AdminScope.objects.create(user=self.admin, is_global=True)

        self.message = Messages.objects.create(
            group=self.group, sender_user=self.alice, message_text="hi"
        )

        self.client_alice = APIClient()
        self.client_alice.force_authenticate(self.alice)
        self.client_bob = APIClient()
        self.client_bob.force_authenticate(self.bob)
        self.client_outsider = APIClient()
        self.client_outsider.force_authenticate(self.outsider)
        self.client_admin = APIClient()
        self.client_admin.force_authenticate(self.admin)

    def _react_url(self, message_id=None):
        return reverse(
            "group-messages-react",
            kwargs={"group_pk": self.group.id, "pk": message_id or self.message.id},
        )

    def _list_url(self):
        return reverse("group-messages-list", kwargs={"group_pk": self.group.id})

    # ---- happy path ----

    def test_add_reaction_creates_row_and_returns_aggregate(self):
        resp = self.client_alice.post(
            self._react_url(), {"emoji": self.THUMBS_UP}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        reactions = resp.data["reactions"]
        self.assertEqual(reactions[self.THUMBS_UP]["count"], 1)
        users = reactions[self.THUMBS_UP]["users"]
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["id"], self.alice.id)
        self.assertEqual(users[0]["name"], "Alice Liu")
        self.assertEqual(
            MessageReaction.objects.filter(message=self.message).count(), 1
        )

    def test_same_emoji_twice_toggles_off(self):
        self.client_alice.post(
            self._react_url(), {"emoji": self.THUMBS_UP}, format="json"
        )
        resp = self.client_alice.post(
            self._react_url(), {"emoji": self.THUMBS_UP}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["reactions"], {})
        self.assertFalse(MessageReaction.objects.filter(message=self.message).exists())

    def test_two_users_same_emoji_aggregates(self):
        self.client_alice.post(
            self._react_url(), {"emoji": self.HEART}, format="json"
        )
        resp = self.client_bob.post(
            self._react_url(), {"emoji": self.HEART}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        entry = resp.data["reactions"][self.HEART]
        self.assertEqual(entry["count"], 2)
        user_ids = sorted(u["id"] for u in entry["users"])
        self.assertEqual(user_ids, sorted([self.alice.id, self.bob.id]))

    def test_user_can_have_multiple_distinct_emojis_on_same_message(self):
        self.client_alice.post(
            self._react_url(), {"emoji": self.THUMBS_UP}, format="json"
        )
        resp = self.client_alice.post(
            self._react_url(), {"emoji": self.HEART}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["reactions"][self.THUMBS_UP]["count"], 1)
        self.assertEqual(resp.data["reactions"][self.HEART]["count"], 1)
        self.assertEqual(
            MessageReaction.objects.filter(
                message=self.message, user=self.alice
            ).count(),
            2,
        )

    def test_list_includes_reactions_field(self):
        self.client_alice.post(
            self._react_url(), {"emoji": self.PARTY}, format="json"
        )
        resp = self.client_bob.get(self._list_url())
        self.assertEqual(resp.status_code, 200)
        item = next(it for it in resp.data["items"] if it["id"] == self.message.id)
        self.assertIn("reactions", item)
        self.assertEqual(item["reactions"][self.PARTY]["count"], 1)
        self.assertEqual(item["reactions"][self.PARTY]["users"][0]["id"], self.alice.id)

    def test_admin_can_react_in_any_group(self):
        resp = self.client_admin.post(
            self._react_url(), {"emoji": self.THUMBS_UP}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.content)

    # ---- validation ----

    def test_unsupported_emoji_rejected(self):
        resp = self.client_alice.post(
            self._react_url(), {"emoji": self.UNSUPPORTED}, format="json"
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("emoji", resp.data)
        self.assertFalse(MessageReaction.objects.exists())

    def test_missing_emoji_rejected(self):
        resp = self.client_alice.post(self._react_url(), {}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("emoji", resp.data)

    def test_non_string_emoji_rejected(self):
        resp = self.client_alice.post(
            self._react_url(), {"emoji": 123}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    # ---- authorization ----

    def test_non_member_forbidden(self):
        resp = self.client_outsider.post(
            self._react_url(), {"emoji": self.THUMBS_UP}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_forbidden(self):
        resp = APIClient().post(
            self._react_url(), {"emoji": self.THUMBS_UP}, format="json"
        )
        self.assertIn(resp.status_code, (401, 403))

    def test_soft_deleted_message_not_reactable(self):
        self.message.soft_delete()
        resp = self.client_alice.post(
            self._react_url(), {"emoji": self.THUMBS_UP}, format="json"
        )
        self.assertEqual(resp.status_code, 404)

    # ---- WS broadcast ----

    @patch("apps.chat.views.get_channel_layer")
    def test_react_broadcasts_flat_envelope(self, mock_get_channel_layer):
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_alice.post(
                self._react_url(), {"emoji": self.THUMBS_UP}, format="json"
            )
            self.assertEqual(resp.status_code, 200, resp.content)

        fake_layer.group_send.assert_called_once()
        group_name, envelope = fake_layer.group_send.call_args.args
        self.assertEqual(group_name, f"group_{self.group.id}")
        self.assertEqual(envelope["type"], "chat.message")
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "message.reaction_updated")
        self.assertEqual(payload["type"], "message.reaction_updated")
        self.assertEqual(payload["group_id"], self.group.id)
        self.assertEqual(payload["message_id"], self.message.id)
        self.assertEqual(payload["reactions"][self.THUMBS_UP]["count"], 1)
        self.assertNotIn("message", payload)
