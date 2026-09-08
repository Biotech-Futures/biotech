import logging

from django.http import HttpResponse
from rest_framework import permissions, serializers
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import GradingSettings
from ..permissions import IsGrader


logger = logging.getLogger(__name__)

# Upload checks (and later the renderers) read the whole file into memory, so
# cap the size well above any real docx or signature scan.
MAX_DOCUMENT_UPLOAD_BYTES = 10 * 1024 * 1024


class GradingSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradingSettings
        fields = [
            "director_1_name",
            "director_1_signature",
            "director_2_name",
            "director_2_signature",
            "marks_summary_template",
            "certificate_template",
            "component_weights",
        ]

    def _checked_upload(self, uploaded, check):
        """Run one incoming file through its pre-replace check.

        A rejected file 400s the whole PATCH, so the previously uploaded file
        — and everything else in the request — stays exactly as it was.
        """
        if not uploaded:
            return uploaded
        if uploaded.size and uploaded.size > MAX_DOCUMENT_UPLOAD_BYTES:
            raise serializers.ValidationError("File is too large (10 MB max).")
        # Local import: python-docx is heavier than anything else views pull in.
        from ..services import docx as docx_service

        data = uploaded.read()
        uploaded.seek(0)
        try:
            check(docx_service, data)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return uploaded

    def validate_marks_summary_template(self, value):
        return self._checked_upload(
            value, lambda svc, data: svc.check_template_upload("marks-summary", data)
        )

    def validate_certificate_template(self, value):
        return self._checked_upload(
            value, lambda svc, data: svc.check_template_upload("certificate", data)
        )

    def validate_director_1_signature(self, value):
        return self._checked_upload(value, lambda svc, data: svc.check_signature_upload(data))

    def validate_director_2_signature(self, value):
        return self._checked_upload(value, lambda svc, data: svc.check_signature_upload(data))


class GradingSettingsView(RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/grading/settings/

    Singleton — returns and patches the one ``GradingSettings`` row.
    File fields (signatures, docx templates) use multipart uploads; the JSON
    field (component_weights) accepts a dict via either parser.

    Incoming files are checked before they replace anything (see the
    serializer), and a replaced or cleared file's old blob is deleted after
    the save — re-uploads must not accumulate orphans in the media container.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]
    serializer_class = GradingSettingsSerializer
    # Accept multipart (file uploads) and JSON (director-name patches with no
    # file). Without JSONParser, plain-text PATCHes 415 with "Unsupported
    # media type application/json".
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "patch"]

    _FILE_FIELDS = (
        "director_1_signature",
        "director_2_signature",
        "marks_summary_template",
        "certificate_template",
    )

    def get_object(self):
        return GradingSettings.load()

    def perform_update(self, serializer):
        # Save first, delete after: a failed save can then never leave the
        # row pointing at a blob that no longer exists.
        instance = serializer.instance
        old_names = {
            name: (getattr(instance, name).name if getattr(instance, name) else "")
            for name in self._FILE_FIELDS
        }
        serializer.save()
        for name, old_name in old_names.items():
            field_file = getattr(instance, name)
            new_name = field_file.name if field_file else ""
            if old_name and old_name != new_name:
                try:
                    instance._meta.get_field(name).storage.delete(old_name)
                except Exception:
                    # Cleanup must never fail the request — an orphaned blob
                    # is harmless next to a 500 on Save.
                    logger.exception(
                        "grading_settings.stale_blob_delete_failed name=%s", old_name
                    )


def _read_candidate(request, kind: str):
    """Read and gate the candidate file of a preview POST.

    The candidate is scanned/rendered but never stored — the saved template
    stays active until the admin commits it through the settings PATCH.
    Returns ``(data, scan, error_response)``: the error is set on failure,
    the other two on success.
    """
    if kind not in ("marks-summary", "certificate"):
        return None, None, Response({"detail": "unknown template kind"}, status=404)
    upload = request.FILES.get("file")
    if upload is None:
        return None, None, Response(
            {"detail": "Attach the candidate .docx as 'file'."}, status=400
        )
    if upload.size and upload.size > MAX_DOCUMENT_UPLOAD_BYTES:
        return None, None, Response({"detail": "File is too large (10 MB max)."}, status=400)
    # Local import: python-docx is heavier than anything else views pull in.
    from ..services import docx as docx_service

    data = upload.read()
    try:
        scan = docx_service.check_template_upload(kind, data)
    except ValueError as exc:
        return None, None, Response({"detail": str(exc)}, status=400)
    return data, scan, None


def _docx_response(payload: bytes, kind: str) -> HttpResponse:
    resp = HttpResponse(
        payload,
        content_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
    )
    resp["Content-Disposition"] = f'attachment; filename="test-{kind}.docx"'
    return resp


class TemplateScanView(APIView):
    """GET/POST /api/v1/grading/settings/template-scan/<kind>/

    GET reports which placeholders the active template contains — what will
    be filled, and what is present but unrecognised (usually a typo).
    POST runs the same report on an attached candidate file WITHOUT saving
    it, so the settings page can preview a selection before Save replaces
    the stored template.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, kind: str):
        from ..services import docx as docx_service

        try:
            return Response(docx_service.scan_template(kind))
        except ValueError:
            return Response({"detail": "unknown template kind"}, status=404)

    def post(self, request, kind: str):
        _data, scan, error = _read_candidate(request, kind)
        if error:
            return error
        return Response({"uploaded": True, **scan})


class TemplateTestRenderView(APIView):
    """GET/POST /api/v1/grading/settings/test-render/<kind>/

    Renders a template with obviously synthetic data and streams the docx,
    so an admin can open it and spot any placeholder that did not get
    substituted — before real documents ever go out. GET renders the active
    template (uploaded, or the bundled fallback); POST renders an attached
    candidate file WITHOUT saving it, so a selection can be test-driven
    while the stored template stays untouched until Save.
    """

    permission_classes = [permissions.IsAuthenticated, IsGrader]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, kind: str):
        # Local import: python-docx is heavier than anything else views pull in.
        from ..services import docx as docx_service

        if kind == "marks-summary":
            payload = docx_service.render_marks_summary(
                docx_service.sample_marks_summary_context()
            )
        elif kind == "certificate":
            payload = docx_service.render_participation_certificate(
                docx_service.sample_certificate_context()
            )
        else:
            return Response({"detail": "unknown template kind"}, status=404)
        return _docx_response(payload, kind)

    def post(self, request, kind: str):
        from ..services import docx as docx_service

        data, _scan, error = _read_candidate(request, kind)
        if error:
            return error
        if kind == "marks-summary":
            payload = docx_service.render_marks_summary_data(
                data, docx_service.sample_marks_summary_context()
            )
        else:
            payload = docx_service.render_certificate_data(
                data, docx_service.sample_certificate_context()
            )
        return _docx_response(payload, kind)
