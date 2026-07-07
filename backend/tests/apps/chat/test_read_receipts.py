from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.chat.models import MessageStatus, Messages
from apps.chat.views import mark_delivered_cursor
from apps.groups.models import GroupMembership, Groups
from apps.users.models import AdminScope


CHANNEL_TEST_SETTINGS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class MessageReadReceiptTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(
            email="alice@test.com", password="pw", first_name="Alice", last_name="Liu"
        )
        self.bob = User.objects.create_user(
            email="bob@test.com", password="pw", first_name="Bob", last_name="Lee"
        )
        self.carol = User.objects.create_user(
            email="carol@test.com", password="pw", first_name="Carol", last_name="Ng"
        )
        self.outsider = User.objects.create_user(
            email="out@test.com", password="pw", first_name="Out", last_name="Sider"
        )
        self.admin = User.objects.create_user(
            email="admin@test.com", password="pw", first_name="Ad", last_name="Min"
        )

        self.group = Groups.objects.create(group_name="G1")
        self.other_group = Groups.objects.create(group_name="G2")

        GroupMembership.objects.create(user=self.alice, group=self.group)
        GroupMembership.objects.create(user=self.bob, group=self.group)
        GroupMembership.objects.create(user=self.carol, group=self.group)
        AdminScope.objects.create(user=self.admin)

        # Alice sends 3, Bob sends 1.
        self.m1 = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="a1")
        self.m2 = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="a2")
        self.m3 = Messages.objects.create(group=self.group, sender_user=self.bob, message_text="b1")
        self.m4 = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="a3")

        self.client_alice = APIClient(); self.client_alice.force_authenticate(self.alice)
        self.client_bob = APIClient(); self.client_bob.force_authenticate(self.bob)
        self.client_carol = APIClient(); self.client_carol.force_authenticate(self.carol)
        self.client_outsider = APIClient(); self.client_outsider.force_authenticate(self.outsider)
        self.client_admin = APIClient(); self.client_admin.force_authenticate(self.admin)

    def _read_url(self, message):
        return reverse(
            "group-messages-read",
            kwargs={"group_pk": self.group.id, "pk": message.id},
        )

    def _list_url(self):
        return reverse("group-messages-list", kwargs={"group_pk": self.group.id})

    # ---- cursor semantics ----

    def test_mark_cursor_marks_all_earlier_and_skips_own(self):
        resp = self.client_bob.post(self._read_url(self.m4))
        self.assertEqual(resp.status_code, 200, resp.content)
        # m1, m2, m4 are Alice's; m3 is Bob's own (skipped). Scope = 3 (excludes Bob's own).
        self.assertEqual(resp.data["up_to_id"], self.m4.id)
        self.assertEqual(resp.data["marked_count"], 3)
        # Three MessageStatus rows for Bob; none for his own m3.
        bob_rows = MessageStatus.objects.filter(user=self.bob)
        self.assertEqual(bob_rows.count(), 3)
        self.assertFalse(bob_rows.filter(message_id=self.m3.id).exists())
        for row in bob_rows:
            self.assertEqual(row.status, MessageStatus.StatusChoices.READ)
            self.assertIsNotNone(row.read_at)

    def test_marking_is_idempotent(self):
        self.client_bob.post(self._read_url(self.m4))
        first_read_at = MessageStatus.objects.get(user=self.bob, message=self.m1).read_at
        resp = self.client_bob.post(self._read_url(self.m4))
        self.assertEqual(resp.status_code, 200)
        # No duplicate rows, and read_at is unchanged (existing read rows are
        # filtered out of the update).
        self.assertEqual(
            MessageStatus.objects.filter(user=self.bob, message=self.m1).count(), 1
        )
        self.assertEqual(
            MessageStatus.objects.get(user=self.bob, message=self.m1).read_at,
            first_read_at,
        )

    def test_partial_then_full_cursor_only_marks_new(self):
        # Bob reads up to m2 (Alice's), then later up to m4.
        self.client_bob.post(self._read_url(self.m2))
        self.assertEqual(MessageStatus.objects.filter(user=self.bob, read_at__isnull=False).count(), 2)
        self.client_bob.post(self._read_url(self.m4))
        # Should now have 3 read rows (m1, m2, m4 — m3 is Bob's own).
        self.assertEqual(MessageStatus.objects.filter(user=self.bob, read_at__isnull=False).count(), 3)

    def test_delivered_then_read_advances_status(self):
        # Simulate a pre-existing "delivered" row with no read_at.
        from django.utils import timezone
        MessageStatus.objects.create(
            message=self.m1,
            user=self.bob,
            status=MessageStatus.StatusChoices.DELIVERED,
            delivered_at=timezone.now(),
        )
        self.client_bob.post(self._read_url(self.m1))
        row = MessageStatus.objects.get(user=self.bob, message=self.m1)
        self.assertEqual(row.status, MessageStatus.StatusChoices.READ)
        self.assertIsNotNone(row.read_at)

    def test_soft_deleted_messages_skipped_from_scope(self):
        self.m2.soft_delete()
        resp = self.client_bob.post(self._read_url(self.m4))
        self.assertEqual(resp.status_code, 200)
        # Only m1 and m4 in scope (m2 deleted, m3 is Bob's own).
        self.assertEqual(resp.data["marked_count"], 2)
        self.assertFalse(MessageStatus.objects.filter(user=self.bob, message=self.m2).exists())

    # ---- payload enrichment ----

    def test_list_payload_includes_read_count_and_is_read_by_me(self):
        # Bob reads up to m2; Carol reads up to m1.
        self.client_bob.post(self._read_url(self.m2))
        self.client_carol.post(self._read_url(self.m1))
        resp = self.client_alice.get(self._list_url())
        items = {it["id"]: it for it in resp.data["items"]}
        self.assertEqual(items[self.m1.id]["read_count"], 2)   # Bob + Carol
        self.assertEqual(items[self.m2.id]["read_count"], 1)   # Bob only
        self.assertEqual(items[self.m4.id]["read_count"], 0)
        # Alice (sender) is_read_by_me — Alice has no status rows of her own.
        self.assertFalse(items[self.m1.id]["is_read_by_me"])

    def test_is_read_by_me_true_after_marking(self):
        self.client_bob.post(self._read_url(self.m2))
        resp = self.client_bob.get(self._list_url())
        items = {it["id"]: it for it in resp.data["items"]}
        self.assertTrue(items[self.m1.id]["is_read_by_me"])
        self.assertTrue(items[self.m2.id]["is_read_by_me"])
        self.assertFalse(items[self.m4.id]["is_read_by_me"])

    # ---- authorization ----

    def test_non_member_forbidden(self):
        resp = self.client_outsider.post(self._read_url(self.m1))
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_mark_in_any_group(self):
        resp = self.client_admin.post(self._read_url(self.m1))
        self.assertEqual(resp.status_code, 200)

    def test_pivot_in_other_group_returns_404(self):
        other_msg = Messages.objects.create(
            group=self.other_group, sender_user=self.alice, message_text="other"
        )
        url = reverse(
            "group-messages-read",
            kwargs={"group_pk": self.group.id, "pk": other_msg.id},
        )
        resp = self.client_bob.post(url)
        self.assertEqual(resp.status_code, 404)

    def test_pivot_soft_deleted_returns_404(self):
        self.m4.soft_delete()
        resp = self.client_bob.post(self._read_url(self.m4))
        self.assertEqual(resp.status_code, 404)

    # ---- WS broadcast ----

    @patch("apps.chat.views.get_channel_layer")
    def test_read_broadcasts_flat_envelope(self, mock_get_channel_layer):
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_bob.post(self._read_url(self.m2))
            self.assertEqual(resp.status_code, 200, resp.content)

        fake_layer.group_send.assert_called_once()
        group_name, envelope = fake_layer.group_send.call_args.args
        self.assertEqual(group_name, f"group_{self.group.id}")
        self.assertEqual(envelope["type"], "chat.message")
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "message.read_updated")
        self.assertEqual(payload["type"], "message.read_updated")
        self.assertEqual(payload["group_id"], self.group.id)
        self.assertEqual(payload["reader_id"], self.bob.id)
        self.assertEqual(payload["up_to_id"], self.m2.id)
        self.assertNotIn("message", payload)


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class MessageDeliveredReceiptTests(TestCase):
    """Mirrors ``MessageReadReceiptTests`` for the delivered cursor.

    The cursor logic is symmetric (same scope rules, same idempotence,
    same "skip the sender's own" rule), so these tests focus on the
    delivered-specific invariants: ``delivered_at`` is set without
    touching ``read_at``, and a row that is already ``read`` is NEVER
    downgraded back to ``delivered``.
    """

    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(
            email="alice2@test.com", password="pw", first_name="Alice", last_name="Liu"
        )
        self.bob = User.objects.create_user(
            email="bob2@test.com", password="pw", first_name="Bob", last_name="Lee"
        )
        self.outsider = User.objects.create_user(
            email="out2@test.com", password="pw", first_name="Out", last_name="Sider"
        )

        self.group = Groups.objects.create(group_name="G1")
        self.other_group = Groups.objects.create(group_name="G2")

        GroupMembership.objects.create(user=self.alice, group=self.group)
        GroupMembership.objects.create(user=self.bob, group=self.group)

        # Alice sends 2, Bob sends 1.
        self.m1 = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="a1")
        self.m2 = Messages.objects.create(group=self.group, sender_user=self.bob, message_text="b1")
        self.m3 = Messages.objects.create(group=self.group, sender_user=self.alice, message_text="a2")

        self.client_alice = APIClient(); self.client_alice.force_authenticate(self.alice)
        self.client_bob = APIClient(); self.client_bob.force_authenticate(self.bob)
        self.client_outsider = APIClient(); self.client_outsider.force_authenticate(self.outsider)

    def _delivered_url(self, message):
        return reverse(
            "group-messages-delivered",
            kwargs={"group_pk": self.group.id, "pk": message.id},
        )

    def _list_url(self):
        return reverse("group-messages-list", kwargs={"group_pk": self.group.id})

    # ---- cursor semantics ----

    def test_marks_earlier_and_skips_own(self):
        resp = self.client_bob.post(self._delivered_url(self.m3))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["up_to_id"], self.m3.id)
        # m1, m3 are Alice's; m2 is Bob's own (skipped).
        self.assertEqual(resp.data["marked_count"], 2)
        bob_rows = MessageStatus.objects.filter(user=self.bob)
        self.assertEqual(bob_rows.count(), 2)
        self.assertFalse(bob_rows.filter(message_id=self.m2.id).exists())
        for row in bob_rows:
            self.assertEqual(row.status, MessageStatus.StatusChoices.DELIVERED)
            self.assertIsNotNone(row.delivered_at)
            self.assertIsNone(row.read_at)  # delivered alone — read_at untouched

    def test_idempotent(self):
        self.client_bob.post(self._delivered_url(self.m3))
        first_delivered_at = MessageStatus.objects.get(user=self.bob, message=self.m1).delivered_at
        resp = self.client_bob.post(self._delivered_url(self.m3))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            MessageStatus.objects.filter(user=self.bob, message=self.m1).count(), 1
        )
        self.assertEqual(
            MessageStatus.objects.get(user=self.bob, message=self.m1).delivered_at,
            first_delivered_at,
        )

    def test_does_not_downgrade_already_read(self):
        # Read first (sets both delivered_at and read_at, status=read),
        # then call delivered — status MUST stay "read".
        from django.utils import timezone
        MessageStatus.objects.create(
            message=self.m1,
            user=self.bob,
            status=MessageStatus.StatusChoices.READ,
            delivered_at=timezone.now(),
            read_at=timezone.now(),
        )
        self.client_bob.post(self._delivered_url(self.m3))
        row = MessageStatus.objects.get(user=self.bob, message=self.m1)
        self.assertEqual(row.status, MessageStatus.StatusChoices.READ)
        self.assertIsNotNone(row.read_at)

    def test_backfills_delivered_at_when_only_read_at_set(self):
        # Pathological row: read_at set without delivered_at. The
        # cursor should backfill delivered_at WITHOUT clearing read_at
        # or downgrading the status.
        from django.utils import timezone
        MessageStatus.objects.create(
            message=self.m1,
            user=self.bob,
            status=MessageStatus.StatusChoices.READ,
            delivered_at=None,
            read_at=timezone.now(),
        )
        self.client_bob.post(self._delivered_url(self.m3))
        row = MessageStatus.objects.get(user=self.bob, message=self.m1)
        self.assertEqual(row.status, MessageStatus.StatusChoices.READ)
        self.assertIsNotNone(row.delivered_at)
        self.assertIsNotNone(row.read_at)

    def test_soft_deleted_skipped(self):
        self.m1.soft_delete()
        resp = self.client_bob.post(self._delivered_url(self.m3))
        self.assertEqual(resp.status_code, 200)
        # m1 deleted, m2 is Bob's own — only m3 left in scope.
        self.assertEqual(resp.data["marked_count"], 1)
        self.assertFalse(MessageStatus.objects.filter(user=self.bob, message=self.m1).exists())

    # ---- payload enrichment ----

    def test_list_payload_includes_delivered_count_and_is_delivered_to_me(self):
        self.client_bob.post(self._delivered_url(self.m3))
        resp = self.client_alice.get(self._list_url())
        items = {it["id"]: it for it in resp.data["items"]}
        self.assertEqual(items[self.m1.id]["delivered_count"], 1)  # Bob
        self.assertEqual(items[self.m3.id]["delivered_count"], 1)  # Bob
        self.assertEqual(items[self.m2.id]["delivered_count"], 0)  # Bob's own
        # is_delivered_to_me is from the *caller's* perspective. Alice
        # has no rows for any message — her perspective is empty.
        self.assertFalse(items[self.m1.id]["is_delivered_to_me"])

    def test_delivered_count_includes_read(self):
        # Read implies delivered (the read endpoint sets both
        # timestamps). delivered_count is the superset.
        read_url = reverse(
            "group-messages-read",
            kwargs={"group_pk": self.group.id, "pk": self.m3.id},
        )
        self.client_bob.post(read_url)
        resp = self.client_alice.get(self._list_url())
        items = {it["id"]: it for it in resp.data["items"]}
        self.assertEqual(items[self.m1.id]["delivered_count"], 1)
        self.assertEqual(items[self.m1.id]["read_count"], 1)

    # ---- authorization ----

    def test_non_member_forbidden(self):
        resp = self.client_outsider.post(self._delivered_url(self.m1))
        self.assertEqual(resp.status_code, 403)

    # ---- WS broadcast ----

    @patch("apps.chat.views.get_channel_layer")
    def test_delivered_broadcasts_flat_envelope(self, mock_get_channel_layer):
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_bob.post(self._delivered_url(self.m3))
            self.assertEqual(resp.status_code, 200, resp.content)

        fake_layer.group_send.assert_called_once()
        group_name, envelope = fake_layer.group_send.call_args.args
        self.assertEqual(group_name, f"group_{self.group.id}")
        self.assertEqual(envelope["type"], "chat.message")
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "message.delivered_updated")
        self.assertEqual(payload["type"], "message.delivered_updated")
        self.assertEqual(payload["group_id"], self.group.id)
        self.assertEqual(payload["user_id"], self.bob.id)
        self.assertEqual(payload["up_to_id"], self.m3.id)
        self.assertNotIn("message", payload)


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class MarkDeliveredCursorUnitTests(TestCase):
    """Direct tests for ``mark_delivered_cursor`` — the helper the WS
    consumer calls on connect. The HTTP action is just a thin wrapper
    around this, so coverage here also covers the consumer path
    without standing up a WebsocketCommunicator."""

    def setUp(self):
        User = get_user_model()
        self.sender = User.objects.create_user(email="s@test.com", password="pw")
        self.receiver = User.objects.create_user(email="r@test.com", password="pw")

        self.group = Groups.objects.create(group_name="G")
        GroupMembership.objects.create(user=self.sender, group=self.group)
        GroupMembership.objects.create(user=self.receiver, group=self.group)

        self.m1 = Messages.objects.create(group=self.group, sender_user=self.sender, message_text="x1")
        self.m2 = Messages.objects.create(group=self.group, sender_user=self.sender, message_text="x2")

    def test_helper_creates_rows(self):
        count = mark_delivered_cursor(self.receiver, self.group.id, self.m2.id)
        self.assertEqual(count, 2)
        self.assertEqual(
            MessageStatus.objects.filter(user=self.receiver).count(), 2
        )

    def test_helper_empty_scope_returns_zero(self):
        # Nothing in this group from someone other than receiver — they
        # haven't sent any messages, but the receiver sent none either.
        # Use a fresh group with only the receiver's own messages.
        other_group = Groups.objects.create(group_name="solo")
        GroupMembership.objects.create(user=self.receiver, group=other_group)
        msg = Messages.objects.create(group=other_group, sender_user=self.receiver, message_text="self")
        count = mark_delivered_cursor(self.receiver, other_group.id, msg.id)
        self.assertEqual(count, 0)
        self.assertEqual(MessageStatus.objects.filter(user=self.receiver, message=msg).count(), 0)
