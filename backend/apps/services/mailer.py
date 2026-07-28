"""Off-request email dispatch for the auth flows.

A blocking SMTP round trip inside the login-code request is what makes users
believe the send failed (the SPA aborts at its own timeout) and click again.
Same shape as ``apps/chat/tasks.dispatch_og`` — no Celery, no extra service.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings

logger = logging.getLogger(__name__)

# A bounded pool, unlike the raw thread in chat/tasks.py: this runs on an
# unauthenticated endpoint, so thread-per-request would be an amplification
# primitive. Saturating the pool degrades to "mail is delayed", not "process
# out of threads".
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="auth-mail")


def send_async(msg, *, kind: str) -> None:
    """Hand an already-built message to the pool. Never raises to the caller.

    The message must be fully rendered by the caller — the worker does no ORM
    work, so it never opens a second DB connection that could not see the
    uncommitted row that triggered it.
    """
    if getattr(settings, "AUTH_EMAIL_DISPATCH_SYNC", False):
        _send(msg, kind)
        return

    try:
        _EXECUTOR.submit(_send, msg, kind)
    except RuntimeError:
        # submit() raises once the interpreter is shutting down (worker recycling).
        # Losing one email beats 500-ing a login request that already succeeded.
        logger.warning("auth_email.dispatch_unavailable kind=%s", kind)


def _send(msg, kind: str) -> None:
    started = time.perf_counter()
    try:
        msg.send()
    except Exception as exc:
        # Not logger.exception: SMTPRecipientsRefused and friends carry the
        # recipient address in their args, which would land raw in the log sink.
        logger.error(
            "auth_email.send_failed kind=%s error=%s", kind, type(exc).__name__,
        )
        return

    logger.info(
        "auth_email.sent kind=%s duration_ms=%.1f",
        kind,
        (time.perf_counter() - started) * 1000,
    )
