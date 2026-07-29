from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.chat.models import MessageStatus, Messages
from apps.chat.rbac import chat_recipients_qs
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


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class MessageStatusEndpointTests(TestCase):
    """The ``/status`` action behind the sender's read-receipt popover.

    A mentor saw "Receipt details unavailable" on a message no student had
    opened: two empty lists were indistinguishable from a failed lookup.
    ``pending`` closes that gap, so these tests pin the empty case as hard
    as the populated one.
    """

    def setUp(self):
        User = get_user_model()
        self.mentor = User.objects.create_user(
            email="mentor@test.com", password="pw", first_name="Kai", last_name="Lee"
        )
        self.student_a = User.objects.create_user(
            email="sa@test.com", password="pw", first_name="Ann", last_name="Ng"
        )
        self.student_b = User.objects.create_user(
            email="sb@test.com", password="pw", first_name="Bo", last_name="Tan"
        )
        self.supervisor = User.objects.create_user(
            email="sup@test.com", password="pw", first_name="Sue", last_name="Perv"
        )
        self.suspended = User.objects.create_user(
            email="susp@test.com", password="pw", first_name="Sus", last_name="Pended"
        )
        self.suspended.account_status = User.AccountStatus.SUSPENDED
        self.suspended.save(update_fields=["account_status"])
        # invited: is_active=False but can still sign in, so still a recipient.
        self.invited = User.objects.create_user(
            email="inv@test.com", password="pw", first_name="Ivy", last_name="Ted"
        )
        self.invited.account_status = User.AccountStatus.INVITED
        self.invited.is_active = False
        self.invited.save(update_fields=["account_status", "is_active"])
        self.outsider = User.objects.create_user(
            email="out2@test.com", password="pw", first_name="Out", last_name="Sider"
        )

        self.group = Groups.objects.create(group_name="G-mentor")
        R = GroupMembership.MembershipRoleChoices
        GroupMembership.objects.create(user=self.mentor, group=self.group, membership_role=R.MENTOR)
        GroupMembership.objects.create(user=self.student_a, group=self.group, membership_role=R.STUDENT)
        GroupMembership.objects.create(user=self.student_b, group=self.group, membership_role=R.STUDENT)
        GroupMembership.objects.create(user=self.supervisor, group=self.group, membership_role=R.SUPERVISOR)
        GroupMembership.objects.create(user=self.suspended, group=self.group, membership_role=R.STUDENT)
        GroupMembership.objects.create(user=self.invited, group=self.group, membership_role=R.STUDENT)

        self.welcome = Messages.objects.create(
            group=self.group, sender_user=self.mentor, message_text="welcome!"
        )

        self.client_mentor = APIClient(); self.client_mentor.force_authenticate(self.mentor)
        self.client_a = APIClient(); self.client_a.force_authenticate(self.student_a)
        self.client_outsider = APIClient(); self.client_outsider.force_authenticate(self.outsider)

    def _status_url(self, message):
        return reverse(
            "group-messages-message-status",
            kwargs={"group_pk": self.group.id, "pk": message.id},
        )

    def _read_url(self, message):
        return reverse(
            "group-messages-read",
            kwargs={"group_pk": self.group.id, "pk": message.id},
        )

    def _names(self, rows):
        return sorted(row["name"] for row in rows)

    def test_nobody_opened_yet_returns_pending_not_empty_everything(self):
        resp = self.client_mentor.get(self._status_url(self.welcome))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["read_by"], [])
        self.assertEqual(resp.data["delivered_by"], [])
        # Students + the invited student. Never the supervisor, the suspended
        # account, or the mentor who sent it.
        self.assertEqual(self._names(resp.data["pending"]), ["Ann Ng", "Bo Tan", "Ivy Ted"])

    def test_sender_absent_from_every_list(self):
        self.client_a.post(self._read_url(self.welcome))
        resp = self.client_mentor.get(self._status_url(self.welcome))
        everyone = (
            resp.data["read_by"] + resp.data["delivered_by"] + resp.data["pending"]
        )
        self.assertNotIn(self.mentor.id, [row["id"] for row in everyone])

    def test_pending_shrinks_as_receipts_land(self):
        self.client_a.post(self._read_url(self.welcome))
        resp = self.client_mentor.get(self._status_url(self.welcome))
        self.assertEqual(self._names(resp.data["read_by"]), ["Ann Ng"])
        self.assertEqual(self._names(resp.data["pending"]), ["Bo Tan", "Ivy Ted"])

    def test_delivered_only_member_is_not_pending(self):
        mark_delivered_cursor(self.student_b, self.group.id, self.welcome.id)
        resp = self.client_mentor.get(self._status_url(self.welcome))
        self.assertEqual(self._names(resp.data["delivered_by"]), ["Bo Tan"])
        self.assertNotIn("Bo Tan", self._names(resp.data["pending"]))

    def test_supervisor_who_reads_appears_but_is_never_pending(self):
        # Supervisors are excluded from the recipient denominator, but they can
        # still open the board — a real read must not be silently dropped.
        client_sup = APIClient(); client_sup.force_authenticate(self.supervisor)
        client_sup.post(self._read_url(self.welcome))
        resp = self.client_mentor.get(self._status_url(self.welcome))
        self.assertEqual(self._names(resp.data["read_by"]), ["Sue Perv"])
        self.assertNotIn("Sue Perv", self._names(resp.data["pending"]))

    def test_supervisor_read_does_not_count_toward_the_ticks(self):
        # The bug this guards: read_count counted every status row while
        # recipient_count excluded supervisors, so one supervisor opening the
        # board could push a message to "read by everyone" while students who
        # never received it were still listed as pending.
        client_sup = APIClient(); client_sup.force_authenticate(self.supervisor)
        client_sup.post(self._read_url(self.welcome))
        self.client_a.post(self._read_url(self.welcome))

        resp = self.client_mentor.get(self._list_url())
        row = next(m for m in resp.data["items"] if m["id"] == self.welcome.id)
        self.assertEqual(row["read_by_ids"], [self.student_a.id])
        self.assertEqual(row["read_count"], 1)
        self.assertNotIn(self.supervisor.id, row["delivered_to_ids"])
        # Numerator and denominator must describe the same population.
        self.assertLess(row["read_count"], resp.data["recipient_count"])

    def test_blocked_account_read_does_not_count_toward_the_ticks(self):
        # Same failure mode via a suspended member rather than a supervisor.
        MessageStatus.objects.create(
            message=self.welcome,
            user=self.suspended,
            status=MessageStatus.StatusChoices.READ,
            delivered_at=timezone.now(),
            read_at=timezone.now(),
        )
        resp = self.client_mentor.get(self._list_url())
        row = next(m for m in resp.data["items"] if m["id"] == self.welcome.id)
        self.assertEqual(row["read_count"], 0)
        self.assertEqual(row["read_by_ids"], [])

    def test_left_member_is_not_pending(self):
        membership = GroupMembership.objects.get(user=self.student_b, group=self.group)
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])
        resp = self.client_mentor.get(self._status_url(self.welcome))
        self.assertEqual(self._names(resp.data["pending"]), ["Ann Ng", "Ivy Ted"])

    def test_non_member_cannot_read_receipts(self):
        resp = self.client_outsider.get(self._status_url(self.welcome))
        self.assertIn(resp.status_code, (403, 404))

    def test_pending_carries_no_email(self):
        # get_full_name only; emails stay admin-only elsewhere in the roster API.
        resp = self.client_mentor.get(self._status_url(self.welcome))
        serialized = str(resp.data)
        self.assertNotIn("@test.com", serialized)

    # ---- reader ids + recipient denominator ----

    def _list_url(self):
        return reverse("group-messages-list", kwargs={"group_pk": self.group.id})

    def test_list_exposes_reader_ids_matching_counts(self):
        self.client_a.post(self._read_url(self.welcome))
        mark_delivered_cursor(self.student_b, self.group.id, self.welcome.id)

        resp = self.client_mentor.get(self._list_url())
        row = next(m for m in resp.data["items"] if m["id"] == self.welcome.id)
        self.assertEqual(row["read_by_ids"], [self.student_a.id])
        self.assertEqual(
            sorted(row["delivered_to_ids"]),
            sorted([self.student_a.id, self.student_b.id]),
        )
        # The ids must agree with the counts the ticks are drawn from.
        self.assertEqual(len(row["read_by_ids"]), row["read_count"])
        self.assertEqual(len(row["delivered_to_ids"]), row["delivered_count"])

    def test_list_reader_ids_empty_when_nobody_opened(self):
        resp = self.client_mentor.get(self._list_url())
        row = next(m for m in resp.data["items"] if m["id"] == self.welcome.id)
        self.assertEqual(row["read_by_ids"], [])
        self.assertEqual(row["delivered_to_ids"], [])

    def test_recipient_count_excludes_self_supervisor_and_blocked(self):
        # Mentor's view: 2 students + the invited student. Not the supervisor,
        # not the suspended account, not the mentor themselves.
        resp = self.client_mentor.get(self._list_url())
        self.assertEqual(resp.data["recipient_count"], 3)

    def test_recipient_count_is_per_caller(self):
        # Same size for both callers, so assert the actual membership rather
        # than a count that can't tell "excludes me" from "excludes anyone".
        recipients_for_mentor = set(
            chat_recipients_qs(self.group.id, exclude_user_id=self.mentor.id)
            .values_list("user_id", flat=True)
        )
        recipients_for_student = set(
            chat_recipients_qs(self.group.id, exclude_user_id=self.student_a.id)
            .values_list("user_id", flat=True)
        )
        self.assertEqual(
            recipients_for_mentor,
            {self.student_a.id, self.student_b.id, self.invited.id},
        )
        self.assertEqual(
            recipients_for_student,
            {self.mentor.id, self.student_b.id, self.invited.id},
        )
        self.assertEqual(self.client_a.get(self._list_url()).data["recipient_count"], 3)

    def test_recipient_count_drops_a_departed_member(self):
        membership = GroupMembership.objects.get(user=self.student_b, group=self.group)
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])
        resp = self.client_mentor.get(self._list_url())
        self.assertEqual(resp.data["recipient_count"], 2)
