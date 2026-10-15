"""Checking that email addresses exist, with QuickEmailVerification (QEV).

Public surface:

- ``verify_after_commit(emails)``: schedules a check of ``emails`` once the
  current transaction commits, on a background worker. Nothing runs if it
  rolls back. Registration calls this (in a later change); it never makes a
  network call itself, inside its transaction or its serializer.
- ``verify_emails(emails)`` / ``verify_email(email)``: the check itself, run
  by that worker. Blank and repeated addresses are dropped, a malformed one is
  invalid without a lookup, and a recent valid or invalid answer on file is
  reused instead of paid for again. Each answer from QEV is stored
  (``EmailVerification``); that row is what later flags an address.

Nothing here blocks anything: it only reports. Only ``invalid`` is a failed
check; ``unknown`` (QEV's unknown, or a domain that accepts every address) and
``error`` pass. ``error`` means no answer was had: no API key, a timeout, an
outage, a refused or malformed response, or the daily lookup cap reached. It
is logged and never stored, so the address is checked again next time.

The API key is sent as a query parameter, so request URLs and the text of
``requests`` exceptions (which include the URL) are never logged. Addresses
are logged as ``email_log_tag`` hashes.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Iterable, Optional

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError, connections, transaction
from django.db.models import F
from django.utils import timezone

from apps.common.pii import email_log_tag

from .models import EmailVerification, EmailVerificationCredits

logger = logging.getLogger(__name__)

VERIFY_URL = "https://api.quickemailverification.com/v1/verify"
# Free; answers by the test address used (e.g. rejected-email@example.com).
SANDBOX_URL = "https://api.quickemailverification.com/v1/verify/sandbox"

VALID = EmailVerification.Status.VALID.value
INVALID = EmailVerification.Status.INVALID.value
UNKNOWN = EmailVerification.Status.UNKNOWN.value
ERROR = "error"

# One worker: batches are checked one after another, so a public endpoint can't
# start threads without bound, and one process never pays twice for an address
# two batches share.
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="email-verify")


@dataclass(frozen=True)
class VerificationResult:
    email: str
    status: str
    # QEV's reason for an answer, or why there was none (e.g. "http_429").
    reason: str = ""
    did_you_mean: str = ""
    # True when reused from an earlier answer instead of looked up now.
    cached: bool = False

    @property
    def passed(self) -> bool:
        return self.status != INVALID


def _api_key() -> str:
    return getattr(settings, "QEV_API_KEY", "") or ""


def _sandbox() -> bool:
    return bool(getattr(settings, "QEV_USE_SANDBOX", False))


def _true(value) -> bool:
    # QEV sends its flags as the strings "true" and "false".
    return value is True or str(value).strip().lower() == "true"


def _said(value) -> Optional[bool]:
    return None if value in (None, "") else _true(value)


def _status(data: dict) -> Optional[str]:
    result = str(data.get("result") or "").strip().lower()
    if result == "valid":
        # A domain that accepts every address can't say whether this one exists.
        return UNKNOWN if _true(data.get("accept_all")) else VALID
    if result in (INVALID, UNKNOWN):
        return result
    return None


def _failed(email: str, reason: str, exc: Optional[BaseException] = None) -> VerificationResult:
    # Only the exception's type: its text can carry the request URL, and so the key.
    logger.warning(
        "email_verification.lookup_failed email=%s reason=%s error=%s",
        email_log_tag(email), reason, type(exc).__name__ if exc else "",
    )
    return VerificationResult(email, ERROR, reason)


def _lookup(email: str) -> tuple[VerificationResult, Optional[dict]]:
    """Ask QEV about one address: the result, and QEV's answer when there was
    one to store. Never raises."""
    try:
        response = requests.get(
            SANDBOX_URL if _sandbox() else VERIFY_URL,
            params={"apikey": _api_key(), "email": email},
            timeout=float(getattr(settings, "QEV_TIMEOUT_SECONDS", 5)),
        )
    except requests.Timeout as exc:
        return _failed(email, "request_timeout", exc), None
    except requests.RequestException as exc:
        return _failed(email, "connection_error", exc), None
    except Exception as exc:  # noqa: BLE001 - an outage must never stop a registration
        return _failed(email, "request_failed", exc), None

    if response.status_code != 200:
        return _failed(email, f"http_{response.status_code}"), None
    try:
        data = response.json()
    except ValueError as exc:
        return _failed(email, "bad_response", exc), None
    if not isinstance(data, dict):
        return _failed(email, "bad_response"), None
    if not _true(data.get("success")):
        # e.g. out of credit. Its message isn't logged: it's QEV's own text.
        return _failed(email, "service_refused"), None
    status = _status(data)
    if status is None:
        return _failed(email, "bad_response"), None

    result = VerificationResult(
        email, status,
        reason=str(data.get("reason") or "")[:32],
        did_you_mean=str(data.get("did_you_mean") or "")[:254],
    )
    logger.info(
        "email_verification.checked email=%s status=%s reason=%s",
        email_log_tag(email), result.status, result.reason,
    )
    return result, data


def _reserve_lookup() -> bool:
    """Count one paid lookup against today's cap (QEV_DAILY_LOOKUP_CAP), if
    there's room. Sandbox lookups are free, so they aren't counted. False when
    the cap is reached or the count can't be kept."""
    if _sandbox():
        return True
    cap = int(getattr(settings, "QEV_DAILY_LOOKUP_CAP", 600))
    today = timezone.now().date()
    try:
        with transaction.atomic():
            EmailVerificationCredits.get()
            rows = EmailVerificationCredits.objects.filter(pk=EmailVerificationCredits.SINGLETON_PK)
            rows.exclude(lookups_on=today).update(lookups_on=today, lookups_today=0)
            # One conditional update, so two workers can't both take the last slot.
            return bool(
                rows.filter(lookups_on=today, lookups_today__lt=cap)
                .update(lookups_today=F("lookups_today") + 1)
            )
    except DatabaseError as exc:
        # Without the count the cap can't be kept, so no paid lookup is made.
        logger.error("email_verification.cap_check_failed error=%s", type(exc).__name__)
        return False


