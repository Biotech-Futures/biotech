"""Checking a registration's addresses before it's submitted, so the person
registering can correct any that don't exist while they wait.

- ``POST /api/v1/registration/email-check/`` takes the registration as
  ``register()`` would (``{journey, payload}``), finds every student's and
  guardian's address, and starts a check of those without a recent answer on
  file. ``202 {"status": "started" | "done", "jobId", "total", "done"}``.
- ``GET /api/v1/registration/email-check/<jobId>/`` reports its progress:
  ``{"status", "total", "done", "invalid", "errors", "skipped",
  "estimatedSecondsRemaining"}``.

Each answer is stored as an EmailVerification, so when the registration is
then submitted, ``register()`` warns about any address found not to exist
(``registration_warnings``). The check never holds a registration up: any
answer without a ``jobId`` (``disabled``, ``closed``, ``too_many``), any
error, and a job that's ``failed`` or ``stalled`` mean the page submits
without it.

It's open only while registration is (or with a valid late link, or for a
supervisor allowed after close), off unless EMAIL_PRECHECK_ENABLED, limited
in how many addresses one request may carry (fewer for anyone not signed
in), and limited in how many new lookups one IP address may cause an hour.
Addresses over that budget are left unchecked. Addresses are never logged or
kept on the job.
"""
from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connections, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import email_verification
from .models import EmailCheckJob, EmailVerification
from .registration_intake import (
    SUPERVISOR_JOURNEYS, IntakeInput, authenticated_supervisor, current_window, error_fields,
    registers_after_close, valid_invitation,
)
from .serializers import email_precheck_enabled

logger = logging.getLogger(__name__)

# Answers without a job: the page submits without the check.
DISABLED, CLOSED, TOO_MANY = "disabled", "closed", "too_many"
STARTED, STALLED = "started", "stalled"

# Jobs are deleted this long after they start.
JOB_LIFETIME = timedelta(days=1)

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="email-precheck")


