import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.chat.models import ChatDigestState, MessageStatus, Messages
from apps.chat.services import digest as digest_service
from apps.chat.services.digest import send_unread_message_digests
from apps.groups.models import GroupMembership, Groups

User = get_user_model()
Role = GroupMembership.MembershipRoleChoices
READ = MessageStatus.StatusChoices.READ
DELIVERED = MessageStatus.StatusChoices.DELIVERED


# locmem so no SMTP is attempted; explicit EMAIL_CONNECT_* so the second-mailbox
# wiring is what the assertions check, not the primary account defaults.
DIGEST_SETTINGS = dict(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_CONNECT_HOST="smtp.connect.test",
    EMAIL_CONNECT_PORT=465,
    EMAIL_CONNECT_USE_SSL=True,
    EMAIL_CONNECT_HOST_USER="global@biotechfutures.org",
    EMAIL_CONNECT_HOST_PASSWORD="pw",
    CONNECT_FROM_ADDRESS="connect@biotechfutures.org",
    CONNECT_DEFAULT_FROM_EMAIL="BIOTech Connect <connect@biotechfutures.org>",
    UNREAD_DIGEST_TOKEN="secret-token",
    UNREAD_DIGEST_MIN_INTERVAL_HOURS=24,
    UNREAD_DIGEST_DISPATCH_SYNC=True,
    # start == end disables quiet hours so these tests never depend on the
    # wall-clock time they happen to run at.
    UNREAD_DIGEST_QUIET_START_HOUR=0,
    UNREAD_DIGEST_QUIET_END_HOUR=0,
    FRONTEND_BASE_URL="https://mentoring.biotechfutures.org",
)


