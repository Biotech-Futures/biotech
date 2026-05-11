import os
import re
import tempfile
from typing import Any, Mapping

from django.db import transaction
from django.utils import timezone

from apps.audit.services import log_audit_event
from apps.resources.models import ResourceType, Resources
from apps.resources.serializers import ResourcesSerializer
from azure_blob_utils import upload_file


def _get_first(data: Mapping[str, Any], key: str, default: Any = None) -> Any:
    if hasattr(data, "get"):
        return data.get(key, default)
    return default


def _get_list(data: Mapping[str, Any], key: str) -> list[Any]:
    if hasattr(data, "getlist"):
        return [value for value in data.getlist(key) if value not in ("", None)]

    value = data.get(key) if hasattr(data, "get") else None
    if value in ("", None):
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item not in ("", None)]
    return [value]


def _to_int_or_none(value: Any) -> int | None:
    if value in ("", None):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _visibility_scope(value: Any, *, track_id: int | None, role_ids: list[Any]) -> str:
    legacy_map = {
        "global": Resources.VisibilityScope.PUBLIC,
        "track_based": Resources.VisibilityScope.TRACK,
        "role_based": Resources.VisibilityScope.ROLE,
    }
    if value in legacy_map:
        return legacy_map[value]
    if value in {choice[0] for choice in Resources.VisibilityScope.choices}:
        return value
    if role_ids:
        return Resources.VisibilityScope.ROLE
    if track_id is not None:
        return Resources.VisibilityScope.TRACK
    return Resources.VisibilityScope.PUBLIC


def _storage_key(resource_id: int, file_name: str | None) -> str:
    stamp = int(timezone.now().timestamp() * 1000)
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file_name or "resource.bin")
    return f"resources/{stamp}-{resource_id}-{safe_name}"


def _resource_type_id(data: Mapping[str, Any]) -> int | None:
    explicit_type_id = _to_int_or_none(_get_first(data, "resource_type_id"))
    if explicit_type_id is not None:
        return explicit_type_id

    resource_type = _get_first(data, "resource_type")
    if not resource_type:
        return None

    return ResourceType.objects.filter(type_name__iexact=str(resource_type)).values_list(
        "id",
        flat=True,
    ).first()


@transaction.atomic
def upload_resource_file(*, data: Mapping[str, Any], files: Mapping[str, Any], user) -> Resources:
    """Create a file resource from multipart admin upload data."""
    uploaded_file = _get_first(files, "file")
    if uploaded_file is None:
        raise ValueError("No file was uploaded.")

    role_ids = _get_list(data, "role_ids")
    track_id = _to_int_or_none(_get_first(data, "track_id"))
    group_id = _to_int_or_none(_get_first(data, "group_id"))
    type_id = _resource_type_id(data)

    serializer_data: dict[str, Any] = {
        "name": _get_first(data, "name") or _get_first(data, "resource_name"),
        "description": _get_first(data, "description")
        or _get_first(data, "resource_description"),
        "kind": Resources.ResourceKind.FILE,
        "file_mime_type": getattr(uploaded_file, "content_type", None)
        or "application/octet-stream",
        "file_size": getattr(uploaded_file, "size", None),
        "visibility_scope": _visibility_scope(
            _get_first(data, "visibility_scope"),
            track_id=track_id,
            role_ids=role_ids,
        ),
    }

    if type_id is not None:
        serializer_data["type_id"] = type_id
    if track_id is not None:
        serializer_data["track"] = track_id
    if group_id is not None:
        serializer_data["group"] = group_id
    if role_ids:
        serializer_data["role_ids"] = role_ids

    serializer = ResourcesSerializer(data=serializer_data)
    serializer.is_valid(raise_exception=True)
    resource = serializer.save(uploaded_by=user)

    storage_key = _storage_key(resource.id, getattr(uploaded_file, "name", None))
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp.flush()
        try:
            upload_file(tmp.name, storage_key)
        finally:
            os.unlink(tmp.name)

    resource.storage_key = storage_key
    resource.save(update_fields=["storage_key"])

    log_audit_event(
        actor=user,
        entity_type="resource",
        entity_id=resource.id,
        action="create",
        after_state=ResourcesSerializer(resource).data,
    )

    return resource
