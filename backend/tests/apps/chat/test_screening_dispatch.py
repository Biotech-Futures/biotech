import threading
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from apps.chat.models import MessageScreening, Messages
from apps.chat.services.screening import (
    _run_ai_screening_in_thread,
    dispatch_suspicious_message_screening,
    schedule_message_screening,
)
from apps.groups.models import Groups

TARGET = "apps.chat.services.screening"


class FreshLockMixin:
    """Give each test its own lock so a held lock never leaks between tests."""

    def _use_fresh_lock(self):
        self.lock = threading.Lock()
        patcher = patch(f"{TARGET}._ai_dispatch_lock", self.lock)
        patcher.start()
        self.addCleanup(patcher.stop)


class DispatchTests(FreshLockMixin, SimpleTestCase):
    def setUp(self):
        self._use_fresh_lock()

    def test_returns_already_running_when_a_batch_holds_the_lock(self):
        self.lock.acquire()

        with patch(f"{TARGET}.process_suspicious_messages") as process:
            result = dispatch_suspicious_message_screening()

        self.assertEqual(result, "already_running")
        process.assert_not_called()
        self.assertTrue(self.lock.locked())

    @override_settings(AI_SCREENING_DISPATCH_SYNC=True)
    def test_sync_mode_runs_the_batch_inline_and_releases_the_lock(self):
        with patch(f"{TARGET}.process_suspicious_messages") as process:
            result = dispatch_suspicious_message_screening()

        self.assertEqual(result, "completed")
        process.assert_called_once_with()
        self.assertFalse(self.lock.locked())

    @override_settings(AI_SCREENING_DISPATCH_SYNC=True)
    def test_sync_mode_releases_the_lock_even_when_the_batch_crashes(self):
        with patch(
            f"{TARGET}.process_suspicious_messages",
            side_effect=RuntimeError("batch crashed"),
        ):
            with self.assertRaises(RuntimeError):
                dispatch_suspicious_message_screening()

        self.assertFalse(self.lock.locked())

    @override_settings(AI_SCREENING_DISPATCH_SYNC=False)
    def test_async_mode_starts_a_daemon_worker_and_keeps_the_lock(self):
        with patch(f"{TARGET}.threading") as fake_threading:
            result = dispatch_suspicious_message_screening()

        self.assertEqual(result, "started")
        fake_threading.Thread.assert_called_once_with(
            target=_run_ai_screening_in_thread,
            name="ai-message-screening",
            daemon=True,
        )
        fake_threading.Thread.return_value.start.assert_called_once_with()
        # The worker releases the lock when it finishes, not the dispatcher.
        self.assertTrue(self.lock.locked())


class WorkerTests(FreshLockMixin, SimpleTestCase):
    def setUp(self):
        self._use_fresh_lock()
        # The dispatcher takes the lock before starting the worker.
        self.lock.acquire()

    @patch(f"{TARGET}.connections")
    @patch(
        f"{TARGET}.process_suspicious_messages",
        return_value={"considered": 0, "safe": 0, "flagged": 0, "failed": 0},
    )
    def test_worker_runs_the_batch_closes_connections_and_releases_the_lock(
        self, process, connections
    ):
        _run_ai_screening_in_thread()

        process.assert_called_once_with()
        connections.close_all.assert_called_once_with()
        self.assertFalse(self.lock.locked())

    @patch(f"{TARGET}.connections")
    @patch(
        f"{TARGET}.process_suspicious_messages",
        side_effect=RuntimeError("batch crashed"),
    )
    def test_worker_survives_a_crash_and_still_releases_the_lock(
        self, process, connections
    ):
        _run_ai_screening_in_thread()

        connections.close_all.assert_called_once_with()
        self.assertFalse(self.lock.locked())


class ScheduleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="schedule-user@test.com",
            password="pw",
            first_name="Schedule",
            last_name="User",
        )
        self.group = Groups.objects.create(group_name="Schedule Group")

    def _message(self, text):
        return Messages.objects.create(
            group=self.group,
            sender_user=self.user,
            message_text=text,
        )

    @override_settings(OPENAI_API_KEY="test-key")
    @patch(f"{TARGET}.dispatch_suspicious_message_screening")
    def test_queues_the_message_then_triggers_a_batch_when_a_key_is_set(self, dispatch):
        message = self._message("Hello team.")

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            schedule_message_screening(message)

        self.assertEqual(len(callbacks), 1)
        self.assertEqual(MessageScreening.objects.filter(message=message).count(), 1)
        dispatch.assert_called_once_with()

    @override_settings(OPENAI_API_KEY="")
    @patch(f"{TARGET}.dispatch_suspicious_message_screening")
    def test_queues_the_message_but_does_not_trigger_a_batch_without_a_key(self, dispatch):
        message = self._message("Hello team.")

        with self.captureOnCommitCallbacks(execute=True):
            schedule_message_screening(message)

        self.assertEqual(MessageScreening.objects.filter(message=message).count(), 1)
        dispatch.assert_not_called()

    @override_settings(OPENAI_API_KEY="test-key")
    @patch(f"{TARGET}.dispatch_suspicious_message_screening")
    def test_a_message_that_needs_no_screening_triggers_nothing(self, dispatch):
        message = self._message("   ")

        with self.captureOnCommitCallbacks(execute=True):
            schedule_message_screening(message)

        self.assertEqual(MessageScreening.objects.count(), 0)
        dispatch.assert_not_called()

    @override_settings(OPENAI_API_KEY="test-key")
    @patch(f"{TARGET}.dispatch_suspicious_message_screening")
    def test_a_message_removed_before_commit_is_skipped_without_error(self, dispatch):
        message = self._message("Hello team.")

        with self.captureOnCommitCallbacks(execute=True):
            schedule_message_screening(message)
            Messages.objects.filter(pk=message.pk).delete()

        self.assertEqual(MessageScreening.objects.count(), 0)
        dispatch.assert_not_called()
