"""
Tests for off-request auth email dispatch.

Every other settings module forces AUTH_EMAIL_DISPATCH_SYNC=True, so without
these the production (threaded) path would ship completely unexercised.

Run with:
    python manage.py test tests.apps.services.test_mailer \
        --settings=config.settings_test
"""

from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from apps.services.mailer import _EXECUTOR, send_async


def _drain():
    """Block until every queued send has run."""
    list(_EXECUTOR.map(lambda _: None, range(_EXECUTOR._max_workers)))


class SendAsyncTest(SimpleTestCase):

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
    def test_sync_mode_sends_inline(self):
        msg = MagicMock()
        send_async(msg, kind="login_code")
        msg.send.assert_called_once()

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=False)
    def test_async_mode_sends_on_the_pool(self):
        msg = MagicMock()
        send_async(msg, kind="login_code")
        _drain()
        msg.send.assert_called_once()

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=False)
    def test_send_failure_never_reaches_the_caller(self):
        # A dead relay must not 500 the login request or kill the pool.
        msg = MagicMock()
        msg.send.side_effect = RuntimeError("smtp down")

        send_async(msg, kind="login_code")
        _drain()

        self.assertFalse(_EXECUTOR._shutdown)
        healthy = MagicMock()
        send_async(healthy, kind="login_code")
        _drain()
        healthy.send.assert_called_once()

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=False)
    def test_dispatch_is_bounded_under_burst(self):
        # The endpoint is unauthenticated, so thread-per-request would be an
        # amplification primitive; excess sends must queue, not spawn.
        messages = [MagicMock() for _ in range(40)]
        for msg in messages:
            send_async(msg, kind="login_code")
        _drain()

        self.assertLessEqual(len(_EXECUTOR._threads), _EXECUTOR._max_workers)
        for msg in messages:
            msg.send.assert_called_once()
