"""Management > Challenge Start > Release Resources: every resource (not the
files embedded in pages), whether it's shown, its release date, and when it
was released last year, for admins; and changing whether it's shown or its
release date (apps.resources.release)."""
from __future__ import annotations

from django.db import transaction
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.services import log_audit_event
from apps.common.rbac import IsStaffOrAdmin
from apps.resources.models import Resources
from apps.resources.release import is_released, last_released, set_release_on, set_shown


def _resources():
    return Resources.objects.filter(deleted_at__isnull=True).exclude(kind=Resources.ResourceKind.ATTACHMENT)


def _state(resource) -> dict:
    return {
        "shown": resource.shown,
        "release_on": resource.release_on.isoformat() if resource.release_on else None,
    }


def _rows(resources) -> list[dict]:
    """Each resource's row: shown, its release date, whether students and
    the rest have it now (released), and its release last year."""
    resources = list(resources)
    last = last_released(resource.id for resource in resources)
    return [
        {
            "id": resource.id,
            "name": resource.name,
            # For its icon, as the Resources page shows it.
            "kind": resource.kind,
            "file_mime_type": resource.file_mime_type,
            **_state(resource),
            "released": is_released(resource),
            "last_released_at": last[resource.id].isoformat() if resource.id in last else None,
        }
        for resource in resources
    ]


class ResourceReleasesView(APIView):
    """GET ``{"resources": [...]}``: every resource's row, by name."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        return Response({"resources": _rows(_resources().order_by("name", "id"))})


class ResourceReleaseView(APIView):
    """PATCH ``{"shown": bool}`` and/or ``{"release_on": "YYYY-MM-DD" | null}``:
    one resource's row as it is then."""

    permission_classes = [permissions.IsAuthenticated, IsStaffOrAdmin]

    def patch(self, request, resource_id):
        resource = _resources().filter(pk=resource_id).first()
        if resource is None:
            return Response({"detail": "No resource has this id."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data if isinstance(request.data, dict) else {}
        if "shown" not in data and "release_on" not in data:
            return Response({"detail": "Give shown or release_on."}, status=status.HTTP_400_BAD_REQUEST)
        if "shown" in data and not isinstance(data["shown"], bool):
            return Response({"shown": ["Give true or false."]}, status=status.HTTP_400_BAD_REQUEST)
        day = None
        if "release_on" in data:
            try:
                day = serializers.DateField(allow_null=True).run_validation(data["release_on"])
            except serializers.ValidationError:
                return Response(
                    {"release_on": ["Give a date (YYYY-MM-DD), or null for none."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        before = _state(resource)
        with transaction.atomic():
            # Shown or hidden first, so a date sent with it stands.
            if "shown" in data:
                set_shown(resource, data["shown"])
            if "release_on" in data:
                set_release_on(resource, day)
            resource.save(update_fields=["shown", "release_on"])
            log_audit_event(
                actor=request.user, entity_type="resource", entity_id=resource.pk,
                action=AuditLog.ActionChoices.UPDATE, before_state=before, after_state=_state(resource),
            )
        return Response(_rows([resource])[0])
