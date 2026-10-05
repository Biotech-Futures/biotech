"""Async job dispatcher for bulk-download exports.

Follows the codebase's existing ``*_DISPATCH_SYNC`` convention (see
``LINK_PREVIEW_DISPATCH_SYNC`` in ``apps.chat.tasks``,
``UNREAD_DIGEST_DISPATCH_SYNC`` in ``apps.chat.services.digest``). No broker,
no Celery, no Redis dependency — a daemon thread is fired after
``transaction.on_commit`` and updates the ``GradingJob`` row when done. Tests
set ``GRADING_JOB_DISPATCH_SYNC=True`` to run inline.

Job params (dict on ``GradingJob.params``):

    {
      "kind": "component_zip" | "component_xlsx" | "component_pdf",
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

from apps.groups.models.groups import Groups
from apps.submissions.models import SubmissionQuestion
from apps.submissions.services import current_cohort

from ..models import (
    Grade,
    GradingJob,
    GroupMarkingCategories,
    RubricCriterion,
    SubmissionComponent,
)
from .content import feedback_map, submission_entries
from .xlsx import build_saq_xlsx
from .zip import _COMPONENT_LABELS, build_saq_pdf_zip, build_submissions_zip

logger = logging.getLogger(__name__)


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
        if not kind:
            raise ValueError(f"job {job_id} missing kind in params")

        # Only the per-component exports need a component.
        component = entries = None
        if kind in ("component_zip", "component_xlsx", "component_pdf"):
            component_code = job.params.get("component_code")
            if not component_code:
                raise ValueError(f"job {job_id} missing component_code in params")
            group_ids = job.params.get("group_ids") or None
            component = SubmissionComponent.objects.get(code=component_code)
            entries = submission_entries(
                component_code=component_code, group_ids=group_ids
            )

        if kind == "component_zip":
            # Flat — one component per bundle, so group file names can't
            # collide and folders would just be an extra layer.
            payload = build_submissions_zip(entries, group_folder=False)
            label = _COMPONENT_LABELS.get(component.code, component.code)
            # SAQ's answers come as text files, beside its PDF download.
            suffix = "_TXT" if component.code == "SAQ" else ""
            filename = f"{current_cohort()}_BTF_{label}{suffix}.zip"
        elif kind == "component_xlsx":
            criteria = list(
                RubricCriterion.objects
                .filter(rubric__component__code=component_code, rubric__active=True)
                .order_by("order", "id")
            )
            grades_by_pair = {
                (g.submission_id, g.criterion_id): g
                for g in Grade.objects.filter(
                    submission_id__in=[e.submission_id for e in entries],
                    criterion__rubric__component__code=component_code,
                )
            }
            feedback_by_group = {
                gid: comment
                for (gid, component_id), comment in feedback_map(
                    [e.group_id for e in entries]
                ).items()
                if component_id == component.id
            }
            categories_by_group = {
                c.group_id: c
                for c in GroupMarkingCategories.objects.filter(
                    group_id__in=[e.group_id for e in entries]
                )
            }
            # Every prompt in form order fixes the qN column order; the export
            # keeps only the questions some group actually answered.
            questions = SubmissionQuestion.objects.order_by("order", "id").values_list(
                "prompt", flat=True
            )
            # Each team's challenge year, for the sheet's year column.
            years_by_group = dict(
                Groups.objects.filter(id__in=[e.group_id for e in entries]).values_list(
                    "id", "year"
                )
            )
            payload = build_saq_xlsx(
                entries,
                criteria,
                grades_by_pair,
                feedback_by_group,
                categories_by_group,
                questions=list(questions),
                years_by_group=years_by_group,
            )
            filename = f"{current_cohort()}_BTF_SAQs.xlsx"
        elif kind == "component_pdf":
            # SAQ only: each group's answers as its own PDF, zipped.
            payload = build_saq_pdf_zip(entries)
            filename = f"{current_cohort()}_BTF_SAQs_PDF.zip"
        elif kind == "all_zip":
            # Everything: every group, every component, full folder structure.
            payload = build_submissions_zip(submission_entries())
            filename = f"{current_cohort()}_BTF_All.zip"
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
