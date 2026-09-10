"""Bulk download endpoints.

Per-group download is synchronous — the payload is bounded (one group × ≤ 4
components) and always small enough to stream back in a single response.

Per-component download is async by default — even the smallest single
component can span ~180 groups × several MB, easily blowing Azure's ~230s
gateway cap. The client enqueues a ``GradingJob`` and polls
``GET /api/v1/grading/jobs/<id>/`` for the result URL. ``format=xlsx`` short-
circuits to the SAQ spreadsheet builder; anything else falls through to the
generic zip.
"""
from __future__ import annotations

import mimetypes

from django.core.files.storage import default_storage
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models.groups import Groups

from ..models import GradingJob, SubmissionComponent
from ..permissions import IsGrader
from ..services import content
from ..services.dispatch import dispatch_job
from ..services.zip import build_submissions_zip, zip_filename


class GroupDownloadView(APIView):
    """GET /api/v1/grading/groups/<id>/download/?component=all|<code>"""

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request, group_id: int):
        group = get_object_or_404(Groups.objects.filter(deleted_at__isnull=True), pk=group_id)
        component_code = request.query_params.get("component") or "all"

        entries = content.submission_entries(
            group_id=group.id,
            component_code=None if component_code == "all" else component_code,
        )

        payload = build_submissions_zip(entries)
        prefix = f"group-{group.id}" + ("" if component_code == "all" else f"-{component_code}")
        response = HttpResponse(payload, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{zip_filename(prefix)}"'
        return response


class ComponentDownloadView(APIView):
    """POST /api/v1/grading/components/<code>/download/

    Body: ``{"group_ids": [1,2,3] | null, "format": "zip" | "xlsx"}``
    Returns 202 with ``{"job_id": <int>}`` — client polls the job endpoint.

    POST (not GET) because kicking off a job mutates server state (creates a
    ``GradingJob`` row and spawns a worker). Keeping this side effect off the
    idempotent GET verb avoids prefetch/scanner traffic accidentally spinning
    up jobs.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def post(self, request, code: str):
        component = get_object_or_404(SubmissionComponent, code=code)
        fmt = (request.data.get("format") or "zip").lower()
        if fmt not in {"zip", "xlsx"}:
            return Response(
                {"detail": f"format must be zip|xlsx, got {fmt!r}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if fmt == "xlsx" and component.code != "SAQ":
            # XLSX is a text-oriented export; only SAQ has text. Rejecting
            # early avoids producing an empty spreadsheet for POSTER etc.
            return Response(
                {"detail": "xlsx format only makes sense for text-bearing components (SAQ)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group_ids = request.data.get("group_ids") or None
        if group_ids is not None and not isinstance(group_ids, list):
            return Response(
                {"detail": "group_ids must be a list of integers or omitted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job = GradingJob.objects.create(
            kind=GradingJob.KIND_BULK_ZIP,
            status=GradingJob.STATUS_PENDING,
            params={
                "kind": "component_xlsx" if fmt == "xlsx" else "component_zip",
                "component_code": component.code,
                "group_ids": group_ids,
            },
            created_by=request.user,
        )
        dispatch_job(job)
        return Response({"job_id": job.id}, status=status.HTTP_202_ACCEPTED)


class GradingJobDetailView(generics.RetrieveAPIView):
    """GET /api/v1/grading/jobs/<id>/ — poll target for the client dialog.

    ``download_url`` is populated once the job is ``done`` and points at
    :class:`GradingJobDownloadView` — a Django-served proxy that streams the
    artefact bytes from ``default_storage``. This decouples the client from
    the storage backend so the same UI works with local files in dev and
    Azure Blob in prod without SAS-token plumbing on the browser side.
    """

    queryset = GradingJob.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def retrieve(self, request, *args, **kwargs):
        job = self.get_object()
        download_url = None
        if job.status == GradingJob.STATUS_DONE and job.result_url:
            download_url = request.build_absolute_uri(
                reverse("grading:job-download", kwargs={"pk": job.pk})
            )
        return Response({
            "id": job.id,
            "kind": job.kind,
            "status": job.status,
            "download_url": download_url,
            "error": job.error or None,
            "created_at": job.created_at,
            "finished_at": job.finished_at,
        })


class GradingJobDownloadView(APIView):
    """GET /api/v1/grading/jobs/<id>/download/ — stream the artefact.

    Opens the stored key via ``default_storage`` and pipes bytes back with a
    filename derived from the storage key. Works whether the file lives on
    the local filesystem (dev, ``FileSystemStorage``) or Azure Blob (prod,
    ``AzureStorage``) — the storage abstraction hides the difference.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]

    def get(self, request, pk: int):
        job = get_object_or_404(GradingJob, pk=pk)
        if job.status != GradingJob.STATUS_DONE or not job.result_url:
            return Response(
                {"detail": "job is not ready"},
                status=status.HTTP_409_CONFLICT,
            )

        filename = job.result_url.rsplit("/", 1)[-1] or f"grading-job-{job.pk}.bin"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # StreamingHttpResponse hands raw file chunks back without buffering
        # a full multi-MB archive in Python memory — matters most in prod
        # when a job's result runs into tens of MB.
        fh = default_storage.open(job.result_url, "rb")

        def _chunks():
            try:
                while True:
                    chunk = fh.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                fh.close()

        response = StreamingHttpResponse(_chunks(), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
