"""Async job dispatcher for bulk-download exports.

Follows the codebase's existing ``*_DISPATCH_SYNC`` convention (see
``LINK_PREVIEW_DISPATCH_SYNC`` in ``apps.chat.tasks``,
``UNREAD_DIGEST_DISPATCH_SYNC`` in ``apps.chat.services.digest``). No broker,
no Celery, no Redis dependency — a daemon thread is fired after
``transaction.on_commit`` and updates the ``GradingJob`` row when done. Tests
set ``GRADING_JOB_DISPATCH_SYNC=True`` to run inline.

Job params (dict on ``GradingJob.params``):

    {
      "kind": "component_zip" | "component_xlsx",
      "component_code": "POSTER",
      "group_ids": [1, 2, 3],   # optional; empty/absent = all groups
    }

Result is written to Azure Blob (django-storages default) under
``grading/jobs/<job_id>/<filename>``; the SAS-signed public URL goes into
``GradingJob.result_url`` for the polling client to fetch.
"""
from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from django.contrib.auth import get_user_model

from apps.groups.models.group_members import GroupMembership
from apps.submissions.models import Submission, SubmissionComponent
from apps.users.models import StudentProfile

from ..models import Grade, GradingJob, RubricCriterion
from .docx import (
    certificate_context,
    marks_summary_context,
    render_marks_summary,
    render_participation_certificate,
)
from .xlsx import build_saq_xlsx
from .zip import _safe, build_submissions_zip

logger = logging.getLogger(__name__)


def _resolve_submissions(component_code: str, group_ids: list[int] | None):
    qs = (
        Submission.objects.filter(component__code=component_code)
        .select_related("group", "component")
        .order_by("group__group_name")
    )
    if group_ids:
        qs = qs.filter(group_id__in=group_ids)
    return list(qs)


def _run_job(job_id: int) -> None:
    """Materialise the export, store it, mark the job done. Runs in a
    daemon thread (or inline under DISPATCH_SYNC). Never raises — errors are
    captured onto the job row so the polling client can surface them."""
    try:
        job = GradingJob.objects.get(pk=job_id)
    except GradingJob.DoesNotExist:
        logger.warning("GradingJob %s vanished before it could run", job_id)
        return

    try:
        GradingJob.objects.filter(pk=job_id).update(status=GradingJob.STATUS_RUNNING)

        kind = job.params.get("kind")
        component_code = job.params.get("component_code")
        group_ids = job.params.get("group_ids") or None
        if not (kind and component_code):
            raise ValueError(f"job {job_id} missing kind/component_code in params")

        component = SubmissionComponent.objects.get(code=component_code)
        submissions = _resolve_submissions(component_code, group_ids)

        if kind == "component_zip":
            payload = build_submissions_zip(submissions)
            filename = f"{component.code}-bundle.zip"
        elif kind == "component_xlsx":
            criteria = list(
                RubricCriterion.objects
                .filter(rubric__component__code=component_code, rubric__active=True)
                .order_by("order", "id")
            )
            grades_by_pair = {
                (g.submission_id, g.criterion_id): g
                for g in Grade.objects.filter(
                    submission_id__in=[s.id for s in submissions],
                    criterion__rubric__component__code=component_code,
                )
            }
            payload = build_saq_xlsx(submissions, criteria, grades_by_pair)
            filename = f"{component.code}-saq.xlsx"
        elif kind == "supervisor_bundle":
            year = int(job.params.get("year"))
            supervisor_user_id = int(job.params.get("supervisor_user_id"))
            payload = _build_supervisor_bundle(supervisor_user_id, year)
            filename = f"supervisor-{supervisor_user_id}-{year}.zip"
        else:
            raise ValueError(f"job {job_id} unknown kind {kind!r}")

        # Store the opaque storage KEY, not a URL. The polling API turns this
        # into a Django-served download URL so the client works whether the
        # backend is Azure Blob (prod) or local filesystem (dev). Avoids the
        # SAS-token / no-credentials headache that surfaced in local testing.
        stored = default_storage.save(
            f"grading/jobs/{job_id}/{filename}", ContentFile(payload)
        )

        GradingJob.objects.filter(pk=job_id).update(
            status=GradingJob.STATUS_DONE,
            result_url=stored,
            finished_at=timezone.now(),
        )
    except Exception as exc:  # noqa: BLE001 — worker-thread swallow with audit
        logger.exception("GradingJob %s failed", job_id)
        GradingJob.objects.filter(pk=job_id).update(
            status=GradingJob.STATUS_FAILED,
            error=str(exc)[:2000],
            finished_at=timezone.now(),
        )


def _build_supervisor_bundle(supervisor_user_id: int, year: int) -> bytes:
    """Bundle marks summary + participation certificate for every student the
    supervisor supervises. Runs off the `_grades_payload` helper so the docx
    context matches what a student would get via ``/me/summary/``.
    """
    import io
    import zipfile

    # Local import to avoid a circular between views.student and services.dispatch.
    from ..views.student import _grades_payload

    User = get_user_model()
    supervisor = User.objects.filter(pk=supervisor_user_id).first()
    if supervisor is None:
        raise ValueError(f"supervisor user {supervisor_user_id} not found")
    profile = getattr(supervisor, "supervisorprofile", None)
    if profile is None:
        raise ValueError(f"user {supervisor_user_id} is not a supervisor")

    students = list(
        StudentProfile.objects.filter(supervisor=profile).select_related("user")
    )

    student_groups = {}
    student_user_ids = [sp.user_id for sp in students]
    if student_user_ids:
        for m in (
            GroupMembership.objects.filter(
                user_id__in=student_user_ids,
                left_at__isnull=True,
                membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
            )
            .select_related("group")
            .order_by("-joined_at")
        ):
            student_groups.setdefault(m.user_id, m.group)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for sp in students:
            group = student_groups.get(sp.user_id)
            if group is None:
                continue
            components = _grades_payload(group, year)
            folder = _safe(sp.user.get_full_name() or sp.user.email)
            summary_bytes = render_marks_summary(
                marks_summary_context(group, year, components)
            )
            cert_bytes = render_participation_certificate(
                certificate_context(
                    sp.user.get_full_name() or sp.user.email,
                    group.group_name,
                    year,
                )
            )
            zf.writestr(f"{folder}/marks-summary.docx", summary_bytes)
            zf.writestr(f"{folder}/certificate.docx", cert_bytes)

    return buffer.getvalue()


def dispatch_job(job: GradingJob) -> None:
    """Kick off a background render for the given job.

    In prod: schedules the thread after commit so the caller's transaction
    is visible to the worker. Under ``GRADING_JOB_DISPATCH_SYNC=True`` runs
    inline for deterministic tests.
    """
    if getattr(settings, "GRADING_JOB_DISPATCH_SYNC", False):
        _run_job(job.id)
        return

    def _later():
        threading.Thread(
            target=_run_job,
            args=(job.id,),
            name=f"grading-job-{job.id}",
            daemon=True,
        ).start()

    # on_commit is a no-op outside a transaction, so calling from a bare view
    # still fires — but if the view wraps its work in @transaction.atomic, we
    # correctly wait for the row to be visible before spawning the thread.
    transaction.on_commit(_later)
