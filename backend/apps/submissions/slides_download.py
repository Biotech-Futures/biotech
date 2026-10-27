"""Finalist slides, downloaded under one name everywhere: "2026_BTF01_Slides.pptx",
as Grading names its files. Served here rather than by the shared helpers,
which lower-case the name."""
from __future__ import annotations

import logging
import os

from django.http import FileResponse, HttpResponseRedirect, JsonResponse

from apps.common.filenames import safe_name
from apps.common.storage import get_slides_storage

logger = logging.getLogger(__name__)


def slides_download_name(group, stored: dict) -> str:
    """"2026_BTF01_Slides.pptx": the team's year and name, the uploaded file's extension."""
    extension = os.path.splitext(stored.get("name") or stored.get("storage_key") or "")[1].lower()
    return f"{group.year}_{safe_name(group.group_name)}_Slides{extension}"


def serve_slides(storage_key: str, filename: str, *, mime: str | None, as_attachment: bool):
    """The file as ``filename``: on Azure a short-lived signed link straight to it, else streamed."""
    storage = get_slides_storage()
    if storage.is_remote:
        parameters = {"content_disposition": f'{"attachment" if as_attachment else "inline"}; filename="{filename}"'}
        if mime:
            parameters["content_type"] = mime
        try:
            return HttpResponseRedirect(storage.backend.url(storage_key, parameters=parameters))
        except Exception:  # noqa: BLE001 - streaming it instead still works
            logger.exception("slides_download.sign_failed key=%s", storage_key)
    try:
        handle = storage.open(storage_key)
    except Exception:  # noqa: BLE001 - a missing file is a 404, not a 500
        return JsonResponse({"detail": "The stored file could not be opened for download."}, status=404)
    return FileResponse(handle, as_attachment=as_attachment, filename=filename, content_type=mime)
