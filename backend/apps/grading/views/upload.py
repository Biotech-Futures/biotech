"""Bulk mark upload endpoint.

``dry_run=true`` returns just the diff so the UI can preview creates /
updates / errors before the admin commits. Without ``dry_run`` the parser
runs *again* alongside the commit — this ensures the diff we act on
reflects the current database state (someone else may have graded in
between preview and apply). All-or-nothing: any row error aborts the whole
batch so partial imports can't happen.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.submissions.models import SubmissionComponent

from ..permissions import IsGrader
from ..services.upload import commit_marks_upload, parse_marks_upload


class BulkUploadMarksView(APIView):
    """POST /api/v1/grading/components/<code>/bulk-upload/

    Multipart body: ``file`` (xlsx/csv), ``dry_run`` ("true"/"false", default "true").
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]
    parser_classes = [MultiPartParser]

    def post(self, request, code: str):
        component = get_object_or_404(SubmissionComponent, code=code)
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"detail": "missing file"}, status=status.HTTP_400_BAD_REQUEST
            )
        dry_run = str(request.data.get("dry_run", "true")).lower() != "false"

        diff = parse_marks_upload(upload, upload.name, component.code)
        if dry_run:
            return Response(diff.as_dict())

        if diff.errors:
            return Response(
                {"detail": "upload has errors; fix them before applying", **diff.as_dict()},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = commit_marks_upload(diff, user=request.user)
        return Response({"applied": True, **result, **diff.as_dict()})
