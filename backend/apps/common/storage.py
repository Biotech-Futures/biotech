from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, HttpResponseRedirect, JsonResponse
from django.utils import timezone

from apps.common.filenames import sanitize_upload_filename

try:
    from storages.backends.azure_storage import AzureStorage as _REAL_AZURE_STORAGE
except ImportError:  # pragma: no cover - only raised when deps are missing.
    _REAL_AZURE_STORAGE = None
    AzureStorage = type("AzureStorage", (), {})
else:
    AzureStorage = _REAL_AZURE_STORAGE


class _BaseAzureContainerStorage(AzureStorage):
    container_setting_name = ""

    def __init__(self, *args, **kwargs):
        if _REAL_AZURE_STORAGE is None:  # pragma: no cover - protected by dependency install.
            raise ImproperlyConfigured(
                "django-storages must be installed to use Azure Blob managed storage."
            )
        kwargs.setdefault("azure_container", getattr(settings, self.container_setting_name))
        kwargs.setdefault("expiration_secs", settings.AZURE_URL_EXPIRATION_SECS)
        kwargs.setdefault("custom_domain", settings.AZURE_CUSTOM_DOMAIN or None)
        super().__init__(*args, **kwargs)


class ResourceAzureStorage(_BaseAzureContainerStorage):
    container_setting_name = "AZURE_RESOURCE_CONTAINER"


class ChatAzureStorage(_BaseAzureContainerStorage):
    container_setting_name = "AZURE_CHAT_CONTAINER"


class LocalContainerStorage(FileSystemStorage):
    def __init__(self, namespace: str):
        media_root = Path(getattr(settings, "MEDIA_ROOT", Path(settings.BASE_DIR) / "media"))
        media_url = getattr(settings, "MEDIA_URL", "/media/").rstrip("/") + "/"
        super().__init__(
            location=media_root / namespace,
            base_url=f"{media_url}{namespace}/",
        )


class ManagedContainerStorage:
    def __init__(self, namespace: str, azure_storage_cls):
        self.namespace = namespace
        self._azure_storage_cls = azure_storage_cls
        self._storage = self._build_storage()

    def _build_storage(self):
        # The namespace stays stable across local and Azure backends so callers do not
        # need different path logic for dev/test versus deploy.
        if not getattr(settings, "USE_AZURE_BLOB_STORAGE", False):
            return LocalContainerStorage(self.namespace)
        return self._azure_storage_cls()

    @property
    def backend(self):
        return self._storage

    @property
    def is_remote(self) -> bool:
        return bool(
            _REAL_AZURE_STORAGE is not None and isinstance(self._storage, _REAL_AZURE_STORAGE)
        )

    def save(self, name, content):
        return self._storage.save(name, content)

    def exists(self, name: str) -> bool:
        return self._storage.exists(name)

    def delete(self, name: str) -> None:
        self._storage.delete(name)

    def open(self, name: str, mode: str = "rb"):
        return self._storage.open(name, mode)

    def url(
        self,
        name: str,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        as_attachment: bool = False,
    ) -> str:
        if not self.is_remote:
            return self._storage.url(name)

        # Azure signed URLs can carry response headers, which lets the backend keep
        # browser download behavior consistent without proxying the file bytes itself.
        parameters = {}
        if content_type:
            parameters["content_type"] = content_type
        if filename:
            disposition = "attachment" if as_attachment else "inline"
            safe_filename = sanitize_upload_filename(filename)
            parameters["content_disposition"] = f'{disposition}; filename="{safe_filename}"'
        elif as_attachment:
            safe_filename = sanitize_upload_filename(Path(name).name)
            parameters["content_disposition"] = f'attachment; filename="{safe_filename}"'

        return self._storage.url(name, parameters=parameters or None)


class ManagedFileService:
    def __init__(self, storage_factory: Callable[[], ManagedContainerStorage]):
        self._storage_factory = storage_factory

    def _storage(self) -> ManagedContainerStorage:
        return self._storage_factory()

    def build_storage_name(self, original_name: str | None) -> str:
        # Developer note: this helper centralizes shared file mechanics, but callers
        # still choose the resource-vs-chat container by passing a storage factory.
        safe_name = sanitize_upload_filename(original_name)
        day = timezone.now().strftime("%Y/%m/%d")
        return f"{day}/{uuid4().hex}/{safe_name}"

    def save_uploaded_file(
        self,
        uploaded_file,
        *,
        content_type_field: str,
        size_field: str,
        original_filename_field: str | None = None,
    ) -> dict:
        storage_name = self.build_storage_name(getattr(uploaded_file, "name", ""))
        saved_name = self._storage().save(storage_name, uploaded_file)
        file_data = {
            "storage_key": saved_name,
            content_type_field: getattr(uploaded_file, "content_type", None) or None,
            size_field: getattr(uploaded_file, "size", None),
        }
        if original_filename_field:
            file_data[original_filename_field] = sanitize_upload_filename(
                getattr(uploaded_file, "name", None)
            )
        return file_data

    def delete(self, storage_key: str | None) -> None:
        if not storage_key:
            return
        storage = self._storage()
        if storage.exists(storage_key):
            storage.delete(storage_key)

    def resolve_url(
        self,
        storage_key: str | None,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        as_attachment: bool = False,
    ):
        if not storage_key:
            return None
        try:
            return self._storage().url(
                storage_key,
                filename=filename,
                content_type=content_type,
                as_attachment=as_attachment,
            )
        except Exception:
            return None

    def open(self, storage_key: str, mode: str = "rb"):
        return self._storage().open(storage_key, mode)


def serve_managed_file(
    *,
    resolve_url: Callable[..., str | None],
    open_file: Callable[[str], object],
    storage_key: str,
    filename: str,
    mime_type: str | None,
    size: int | None,
    as_attachment: bool,
    on_open_failure_status: int = 404,
    on_open_failure_detail: str = "The stored file could not be opened for download.",
):
    safe_filename = sanitize_upload_filename(filename)
    managed_url = resolve_url(
        storage_key,
        filename=safe_filename,
        content_type=mime_type,
        as_attachment=as_attachment,
    )
    # Remote Azure storage returns a signed URL, while local/test storage
    # falls back to app-streamed bytes through Django.
    if managed_url:
        parsed_url = urlparse(managed_url)
        if parsed_url.scheme and parsed_url.netloc:
            return HttpResponseRedirect(managed_url)

    try:
        file_handle = open_file(storage_key)
    except Exception:
        return JsonResponse(
            {"detail": on_open_failure_detail},
            status=on_open_failure_status,
        )

    response = FileResponse(
        file_handle,
        as_attachment=as_attachment,
        filename=safe_filename,
    )
    if mime_type:
        response["Content-Type"] = mime_type
    if size is not None:
        response["Content-Length"] = str(size)
    return response


@lru_cache(maxsize=2)
def get_resource_storage() -> ManagedContainerStorage:
    return ManagedContainerStorage("resources", ResourceAzureStorage)


@lru_cache(maxsize=2)
def get_chat_storage() -> ManagedContainerStorage:
    return ManagedContainerStorage("chat", ChatAzureStorage)
