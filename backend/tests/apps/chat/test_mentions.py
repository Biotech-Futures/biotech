"""End-to-end coverage for @mentions.

Verifies the four moving pieces wired in this feature: token parsing,
write-time RBAC (group-membership filter, self-mention skip), the
inbox endpoint (list / mark-read), and the per-user WS push.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.chat.models import MessageMention, Messages
from apps.chat.utils import parse_mentions
from apps.groups.models import Groups, GroupMembership


class ParseMentionsTests(TestCase):
    def test_parses_single_token(self):
        self.assertEqual(parse_mentions("hi <@5> there"), ({5}, False))

    def test_parses_multiple_unique_tokens(self):
        self.assertEqual(parse_mentions("<@5> and <@7> and <@5> again"), ({5, 7}, False))

    def test_returns_empty_for_no_tokens(self):
        self.assertEqual(parse_mentions("plain text with no mentions"), (set(), False))

    def test_handles_empty_and_none(self):
        self.assertEqual(parse_mentions(""), (set(), False))
        self.assertEqual(parse_mentions(None), (set(), False))

    def test_ignores_malformed_tokens(self):
        # The regex requires digits inside <@...>; bare @5 or <@x> are no-ops.
        self.assertEqual(parse_mentions("ping @5 and <@x>"), (set(), False))

    def test_detects_everyone_keyword(self):
        self.assertEqual(parse_mentions("heads up @everyone"), (set(), True))

    def test_everyone_is_case_insensitive(self):
        self.assertEqual(parse_mentions("@Everyone read this"), (set(), True))

    def test_everyone_combines_with_user_mentions(self):
        self.assertEqual(
            parse_mentions(f"<@5> ping and @everyone too"), ({5}, True),
        )

    def test_everyone_inside_word_is_ignored(self):
        # ``foo@everyone`` is not a mention — guards against email-ish text.
        self.assertEqual(parse_mentions("contact foo@everyone.com"), (set(), False))


class MentionWireupTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(
            email="alice-m@test.com", password="pw", first_name="Alice", last_name="A"
        )
        self.bob = User.objects.create_user(
            email="bob-m@test.com", password="pw", first_name="Bob", last_name="B"
        )
        self.carol = User.objects.create_user(
            email="carol-m@test.com", password="pw", first_name="Carol", last_name="C"
        )
        self.outsider = User.objects.create_user(
            email="out-m@test.com", password="pw", first_name="Out", last_name="O"
        )

        # Geography (state/country) is irrelevant to @mentions, which key
        # off group membership only. Groups no longer carry a track.
        self.group = Groups.objects.create(group_name="G1")
        self.other_group = Groups.objects.create(group_name="G2")

        GroupMembership.objects.create(user=self.alice, group=self.group)
        GroupMembership.objects.create(user=self.bob, group=self.group)
        GroupMembership.objects.create(user=self.carol, group=self.group)
        GroupMembership.objects.create(user=self.outsider, group=self.other_group)

        self.client_alice = APIClient(); self.client_alice.force_authenticate(self.alice)
        self.client_bob = APIClient(); self.client_bob.force_authenticate(self.bob)

    def _post_url(self):
        return reverse("group-messages-list", kwargs={"group_pk": self.group.id})

    # ----- creation -----

    def test_mention_row_created_for_group_member(self):
        resp = self.client_alice.post(
            self._post_url(),
            {"message_text": f"hi <@{self.bob.id}>", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        mid = resp.data["id"]
        self.assertTrue(
            MessageMention.objects.filter(message_id=mid, mentioned_user=self.bob).exists()
        )

    def test_mention_to_non_member_is_dropped(self):
        # outsider is in other_group, not self.group — mention must not insert.
        resp = self.client_alice.post(
            self._post_url(),
            {"message_text": f"hello <@{self.outsider.id}>", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(
            MessageMention.objects
            .filter(message_id=resp.data["id"], mentioned_user=self.outsider)
            .exists()
        )

    def test_self_mention_is_dropped(self):
        resp = self.client_alice.post(
            self._post_url(),
            {"message_text": f"talking to myself <@{self.alice.id}>", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(
            MessageMention.objects
            .filter(message_id=resp.data["id"], mentioned_user=self.alice)
            .exists()
        )

    def test_multiple_distinct_mentions_in_one_message(self):
        resp = self.client_alice.post(
            self._post_url(),
            {"message_text": f"<@{self.bob.id}> and <@{self.carol.id}>", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        ids = set(
            MessageMention.objects
            .filter(message_id=resp.data["id"])
            .values_list("mentioned_user_id", flat=True)
        )
        self.assertEqual(ids, {self.bob.id, self.carol.id})

    def test_edit_adds_new_mention_idempotently(self):
        msg = Messages.objects.create(
            group=self.group, sender_user=self.alice, message_text="hi nobody"
        )
        edit_url = reverse(
            "group-messages-detail",
            kwargs={"group_pk": self.group.id, "pk": msg.id},
        )

        # Edit 1: add Bob.
        resp = self.client_alice.patch(
            edit_url, {"message_text": f"hi <@{self.bob.id}>"}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(
            list(MessageMention.objects.filter(message=msg).values_list("mentioned_user_id", flat=True)),
            [self.bob.id],
        )

        # Edit 2: same mention again — must not duplicate.
        resp = self.client_alice.patch(
            edit_url, {"message_text": f"hi <@{self.bob.id}> still"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            MessageMention.objects.filter(message=msg, mentioned_user=self.bob).count(), 1
        )

        # Edit 3: add Carol — Bob's row stays.
        resp = self.client_alice.patch(
            edit_url,
            {"message_text": f"hi <@{self.bob.id}> and <@{self.carol.id}>"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            set(
                MessageMention.objects.filter(message=msg)
                .values_list("mentioned_user_id", flat=True)
            ),
            {self.bob.id, self.carol.id},
        )

    # ----- inbox endpoint -----

    def test_inbox_lists_only_callers_mentions(self):
        m_alice = Messages.objects.create(
            group=self.group, sender_user=self.alice, message_text="m1"
        )
        m_bob = Messages.objects.create(
            group=self.group, sender_user=self.alice, message_text="m2"
        )
        MessageMention.objects.create(message=m_alice, mentioned_user=self.bob)
        MessageMention.objects.create(message=m_bob, mentioned_user=self.carol)

        resp = self.client_bob.get(reverse("mentions-list"))
        self.assertEqual(resp.status_code, 200, resp.content)
        ids = [it["message_id"] for it in resp.data["items"]]
        self.assertEqual(ids, [m_alice.id])
        self.assertEqual(resp.data["unread_count"], 1)

    def test_inbox_unread_filter(self):
        m1 = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="m1")
        m2 = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="m2")
        unread = MessageMention.objects.create(message=m1, mentioned_user=self.bob)
        already_read = MessageMention.objects.create(message=m2, mentioned_user=self.bob)
        from django.utils import timezone
        already_read.read_at = timezone.now()
        already_read.save(update_fields=["read_at"])

        resp = self.client_bob.get(reverse("mentions-list") + "?unread=true")
        self.assertEqual(resp.status_code, 200)
        ids = [it["id"] for it in resp.data["items"]]
        self.assertEqual(ids, [unread.id])

    def test_inbox_hides_text_for_soft_deleted_parent(self):
        m = Messages.objects.create(
            group=self.group,
            sender_user=self.alice,
            message_text="leaked secret",
        )
        m.soft_delete()
        MessageMention.objects.create(message=m, mentioned_user=self.bob)
        resp = self.client_bob.get(reverse("mentions-list"))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["items"][0]["message_text"])

    def test_mark_read_endpoint(self):
        m = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="m")
        mention = MessageMention.objects.create(message=m, mentioned_user=self.bob)
        url = reverse("mentions-read", kwargs={"pk": mention.id})

        resp = self.client_bob.post(url)
        self.assertEqual(resp.status_code, 200)
        mention.refresh_from_db()
        self.assertIsNotNone(mention.read_at)

    def test_mark_read_does_not_leak_other_users_mention(self):
        m = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="m")
        mention_for_carol = MessageMention.objects.create(message=m, mentioned_user=self.carol)
        url = reverse("mentions-read", kwargs={"pk": mention_for_carol.id})

        resp = self.client_bob.post(url)  # Bob is NOT the mention's target.
        self.assertEqual(resp.status_code, 404)
        mention_for_carol.refresh_from_db()
        self.assertIsNone(mention_for_carol.read_at)

    def test_mark_all_read_clears_only_caller_inbox(self):
        m1 = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="m1")
        m2 = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="m2")
        m3 = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="m3")
        bob_unread = MessageMention.objects.create(message=m1, mentioned_user=self.bob)
        bob_unread2 = MessageMention.objects.create(message=m2, mentioned_user=self.bob)
        carol_unread = MessageMention.objects.create(message=m3, mentioned_user=self.carol)

        resp = self.client_bob.post(reverse("mentions-mark-all-read"))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["marked_count"], 2)
        self.assertEqual(resp.data["unread_count"], 0)

        bob_unread.refresh_from_db(); bob_unread2.refresh_from_db()
        self.assertIsNotNone(bob_unread.read_at)
        self.assertIsNotNone(bob_unread2.read_at)
        carol_unread.refresh_from_db()
        self.assertIsNone(carol_unread.read_at)  # not touched

    def test_mark_all_read_is_idempotent(self):
        resp = self.client_bob.post(reverse("mentions-mark-all-read"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["marked_count"], 0)
        self.assertEqual(resp.data["unread_count"], 0)

    def test_inbox_requires_authentication(self):
        anon = APIClient()
        resp = anon.get(reverse("mentions-list"))
        # IsAuthenticated returns 401 or 403 depending on settings; both are denials.
        self.assertIn(resp.status_code, (401, 403))

    # ----- WS push -----

    @patch("apps.chat.views.get_channel_layer")
    def test_mention_publishes_to_per_user_channel(self, mock_get_channel_layer):
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_alice.post(
                self._post_url(),
                {"message_text": f"<@{self.bob.id}> see this", "resources": []},
                format="json",
            )
        self.assertEqual(resp.status_code, 201, resp.content)

        # Two fan-outs in total: the room broadcast and the per-user mention push.
        channel_names = [call.args[0] for call in fake_layer.group_send.call_args_list]
        self.assertIn(f"group_{self.group.id}", channel_names)
        self.assertIn(f"user_{self.bob.id}", channel_names)

        mention_call = next(
            call for call in fake_layer.group_send.call_args_list
            if call.args[0] == f"user_{self.bob.id}"
        )
        envelope = mention_call.args[1]
        self.assertEqual(envelope["type"], "chat.message")
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "mention.created")
        self.assertEqual(payload["group_id"], self.group.id)
        self.assertEqual(payload["message_id"], resp.data["id"])
        self.assertEqual(payload["sender_user_id"], self.alice.id)
        self.assertIn("see this", payload["preview"])

    # ----- @everyone -----

    def test_everyone_creates_row_for_each_active_member_except_sender(self):
        resp = self.client_alice.post(
            self._post_url(),
            {"message_text": "heads up @everyone", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        ids = set(
            MessageMention.objects
            .filter(message_id=resp.data["id"])
            .values_list("mentioned_user_id", flat=True)
        )
        self.assertEqual(ids, {self.bob.id, self.carol.id})

    def test_everyone_does_not_reach_other_groups(self):
        resp = self.client_alice.post(
            self._post_url(),
            {"message_text": "@everyone in this group only", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        ids = set(
            MessageMention.objects
            .filter(message_id=resp.data["id"])
            .values_list("mentioned_user_id", flat=True)
        )
        self.assertNotIn(self.outsider.id, ids)

    def test_everyone_subsumes_individual_mention_of_member(self):
        # Mixing @everyone with an explicit <@bob> still yields one row for Bob.
        resp = self.client_alice.post(
            self._post_url(),
            {"message_text": f"@everyone and <@{self.bob.id}>", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            MessageMention.objects
            .filter(message_id=resp.data["id"], mentioned_user=self.bob)
            .count(),
            1,
        )

    @patch("apps.chat.views.get_channel_layer")
    def test_everyone_publishes_to_each_member_channel(self, mock_get_channel_layer):
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_alice.post(
                self._post_url(),
                {"message_text": "@everyone come look", "resources": []},
                format="json",
            )
        self.assertEqual(resp.status_code, 201, resp.content)

        channel_names = [call.args[0] for call in fake_layer.group_send.call_args_list]
        self.assertIn(f"user_{self.bob.id}", channel_names)
        self.assertIn(f"user_{self.carol.id}", channel_names)
        self.assertNotIn(f"user_{self.alice.id}", channel_names)  # sender excluded
        self.assertNotIn(f"user_{self.outsider.id}", channel_names)  # other group
