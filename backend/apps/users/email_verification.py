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
  (``EmailVerification``); that row is what later flags an address. Each
  real answer also updates the credit balance (``email_credits``).

Nothing here blocks anything: it only reports. Only ``invalid`` is a failed
check; ``unknown`` (QEV's unknown, or a domain that accepts every address) and
``error`` pass. ``error`` means no answer was had: no API key, a timeout, an
outage, a refused or malformed response, every key out of credit, or the daily
lookup cap reached. It is logged and never stored, so the address is checked
again next time.

There are two keys: the free QEV_API_KEY (100 checks a day) is tried first,
and the paid QEV_PAID_API_KEY when it's out of credit (HTTP 402, or none left
after an answer). A key out of credit is skipped until its retry
(``retry_at``). Either key may be set alone. Only the paid key's balance is
kept, and alerted on.

The API keys are sent as a query parameter, so request URLs and the text of
``requests`` exceptions (which include the URL) are never logged; logs name a
key only as "free" or "paid". Addresses are logged as ``email_log_tag`` hashes.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone as dt_timezone
from typing import Iterable, Optional

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError, connections, transaction
from django.db.models import F
from django.utils import timezone

from apps.common.pii import email_log_tag

from .email_credits import credits_in, record_remaining
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


# The two keys, by the names logs and the credit balance use (never the keys).
FREE, PAID = "free", "paid"


def _keys() -> list[tuple[str, str]]:
    """The keys configured, in the order they're tried: the free QEV_API_KEY,
    then the paid QEV_PAID_API_KEY when it's out of credit. Either may be
    blank; with only the paid key set, it's used directly."""
    keys = [
        (FREE, getattr(settings, "QEV_API_KEY", "") or ""),
        (PAID, getattr(settings, "QEV_PAID_API_KEY", "") or ""),
    ]
    return [(name, key) for name, key in keys if key]


def _exhausted_field(name: str) -> str:
    return f"{name}_exhausted_at"


def retry_at(exhausted_at: datetime) -> datetime:
    """When a key found out of credit at ``exhausted_at`` is tried again:
    QEV_EXHAUSTED_RETRY_MINUTES later or the next UTC midnight, whichever is
    sooner (QEV doesn't say when free daily credits reset)."""
    minutes = int(getattr(settings, "QEV_EXHAUSTED_RETRY_MINUTES", 60))
    midnight = datetime.combine(
        exhausted_at.astimezone(dt_timezone.utc).date() + timedelta(days=1), time.min, tzinfo=dt_timezone.utc,
    )
    return min(exhausted_at + timedelta(minutes=minutes), midnight)


def _usable_keys() -> list[tuple[str, str]]:
    """The configured keys that aren't out of credit, or are due a retry."""
    keys = _keys()
    if not keys:
        return []
    try:
        credits = EmailVerificationCredits.objects.filter(pk=EmailVerificationCredits.SINGLETON_PK).first()
    except DatabaseError as exc:
        # Without the record, try every key: a refused request costs nothing.
        logger.error("email_verification.key_state_unreadable error=%s", type(exc).__name__)
        return keys
    now = timezone.now()
    usable = []
    for name, key in keys:
        exhausted_at = getattr(credits, _exhausted_field(name), None) if credits else None
        if exhausted_at is None or now >= retry_at(exhausted_at):
            usable.append((name, key))
    return usable


def _set_exhausted(name: str, exhausted: bool) -> None:
    """Note a key as out of credit (now), or as having credit again. Logged
    when that changes, not on every request. Never raises."""
    field = _exhausted_field(name)
    rows = EmailVerificationCredits.objects.filter(pk=EmailVerificationCredits.SINGLETON_PK)
    try:
        if exhausted:
            EmailVerificationCredits.get()
            # Newly out of credit: logged once. Already noted (a retry that
            # found it still empty): the time moves on quietly.
            if rows.filter(**{f"{field}__isnull": True}).update(**{field: timezone.now()}):
                logger.warning("email_verification.key_exhausted key=%s", name)
            else:
                rows.update(**{field: timezone.now()})
        elif rows.filter(**{f"{field}__isnull": False}).update(**{field: None}):
            logger.info("email_verification.key_available key=%s", name)
    except DatabaseError as exc:
        logger.error("email_verification.key_state_not_saved key=%s error=%s", name, type(exc).__name__)


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


def _failed(email: str, reason: str, exc: Optional[BaseException] = None, key: str = "") -> VerificationResult:
    # Only the exception's type: its text can carry the request URL, and so the key.
    logger.warning(
        "email_verification.lookup_failed email=%s key=%s reason=%s error=%s",
        email_log_tag(email), key, reason, type(exc).__name__ if exc else "",
    )
    return VerificationResult(email, ERROR, reason)


# What _ask() returns when the key it used is out of credit (HTTP 402).
OUT_OF_CREDIT = "out_of_credit"


def _lookup(email: str) -> tuple[VerificationResult, Optional[dict]]:
    """Ask QEV about one address with the first usable key, falling back to
    the next when one is out of credit: the result, and QEV's answer when
    there was one to store. Never raises."""
    for name, key in _usable_keys():
        outcome = _ask(email, name, key)
        if outcome == OUT_OF_CREDIT:
            _set_exhausted(name, True)
            continue
        return outcome
    # Every key is out of credit: no check, as with any other failure.
    return VerificationResult(email, ERROR, OUT_OF_CREDIT), None


def _ask(email: str, name: str, key: str):
    """One request with one key: ``(result, answer)``, or ``OUT_OF_CREDIT``."""
    try:
        response = requests.get(
            SANDBOX_URL if _sandbox() else VERIFY_URL,
            params={"apikey": key, "email": email},
            timeout=float(getattr(settings, "QEV_TIMEOUT_SECONDS", 5)),
        )
    except requests.Timeout as exc:
        return _failed(email, "request_timeout", exc, name), None
    except requests.RequestException as exc:
        return _failed(email, "connection_error", exc, name), None
    except Exception as exc:  # noqa: BLE001 - an outage must never stop a registration
        return _failed(email, "request_failed", exc, name), None

    if name == PAID and not _sandbox():
        # Every real answer, error statuses included, may say how many paid
        # credits are left. Only the paid balance is kept and alerted on.
        record_remaining(response.headers)
    if response.status_code == 402:
        return OUT_OF_CREDIT
    if response.status_code != 200:
        return _failed(email, f"http_{response.status_code}", key=name), None
    try:
        data = response.json()
    except ValueError as exc:
        return _failed(email, "bad_response", exc, name), None
    if not isinstance(data, dict):
        return _failed(email, "bad_response", key=name), None
    if not _true(data.get("success")):
        # Its message isn't logged: it's QEV's own text.
        return _failed(email, "service_refused", key=name), None
    status = _status(data)
    if status is None:
        return _failed(email, "bad_response", key=name), None
    # A key with no credits left after this answer goes out of use until its
    # retry, so the next check doesn't spend a request finding out.
    _set_exhausted(name, credits_in(response.headers) == 0)

    result = VerificationResult(
        email, status,
        reason=str(data.get("reason") or "")[:32],
        did_you_mean=str(data.get("did_you_mean") or "")[:254],
    )
    logger.info(
        "email_verification.checked email=%s key=%s status=%s reason=%s",
        email_log_tag(email), name, result.status, result.reason,
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
    key_set = bool(_keys())
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
        elif not _usable_keys():
            # Every key is out of credit until its retry: no request, no count.
            results[address] = VerificationResult(address, ERROR, OUT_OF_CREDIT)
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