@override_settings(**DIGEST_SETTINGS)
class UnreadDigestServiceTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@t.com", password="pw", first_name="Alice", last_name="A"
        )
        self.bob = User.objects.create_user(
            email="bob@t.com", password="pw", first_name="Bob", last_name="B"
        )
        self.group = Groups.objects.create(group_name="BTF1")
        GroupMembership.objects.create(
            user=self.alice, group=self.group, membership_role=Role.MENTOR
        )
        GroupMembership.objects.create(
            user=self.bob, group=self.group, membership_role=Role.STUDENT
        )

    # -- helpers ---------------------------------------------------------

    def _msg(self, sender, group=None, text="hi", sent_at=None):
        m = Messages.objects.create(
            group=group or self.group, sender_user=sender, message_text=text
        )
        if sent_at is not None:
            Messages.objects.filter(pk=m.pk).update(sent_at=sent_at)
            m.refresh_from_db()
        return m

    def _recipients(self):
        return sorted(box.to[0] for box in mail.outbox)

    def _age_out(self, user):
        """Push a user's last-notified past the cadence window (simulate a day)."""
        ChatDigestState.objects.filter(user=user).update(
            last_notified_at=timezone.now() - timedelta(hours=25)
        )

    # -- unread detection ------------------------------------------------

    def test_message_with_no_status_row_is_unread(self):
        # The lazy-status crux: Bob never opened the app, so there is no
        # MessageStatus row at all — must still count as unread.
        self._msg(self.alice)
        considered, sent, failed = send_unread_message_digests()
        self.assertEqual((considered, sent, failed), (1, 1, 0))
        self.assertEqual(self._recipients(), ["bob@t.com"])

    def test_delivered_but_not_read_is_unread(self):
        m = self._msg(self.alice)
        MessageStatus.objects.create(
            message=m, user=self.bob, status=DELIVERED, delivered_at=timezone.now()
        )
        _, sent, _ = send_unread_message_digests()
        self.assertEqual(sent, 1)
        self.assertEqual(self._recipients(), ["bob@t.com"])

    def test_read_message_excluded(self):
        m = self._msg(self.alice)
        MessageStatus.objects.create(
            message=m, user=self.bob, status=READ,
            delivered_at=timezone.now(), read_at=timezone.now(),
        )
        considered, sent, _ = send_unread_message_digests()
        self.assertEqual((considered, sent), (0, 0))
        self.assertEqual(mail.outbox, [])

    def test_own_messages_excluded(self):
        # Only Bob sends -> Alice has 1 unread, Bob has 0 (his own).
        self._msg(self.bob)
        _, sent, _ = send_unread_message_digests()
        self.assertEqual(self._recipients(), ["alice@t.com"])
        self.assertEqual(sent, 1)

    def test_soft_deleted_excluded(self):
        m = self._msg(self.alice)
        m.soft_delete()
        considered, sent, _ = send_unread_message_digests()
        self.assertEqual((considered, sent), (0, 0))

    def test_messages_before_join_excluded(self):
        # A message that predates Bob's membership must not count.
        self._msg(self.alice, sent_at=timezone.now() - timedelta(hours=2))
        considered, sent, _ = send_unread_message_digests()
        self.assertEqual((considered, sent), (0, 0))

    # -- membership filters ---------------------------------------------

    def test_supervisor_not_notified(self):
        carol = User.objects.create_user(
            email="carol@t.com", password="pw", first_name="Carol", last_name="C"
        )
        GroupMembership.objects.create(
            user=carol, group=self.group, membership_role=Role.SUPERVISOR
        )
        self._msg(self.alice)  # unread for both Bob (student) and Carol (supervisor)
        send_unread_message_digests()
        self.assertEqual(self._recipients(), ["bob@t.com"])  # Carol excluded

    def test_login_blocked_user_excluded(self):
        self.bob.account_status = User.AccountStatus.DEACTIVATED
        self.bob.save(update_fields=["account_status"])
        self._msg(self.alice)
        considered, sent, _ = send_unread_message_digests()
        self.assertEqual((considered, sent), (0, 0))

    def test_left_member_excluded(self):
        GroupMembership.objects.filter(user=self.bob, group=self.group).update(
            left_at=timezone.now()
        )
        self._msg(self.alice)
        considered, sent, _ = send_unread_message_digests()
        self.assertEqual((considered, sent), (0, 0))

    # -- aggregation -----------------------------------------------------

    def test_aggregates_across_groups(self):
        group2 = Groups.objects.create(group_name="BTF2")
        GroupMembership.objects.create(
            user=self.alice, group=group2, membership_role=Role.MENTOR
        )
        GroupMembership.objects.create(
            user=self.bob, group=group2, membership_role=Role.STUDENT
        )
        self._msg(self.alice)                 # BTF1: 1
        self._msg(self.alice)                 # BTF1: 2
        self._msg(self.alice, group=group2)   # BTF2: 1
        send_unread_message_digests()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, "You have 3 unread messages on BIOTech Connect")
        self.assertIn("BTF1", msg.body)
        self.assertIn("BTF2", msg.body)

    def test_subject_singular_for_one(self):
        self._msg(self.alice)
        send_unread_message_digests()
        self.assertEqual(
            mail.outbox[0].subject, "You have 1 unread message on BIOTech Connect"
        )

    # -- second mailbox --------------------------------------------------

    def test_sends_from_connect_mailbox(self):
        self._msg(self.alice)
        send_unread_message_digests()
        self.assertEqual(
            mail.outbox[0].from_email, "BIOTech Connect <connect@biotechfutures.org>"
        )
        self.assertNotEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)

    @patch("apps.chat.services.digest.get_connection")
    def test_opens_the_connect_smtp_connection(self, mock_get_conn):
        conn = MagicMock()
        conn.connection = None
        mock_get_conn.return_value = conn
        self._msg(self.alice)
        send_unread_message_digests()
        mock_get_conn.assert_called_once()
        kwargs = mock_get_conn.call_args.kwargs
        self.assertEqual(kwargs["host"], "smtp.connect.test")
        self.assertEqual(kwargs["port"], 465)
        self.assertEqual(kwargs["username"], "global@biotechfutures.org")
        self.assertTrue(kwargs["use_ssl"])

    # -- throttle / re-arm ----------------------------------------------

    def test_second_run_same_day_sends_nothing(self):
        self._msg(self.alice)
        _, first, _ = send_unread_message_digests()
        _, second, _ = send_unread_message_digests()
        self.assertEqual((first, second), (1, 0))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(ChatDigestState.objects.filter(user=self.bob).count(), 1)

    def test_high_water_mark_advances_and_blocks_stale_unread(self):
        m1 = self._msg(self.alice)
        send_unread_message_digests()
        state = ChatDigestState.objects.get(user=self.bob)
        self.assertEqual(state.last_notified_message_id, m1.id)
        # A new day, but no new messages -> still nothing above the mark.
        self._age_out(self.bob)
        _, sent, _ = send_unread_message_digests()
        self.assertEqual(sent, 0)

    def test_rearm_on_genuinely_new_message(self):
        m1 = self._msg(self.alice)
        send_unread_message_digests()
        self._age_out(self.bob)
        m2 = self._msg(self.alice)  # id > high-water mark
        _, sent, _ = send_unread_message_digests()
        self.assertEqual(sent, 1)
        state = ChatDigestState.objects.get(user=self.bob)
        self.assertEqual(state.last_notified_message_id, m2.id)

    def test_20h_later_still_blocked_by_24h_interval(self):
        # The old 20h gate under a 15-min cron walked sends 4h earlier per day.
        self._msg(self.alice)
        send_unread_message_digests()
        ChatDigestState.objects.filter(user=self.bob).update(
            last_notified_at=timezone.now() - timedelta(hours=21)
        )
        self._msg(self.alice)  # genuinely new, but inside the 24h window
        _, sent, _ = send_unread_message_digests()
        self.assertEqual(sent, 0)

    def test_read_clears_new_message(self):
        m1 = self._msg(self.alice)
        send_unread_message_digests()          # hwm = m1.id
        self._age_out(self.bob)
        m2 = self._msg(self.alice)             # above hwm, but Bob reads it
        MessageStatus.objects.create(
            message=m2, user=self.bob, status=READ,
            delivered_at=timezone.now(), read_at=timezone.now(),
        )
        _, sent, _ = send_unread_message_digests()
        self.assertEqual(sent, 0)

    # -- prefilter / high-water-mark advance -----------------------------

    def test_all_read_scan_advances_mark_without_consuming_cadence(self):
        m1 = self._msg(self.alice)
        MessageStatus.objects.create(
            message=m1, user=self.bob, status=READ,
            delivered_at=timezone.now(), read_at=timezone.now(),
        )
        _, sent, _ = send_unread_message_digests()
        self.assertEqual(sent, 0)
        state = ChatDigestState.objects.get(user=self.bob)
        self.assertEqual(state.last_notified_message_id, m1.id)
        self.assertIsNone(state.last_notified_at)  # cadence untouched
        # A genuinely new message must email immediately, not wait 24h.
        self._msg(self.alice)
        _, sent, _ = send_unread_message_digests()
        self.assertEqual(sent, 1)
        self.assertEqual(self._recipients(), ["bob@t.com"])

    def test_prefilter_skips_users_with_nothing_new(self):
        self._msg(self.alice)
        send_unread_message_digests()  # bob emailed; alice's mark advanced
        self._age_out(self.bob)
        with patch.object(
            digest_service, "_compute_unread", wraps=digest_service._compute_unread
        ) as spy:
            _, sent, _ = send_unread_message_digests()
        self.assertEqual(sent, 0)
        spy.assert_not_called()  # zero per-user queries on a quiet run

    # -- dry run ---------------------------------------------------------

    def test_dry_run_sends_nothing_and_writes_no_state(self):
        self._msg(self.alice)
        considered, sent, failed = send_unread_message_digests(dry_run=True)
        self.assertEqual((considered, sent, failed), (1, 0, 0))
        self.assertEqual(mail.outbox, [])
        self.assertEqual(ChatDigestState.objects.count(), 0)


