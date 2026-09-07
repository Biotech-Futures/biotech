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

import threading

from apps.services.mailer import _EXECUTOR, send_async


def _drain():
    """Block until every queued send has run.

    ⚠️ Best effort, and known to be. The pool has four resident workers and a
    FIFO queue: these four no-ops only have to be *picked up* to finish, and
    three idle workers can pick all four up while the real task is still
    running. So this returns "probably drained", not "drained".

    It is kept for the tests that only need the pool to still be alive
    afterwards. Anything asserting that a callback RAN should wait on
    ``_wait_for`` instead — that one cannot pass early.
    """
    list(_EXECUTOR.map(lambda _: None, range(_EXECUTOR._max_workers)))


def _wait_for(event, seconds=5):
    """Wait for the worker to say it got there, rather than guessing.

    Ordering in a shared FIFO pool is not a synchronisation primitive. This
    test suite has already seen the difference: the callback assertion below
    failed once under load and passed 25 consecutive runs on an idle machine,
    which is the signature of a race that CI will hit and a laptop will not.
    """
    if not event.wait(seconds):
        raise AssertionError("the worker never got there")


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

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
    def test_sync_mode_swallows_a_send_failure_too(self):
        """"Never raises to the caller", on the inline path, with no callback.

        The docstring's promise was only ever tested through the pool, where
        the worker thread absorbs the exception whether or not _send catches
        it. Inline there is no worker: _send's own try/except is the whole
        promise, and deleting it turned every mail failure into a 500 on the
        request that triggered the mail — while this suite stayed green.
        """
        msg = MagicMock()
        msg.send.side_effect = RuntimeError("smtp down")

        send_async(msg, kind="login_code")  # must simply return

        msg.send.assert_called_once()

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


class SendAsyncFailureCallbackTest(SimpleTestCase):
    """The optional callback added for resolution emails.

    Marking a ticket resolved promises the requester was told. When the send
    fails that promise is not true, and the logs are not somewhere an agent
    looks. The callback is how the failure gets back in front of a person.
    """

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
    def test_a_failed_send_hands_the_error_to_the_callback(self):
        msg = MagicMock()
        msg.send.side_effect = RuntimeError("smtp down")
        seen = []

        send_async(msg, kind="ticket_resolved", on_failure=seen.append)

        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], RuntimeError)

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
    def test_a_successful_send_does_not_call_it(self):
        seen = []
        send_async(MagicMock(), kind="ticket_resolved", on_failure=seen.append)
        self.assertEqual(seen, [])

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=False)
    def test_the_callback_runs_on_the_pool_too(self):
        msg = MagicMock()
        msg.send.side_effect = RuntimeError("smtp down")
        seen = []
        ran = threading.Event()

        def record(exc):
            seen.append(exc)
            ran.set()

        send_async(msg, kind="ticket_resolved", on_failure=record)
        _wait_for(ran)

        self.assertEqual(len(seen), 1)

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=False)
    def test_a_callback_that_blows_up_does_not_take_the_pool_with_it(self):
        msg = MagicMock()
        msg.send.side_effect = RuntimeError("smtp down")

        def explode(_exc):
            raise ValueError("callback is broken")

        send_async(msg, kind="ticket_resolved", on_failure=explode)
        _drain()

        self.assertFalse(_EXECUTOR._shutdown)
        healthy = MagicMock()
        send_async(healthy, kind="login_code")
        _drain()
        healthy.send.assert_called_once()

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
    def test_a_broken_callback_does_not_escape_into_the_caller(self):
        """The mode where the guard around on_failure actually has a job.

        Run asynchronously, anything the callback raises lands on a Future
        nobody reads, so the test above passes with the guard deleted. Run
        synchronously there is a caller for it to escape into, and on the
        ticket path that caller has already committed a resolve.
        """
        msg = MagicMock()
        msg.send.side_effect = RuntimeError("smtp down")

        def explode(_exc):
            raise ValueError("callback is broken")

        send_async(msg, kind="ticket_resolved", on_failure=explode)



class RecipientNeverReachesTheLogTest(SimpleTestCase):
    """The address must not appear in any log line this module writes.

    Users of this platform are minors and this module carries their login
    codes and password resets, not just tickets. SMTP failures name the
    address they refused: ``SMTPRecipientsRefused`` puts it in ``args``, so
    anything that formats the exception — ``logger.exception``, ``%s`` on the
    exception object, ``repr`` — publishes it.

    Both log paths are pinned here because the second one was written after
    the first and did not inherit its reasoning: the callback-failure branch
    runs *inside* the ``except`` block for the send failure, so Python chains
    the two exceptions and ``logger.exception`` there prints the send failure's
    traceback under "During handling of the above exception". The guard on the
    first line kept the address out and the second line handed it back.
    """

    VICTIM = "minor.student@example.com"

    def refusing_message(self):
        from smtplib import SMTPRecipientsRefused

        msg = MagicMock()
        msg.send.side_effect = SMTPRecipientsRefused(
            {self.VICTIM: (550, b"mailbox unavailable")}
        )
        return msg

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
    def test_a_refused_send_does_not_log_the_address(self):
        with self.assertLogs("apps.services.mailer", level="ERROR") as captured:
            send_async(self.refusing_message(), kind="login_code")

        self.assertNotIn(self.VICTIM, "\n".join(captured.output))

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
    def test_a_refused_send_whose_callback_also_fails_does_not_log_it_either(self):
        """The chained case. This is the one that leaked.

        Reaching it needs both halves: the send is refused *and* the callback
        raises. The ticket callback does ORM work on the mail worker thread,
        so a database hiccup is enough.
        """
        def explode(_exc):
            raise RuntimeError("callback blew up")

        with self.assertLogs("apps.services.mailer", level="ERROR") as captured:
            send_async(
                self.refusing_message(), kind="ticket_resolved", on_failure=explode
            )

        joined = "\n".join(captured.output)
        self.assertNotIn(self.VICTIM, joined)
        # Still says enough to act on: which mail, and what broke on each side.
        self.assertIn("failure_callback_failed", joined)
        self.assertIn("RuntimeError", joined)
        self.assertIn("SMTPRecipientsRefused", joined)
