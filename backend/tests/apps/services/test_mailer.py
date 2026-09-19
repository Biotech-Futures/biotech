"""
Tests for off-request auth email dispatch.

Every other settings module forces AUTH_EMAIL_DISPATCH_SYNC=True, so without
these the production (threaded) path would ship completely unexercised.

Run with:
    python manage.py test tests.apps.services.test_mailer \
        --settings=config.settings_test
"""

import concurrent.futures as futures
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.services.mailer import _EXECUTOR, send_async


@contextmanager
def _dispatched():
    """Wait for the sends made inside the block to actually finish.

    The obvious barrier — submitting one no-op per worker and waiting on those
    — looks right and is not. The queue is FIFO, so work submitted earlier is
    *dequeued* first, but with several workers running at once it need not have
    *finished* first: three workers can chew through four no-ops while a fourth
    is still inside the send that was queued ahead of them. The wait then
    returns early and the assertion runs against a message that has not been
    sent yet.

    That race is invisible when these tests run alone, because a MagicMock send
    returns immediately. It surfaces once the pool is busy — and the pool is
    module-level, shared by the whole test process, so every other test that
    sends a confirmation email is queued on it. The result was a suite that
    failed roughly one run in five, always here.

    Waiting on the futures themselves removes the guesswork: these are the exact
    tasks this block created, so there is nothing to infer.
    """
    pending: list[futures.Future] = []
    original = _EXECUTOR.submit

    def recording(fn, *args, **kwargs):
        future = original(fn, *args, **kwargs)
        pending.append(future)
        return future

    with patch.object(_EXECUTOR, "submit", recording):
        yield pending

    _, unfinished = futures.wait(pending, timeout=10)
    if unfinished:
        raise AssertionError(
            f"{len(unfinished)} queued send(s) had not finished after 10s"
        )


class SendAsyncTest(SimpleTestCase):

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
    def test_sync_mode_sends_inline(self):
        msg = MagicMock()
        send_async(msg, kind="login_code")
        msg.send.assert_called_once()

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=False)
    def test_async_mode_sends_on_the_pool(self):
        msg = MagicMock()

        with _dispatched():
            send_async(msg, kind="login_code")

        msg.send.assert_called_once()

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=False)
    def test_send_failure_never_reaches_the_caller(self):
        # A dead relay must not 500 the login request or kill the pool.
        msg = MagicMock()
        msg.send.side_effect = RuntimeError("smtp down")

        with _dispatched():
            send_async(msg, kind="login_code")

        self.assertFalse(_EXECUTOR._shutdown)
        healthy = MagicMock()

        with _dispatched():
            send_async(healthy, kind="login_code")

        healthy.send.assert_called_once()

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=False)
    def test_dispatch_is_bounded_under_burst(self):
        # The endpoint is unauthenticated, so thread-per-request would be an
        # amplification primitive; excess sends must queue, not spawn.
        messages = [MagicMock() for _ in range(40)]

        with _dispatched():
            for msg in messages:
                send_async(msg, kind="login_code")

        self.assertLessEqual(len(_EXECUTOR._threads), _EXECUTOR._max_workers)
        for msg in messages:
            msg.send.assert_called_once()