def _stored_answers(addresses: list[str]) -> dict:
    try:
        return EmailVerification.reusable(
            addresses, max_age_days=int(getattr(settings, "QEV_RESULT_MAX_AGE_DAYS", 180)),
        )
    except DatabaseError as exc:
        logger.error("email_verification.cache_read_failed error=%s", type(exc).__name__)
        return {}


def _store(result: VerificationResult, data: dict) -> None:
    try:
        with transaction.atomic():
            EmailVerification.objects.update_or_create(
                email=result.email,
                defaults={
                    "status": result.status,
                    "reason": result.reason,
                    "accept_all": _true(data.get("accept_all")),
                    "disposable": _true(data.get("disposable")),
                    "role": _true(data.get("role")),
                    "free": _true(data.get("free")),
                    "safe_to_send": _said(data.get("safe_to_send")),
                    "did_you_mean": result.did_you_mean,
                    "checked_at": timezone.now(),
                },
            )
    except DatabaseError as exc:
        # Not the exception's text: a database error can quote the address.
        logger.error(
            "email_verification.store_failed email=%s error=%s",
            email_log_tag(result.email), type(exc).__name__,
        )


def verify_emails(emails: Iterable[str]) -> dict[str, VerificationResult]:
    """Check each address, keyed by its normalised form (stripped, lower case)
    in the order given. Blank addresses are left out and repeats checked once.
    Makes one API call per address that has no recent valid or invalid answer
    on file, up to the daily cap. Never raises."""
    addresses = []
    for email in emails:
        address = EmailVerification.normalise(email)
        if address and address not in addresses:
            addresses.append(address)

    malformed = set()
    for address in addresses:
        try:
            validate_email(address)
        except ValidationError:
            malformed.add(address)
    stored = _stored_answers([address for address in addresses if address not in malformed])
    key_set = bool(_api_key())
    if not key_set and len(stored) + len(malformed) < len(addresses):
        logger.warning("email_verification.not_configured")

    results, capped = {}, False
    for address in addresses:
        if address in malformed:
            results[address] = VerificationResult(address, INVALID, "invalid_email")
        elif address in stored:
            row = stored[address]
            results[address] = VerificationResult(
                address, row.status, row.reason, row.did_you_mean, cached=True,
            )
        elif not key_set:
            results[address] = VerificationResult(address, ERROR, "not_configured")
        elif capped or not _reserve_lookup():
            if not capped:
                logger.warning("email_verification.daily_cap_reached")
            capped = True
            results[address] = VerificationResult(address, ERROR, "daily_cap_reached")
        else:
            result, data = _lookup(address)
            if data is not None:
                _store(result, data)
            results[address] = result
    return results


def verify_email(email: str) -> VerificationResult:
    """Check one address (see ``verify_emails``). Never raises."""
    address = EmailVerification.normalise(email)
    return verify_emails([address]).get(address) or VerificationResult(address, ERROR, "blank")


# --- background ------------------------------------------------------------

def _run(batch: list) -> None:
    try:
        results = verify_emails(batch)
    except Exception as exc:  # noqa: BLE001 - verify_emails shouldn't raise; never let it escape
        logger.error("email_verification.batch_failed error=%s", type(exc).__name__)
        return
    counts = {status: 0 for status in (VALID, INVALID, UNKNOWN, ERROR)}
    for result in results.values():
        counts[result.status] += 1
    logger.info(
        "email_verification.batch_done checked=%s valid=%s invalid=%s unknown=%s error=%s",
        len(results), counts[VALID], counts[INVALID], counts[UNKNOWN], counts[ERROR],
    )


def _run_in_pool(batch: list) -> None:
    try:
        _run(batch)
    finally:
        # The checks opened this thread's own database connection: close it.
        connections.close_all()


def _dispatch(batch: list) -> None:
    if getattr(settings, "EMAIL_VERIFICATION_DISPATCH_SYNC", False):
        _run(batch)
        return
    try:
        _EXECUTOR.submit(_run_in_pool, batch)
    except RuntimeError:
        # submit() raises once the interpreter is shutting down.
        logger.warning("email_verification.dispatch_unavailable")


def verify_after_commit(emails: Iterable[str]) -> None:
    """Check ``emails`` in the background once the current transaction
    commits (at once outside one); nothing happens if it rolls back. Returns
    straight away and never raises: a check can't hold up or fail the work
    that asked for it."""
    batch = [email for email in emails]
    try:
        transaction.on_commit(lambda: _dispatch(batch), robust=True)
    except Exception as exc:  # noqa: BLE001
        logger.error("email_verification.schedule_failed error=%s", type(exc).__name__)
