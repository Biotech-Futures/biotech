"""Off-request email dispatch for the auth flows.

A blocking SMTP round trip inside the login-code request is what makes users
believe the send failed (the SPA aborts at its own timeout) and click again.
Same shape as ``apps/chat/tasks.dispatch_og`` — no Celery, no extra service.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import connections

logger = logging.getLogger(__name__)

# A bounded pool, unlike the raw thread in chat/tasks.py: this runs on an
# unauthenticated endpoint, so thread-per-request would be an amplification
# primitive. Saturating the pool degrades to "mail is delayed", not "process
# out of threads".
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="auth-mail")


def send_async(msg, *, kind: str, on_failure=None) -> None:
    """Hand an already-built message to the pool. Never raises to the caller.

    The message must be fully rendered by the caller — the worker does no ORM
    work of its own, so it never opens a second DB connection that could not
    see the uncommitted row that triggered it.

    ``on_failure`` is optional and off by default; leaving it out is exactly
    the behaviour this function has always had. When given, it is called with
    the exception if the send fails, on whichever thread did the sending. It
    exists for the one case where "we tried to tell them" has to be visible
    to a human afterwards rather than only in the logs.

    A callback that touches the ORM will open a connection on the worker
    thread, which is why the async path closes them on the way out — nothing
    else ever will.
    """
    if getattr(settings, "AUTH_EMAIL_DISPATCH_SYNC", False):
        # Inline: the caller's request already owns this thread's connection,
        # so it is not ours to close.
        _send(msg, kind, on_failure)
        return

    try:
        _EXECUTOR.submit(_send_on_worker, msg, kind, on_failure)
    except RuntimeError:
        # submit() raises once the interpreter is shutting down (worker recycling).
        # Losing one email beats 500-ing a login request that already succeeded.
        logger.warning("auth_email.dispatch_unavailable kind=%s", kind)


def _send_on_worker(msg, kind: str, on_failure=None) -> None:
    try:
        _send(msg, kind, on_failure)
    finally:
        # Thread-local, so this only touches connections this worker opened.
        # A no-op unless a callback actually used the ORM.
        connections.close_all()


def _send(msg, kind: str, on_failure=None) -> None:
    started = time.perf_counter()
    try:
        msg.send()
    except Exception as exc:
        # Not logger.exception: SMTPRecipientsRefused and friends carry the
        # recipient address in their args, which would land raw in the log sink.
        logger.error(
            "auth_email.send_failed kind=%s error=%s", kind, type(exc).__name__,
        )
        if on_failure is not None:
            try:
                on_failure(exc)
            except Exception as callback_exc:
                # A broken callback must not be what takes the pool down.
                #
                # And not logger.exception here either, for exactly the reason
                # given four lines above. This runs inside the `except exc`
                # block, so Python chains the two: logger.exception prints the
                # callback's traceback *and* the "During handling of the above
                # exception" section, which is the send failure — the one
                # carrying the recipient address in its args. The guard above
                # kept that address out of the log and this line handed it
                # straight back. Both the callback's failure and the send's
                # failure are named by type only.
                logger.error(
                    "auth_email.failure_callback_failed kind=%s callback_error=%s "
                    "send_error=%s",
                    kind,
                    type(callback_exc).__name__,
                    type(exc).__name__,
                )
        return

    logger.info(
        "auth_email.sent kind=%s duration_ms=%.1f",
        kind,
        (time.perf_counter() - started) * 1000,
    )