@override_settings(**DIGEST_SETTINGS)
class UnreadDigestTriggerViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("send-unread-digest")

    def test_503_when_token_unset(self):
        with override_settings(UNREAD_DIGEST_TOKEN=""):
            resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 503)

    def test_401_on_bad_token(self):
        resp = self.client.post(self.url, HTTP_X_DIGEST_TOKEN="wrong")
        self.assertEqual(resp.status_code, 401)

    def test_202_on_valid_token(self):
        resp = self.client.post(self.url, HTTP_X_DIGEST_TOKEN="secret-token")
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data["status"], "started")

    def test_valid_trigger_sends_digest(self):
        # End-to-end through the view (sync dispatch): unread message -> email.
        alice = User.objects.create_user(
            email="alice@t.com", password="pw", first_name="Alice", last_name="A"
        )
        bob = User.objects.create_user(
            email="bob@t.com", password="pw", first_name="Bob", last_name="B"
        )
        group = Groups.objects.create(group_name="BTF1")
        GroupMembership.objects.create(
            user=alice, group=group, membership_role=Role.MENTOR
        )
        GroupMembership.objects.create(
            user=bob, group=group, membership_role=Role.STUDENT
        )
        Messages.objects.create(group=group, sender_user=alice, message_text="hi")

        resp = self.client.post(self.url, HTTP_X_DIGEST_TOKEN="secret-token")
        self.assertEqual(resp.status_code, 202)
        self.assertEqual([box.to[0] for box in mail.outbox], ["bob@t.com"])

    def test_202_already_running_when_lock_held(self):
        # Hold the dispatch lock so the async path reports the in-flight run
        # without spawning a second thread.
        self.assertTrue(digest_service._dispatch_lock.acquire(blocking=False))
        try:
            with override_settings(UNREAD_DIGEST_DISPATCH_SYNC=False):
                resp = self.client.post(self.url, HTTP_X_DIGEST_TOKEN="secret-token")
        finally:
            digest_service._dispatch_lock.release()
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data["status"], "already_running")