def _setting(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


def registration_addresses(students) -> list[str]:
    """Every student's and guardian's address in a registration, lower case,
    each once, in the form's order."""
    addresses = []
    for student in students:
        addresses.append(student["email"])
        addresses.append(student["guardian"].get("email", ""))
    return list(dict.fromkeys(
        address.strip().lower() for address in addresses if address and address.strip()
    ))


def _registration_open(request, journey: str) -> bool:
    """Whether this registration could be submitted now: as register() decides,
    without using up a late link."""
    with transaction.atomic():
        window = current_window()
        now = timezone.now()
        if window.is_open(now):
            return True
        token = request.headers.get("X-Registration-Invitation", "")
        if token:
            try:
                return valid_invitation(token, window, now, journey=journey) is not None
            except serializers.ValidationError:
                return False
    return journey in SUPERVISOR_JOURNEYS and registers_after_close(request.user)


def _client_tag(request) -> str:
    from .views import _client_ip

    return hashlib.sha256(_client_ip(request).encode()).hexdigest()[:16]


def _take_budget(tag: str, wanted: int) -> int:
    """How many of ``wanted`` new lookups this IP may still make this hour
    (EMAIL_PRECHECK_IP_HOURLY_LOOKUPS), and count them as made."""
    if wanted <= 0:
        return 0
    limit = _setting("EMAIL_PRECHECK_IP_HOURLY_LOOKUPS", 200)
    key = f"email_precheck_ip:{tag}"
    cache.add(key, 0, 3600)
    used = cache.get(key, 0)
    granted = max(0, min(wanted, limit - used))
    if granted:
        try:
            cache.incr(key, granted)
        except ValueError:
            # Expired between the two calls: start the hour again.
            cache.set(key, granted, 3600)
    return granted


def start_check(request) -> tuple[dict, int]:
    """Start checking the registration in ``request``. Returns the answer and
    its status code."""
    if not email_precheck_enabled():
        return {"status": DISABLED}, status.HTTP_200_OK
    SessionAuthentication().enforce_csrf(request)
    if not isinstance(request.data, dict):
        raise serializers.ValidationError({"detail": "Provide a registration object."})
    parser = IntakeInput(data=request.data, context={"legacy": False})
    if not parser.is_valid():
        errors = error_fields(parser.errors)
        raise serializers.ValidationError({key.removeprefix("payload."): value for key, value in errors.items()})
    journey = parser.validated_data["journey"]
    students = parser.validated_data["payload"]["students"]
    if journey in SUPERVISOR_JOURNEYS:
        authenticated_supervisor(request)
    if not _registration_open(request, journey):
        return {"status": CLOSED}, status.HTTP_200_OK

    addresses = registration_addresses(students)
    signed_in = request.user.is_authenticated
    most = _setting("EMAIL_PRECHECK_MAX_ADDRESSES", 2000) if signed_in else _setting(
        "EMAIL_PRECHECK_ANONYMOUS_MAX_ADDRESSES", 20,
    )
    if len(addresses) > most:
        return {"status": TOO_MANY}, status.HTTP_200_OK

    try:
        on_file = EmailVerification.reusable(addresses, max_age_days=_setting("QEV_RESULT_MAX_AGE_DAYS", 180))
    except DatabaseError:
        on_file = {}
    unchecked = [address for address in addresses if address not in on_file]
    tag = _client_tag(request)
    to_check = unchecked[:_take_budget(tag, len(unchecked))]
    skipped = len(unchecked) - len(to_check)
    if skipped:
        logger.warning("email_precheck.budget_reached client=%s skipped=%s", tag, skipped)

    EmailCheckJob.objects.filter(created_at__lt=timezone.now() - JOB_LIFETIME).delete()
    job = EmailCheckJob.objects.create(
        status=EmailCheckJob.Status.QUEUED if to_check else EmailCheckJob.Status.DONE,
        total=len(addresses), cached=len(on_file), skipped=skipped,
        done=len(on_file) + skipped,
        invalid=sum(answer.status == EmailVerification.Status.INVALID for answer in on_file.values()),
        client_tag=tag, created_by=request.user if signed_in else None,
    )
    if to_check:
        transaction.on_commit(lambda: _dispatch(job.pk, to_check), robust=True)
    logger.info(
        "email_precheck.started job=%s total=%s cached=%s checking=%s skipped=%s",
        job.pk, job.total, job.cached, len(to_check), skipped,
    )
    return {
        "status": STARTED if to_check else job.status, "jobId": str(job.pk),
        "total": job.total, "done": job.done,
    }, status.HTTP_202_ACCEPTED


def job_status(job_id) -> tuple[dict, int]:
    """A job's progress, as the page polls it."""
    if not email_precheck_enabled():
        return {"status": DISABLED}, status.HTTP_200_OK
    job = EmailCheckJob.objects.filter(pk=job_id).first()
    if job is None:
        return {"status": "not_found"}, status.HTTP_404_NOT_FOUND
    current = job.status
    stall_after = timedelta(seconds=_setting("EMAIL_PRECHECK_STALL_SECONDS", 60))
    if current in (EmailCheckJob.Status.QUEUED, EmailCheckJob.Status.RUNNING) and \
            timezone.now() - job.updated_at > stall_after:
        current = STALLED
    return {
        "status": current, "total": job.total, "done": job.done, "invalid": job.invalid,
        "errors": job.errors, "skipped": job.skipped,
        "estimatedSecondsRemaining": estimate_seconds(job) if current not in (STALLED,) else None,
    }, status.HTTP_200_OK


def estimate_seconds(job: EmailCheckJob):
    """Not estimated yet (stage 3): None while the job runs, 0 once done."""
    return 0 if job.status == EmailCheckJob.Status.DONE else None


# --- running a job -----------------------------------------------------------

def _progress(job_id, **counts) -> None:
    EmailCheckJob.objects.filter(pk=job_id).update(
        updated_at=timezone.now(), **{field: F(field) + value for field, value in counts.items()},
    )


def run_job(job_id, addresses) -> None:
    """Check each address in turn, noting the job's progress. Never raises:
    a job that fails is marked failed, and the page submits without it."""
    try:
        EmailCheckJob.objects.filter(pk=job_id).update(status=EmailCheckJob.Status.RUNNING, updated_at=timezone.now())
        for address in addresses:
            result = email_verification.verify_email(address)
            _progress(
                job_id, done=1,
                invalid=int(result.status == email_verification.INVALID),
                errors=int(result.status == email_verification.ERROR),
            )
        EmailCheckJob.objects.filter(pk=job_id).update(status=EmailCheckJob.Status.DONE, updated_at=timezone.now())
    except Exception as exc:  # noqa: BLE001
        logger.error("email_precheck.job_failed job=%s error=%s", job_id, type(exc).__name__)
        try:
            EmailCheckJob.objects.filter(pk=job_id).update(status=EmailCheckJob.Status.FAILED, updated_at=timezone.now())
        except Exception:  # noqa: BLE001
            pass


def _run_in_pool(job_id, addresses) -> None:
    try:
        run_job(job_id, addresses)
    finally:
        connections.close_all()


def _dispatch(job_id, addresses) -> None:
    if getattr(settings, "EMAIL_VERIFICATION_DISPATCH_SYNC", False):
        run_job(job_id, addresses)
        return
    try:
        _EXECUTOR.submit(_run_in_pool, job_id, addresses)
    except RuntimeError:
        logger.warning("email_precheck.dispatch_unavailable job=%s", job_id)
        EmailCheckJob.objects.filter(pk=job_id).update(status=EmailCheckJob.Status.FAILED)


# --- views -------------------------------------------------------------------

class EmailCheckStartView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = [SessionAuthentication]
    parser_classes = [JSONParser]

    def post(self, request):
        body, code = start_check(request)
        return Response(body, status=code)


class EmailCheckStatusView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = [SessionAuthentication]

    def get(self, request, job_id):
        body, code = job_status(job_id)
        return Response(body, status=code)