@override_settings(**DIGEST_SETTINGS)
class UnreadDigestQuietHoursTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            email="alice@t.com", password="pw", first_name="Alice", last_name="A"
        )
        self.bob = User.objects.create_user(
            email="bob@t.com", password="pw", first_name="Bob", last_name="B"
        )
        group = Groups.objects.create(group_name="BTF1")
        GroupMembership.objects.create(
            user=self.alice, group=group, membership_role=Role.MENTOR
        )
        GroupMembership.objects.create(
            user=self.bob, group=group, membership_role=Role.STUDENT
        )
        Messages.objects.create(group=group, sender_user=self.alice, message_text="hi")

    @staticmethod
    def _quiet_now():
        # A 2h UTC window straddling "now", so the run is mid-quiet whenever
        # the test executes.
        hour = timezone.now().astimezone(ZoneInfo("UTC")).hour
        return dict(
            UNREAD_DIGEST_QUIET_START_HOUR=hour,
            UNREAD_DIGEST_QUIET_END_HOUR=(hour + 2) % 24,
            UNREAD_DIGEST_QUIET_TZ="UTC",
        )

    def test_quiet_hours_hold_all_sends(self):
        with override_settings(**self._quiet_now()):
            considered, sent, failed = send_unread_message_digests()
        self.assertEqual((considered, sent, failed), (0, 0, 0))
        self.assertEqual(mail.outbox, [])
        self.assertEqual(ChatDigestState.objects.count(), 0)  # no state touched

    def test_dry_run_still_reports_during_quiet_hours(self):
        with override_settings(**self._quiet_now()):
            considered, _, _ = send_unread_message_digests(dry_run=True)
        self.assertEqual(considered, 1)

    def test_send_resumes_outside_the_window(self):
        # Same fixtures, quiet window disabled (class default) -> bob emailed.
        _, sent, _ = send_unread_message_digests()
        self.assertEqual(sent, 1)

    def test_window_math(self):
        sydney = ZoneInfo("Australia/Sydney")
        wrap = dict(
            UNREAD_DIGEST_QUIET_START_HOUR=22,
            UNREAD_DIGEST_QUIET_END_HOUR=7,
            UNREAD_DIGEST_QUIET_TZ="Australia/Sydney",
        )
        with override_settings(**wrap):
            self.assertTrue(
                digest_service._in_quiet_hours(
                    datetime(2026, 8, 3, 23, 30, tzinfo=sydney)
                )
            )
            self.assertTrue(
                digest_service._in_quiet_hours(
                    datetime(2026, 8, 3, 6, 59, tzinfo=sydney)
                )
            )
            self.assertFalse(
                digest_service._in_quiet_hours(
                    datetime(2026, 8, 3, 7, 0, tzinfo=sydney)
                )
            )
            self.assertFalse(
                digest_service._in_quiet_hours(
                    datetime(2026, 8, 3, 12, 0, tzinfo=sydney)
                )
            )
            # TZ conversion: 13:00 UTC == 23:00 AEST (winter, +10) -> quiet.
            self.assertTrue(
                digest_service._in_quiet_hours(
                    datetime(2026, 8, 3, 13, 0, tzinfo=ZoneInfo("UTC"))
                )
            )

    def test_start_equals_end_disables_window(self):
        with override_settings(
            UNREAD_DIGEST_QUIET_START_HOUR=5, UNREAD_DIGEST_QUIET_END_HOUR=5
        ):
            self.assertFalse(
                digest_service._in_quiet_hours(
                    datetime(2026, 8, 3, 5, 0, tzinfo=ZoneInfo("UTC"))
                )
            )


class UnreadDigestDispatchTests(TestCase):
    """Lock hygiene on the real thread path, which every other class bypasses
    via UNREAD_DIGEST_DISPATCH_SYNC. The digest itself is stubbed: what's
    under test is that the lock frees again whatever the run does."""

    def _dispatch_and_await(self, digest_stub):
        ran = threading.Event()

        def tracked():
            try:
                return digest_stub()
            finally:
                ran.set()

        with override_settings(UNREAD_DIGEST_DISPATCH_SYNC=False), patch.object(
            digest_service, "send_unread_message_digests", side_effect=tracked
        ):
            self.assertEqual(digest_service.dispatch_unread_digest(), "started")
            self.assertTrue(ran.wait(5), "digest thread never ran")
        # Release happens just after the stub returns; poll-acquire to sync.
        self.assertTrue(
            digest_service._dispatch_lock.acquire(timeout=5),
            "dispatch lock leaked",
        )
        digest_service._dispatch_lock.release()

    def test_lock_released_after_successful_run(self):
        self._dispatch_and_await(lambda: (0, 0, 0))

    def test_lock_released_after_crashed_run(self):
        def boom():
            raise RuntimeError("boom")

        self._dispatch_and_await(boom)
