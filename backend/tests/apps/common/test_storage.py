from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from unittest.mock import patch

from apps.chat.utils import reset_pattern_cache
from apps.common.storage import (
    ManagedFileService,
    ResourceAzureStorage,
    get_chat_storage,
    reset_managed_storage_caches,
    serve_managed_file,
)


class _FakeManagedStorage:
    def __init__(self):
        self.saved_names = []
        self.deleted_names = []
        self.url_calls = []

    def save(self, name, content):
        self.saved_names.append(name)
        return name

    def exists(self, name):
        return bool(name)

    def delete(self, name):
        self.deleted_names.append(name)

    def url(self, name, *, filename=None, content_type=None, as_attachment=False):
        self.url_calls.append(
            {
                "name": name,
                "filename": filename,
                "content_type": content_type,
                "as_attachment": as_attachment,
            }
        )
        return f"https://example.test/{name}"


@override_settings(CHAT_SANITIZER_BLACKLIST=["badword*"])
class ManagedFileServiceTests(SimpleTestCase):
    def setUp(self):
        reset_pattern_cache()
        reset_managed_storage_caches()
        self.storage = _FakeManagedStorage()
        self.service = ManagedFileService(lambda: self.storage)

    def tearDown(self):
        reset_managed_storage_caches()
        reset_pattern_cache()

    def test_save_uploaded_file_returns_sanitized_metadata(self):
        uploaded_file = SimpleUploadedFile(
            "<script>badword.PDF",
            b"payload",
            content_type="application/pdf",
        )

        saved = self.service.save_uploaded_file(
            uploaded_file,
            original_filename_field="attachment_filename",
            content_type_field="attachment_mime_type",
            size_field="attachment_size",
        )

        self.assertEqual(saved["attachment_filename"], "redacted.pdf")
        self.assertEqual(saved["attachment_mime_type"], "application/pdf")
        self.assertEqual(saved["attachment_size"], len(b"payload"))
        self.assertTrue(saved["storage_key"].endswith("/redacted.pdf"))

    def test_delete_and_resolve_url_delegate_to_storage_backend(self):
        managed_url = self.service.resolve_url(
            "2026/05/08/example/report.pdf",
            filename="report.pdf",
            content_type="application/pdf",
            as_attachment=True,
        )
        self.service.delete("2026/05/08/example/report.pdf")

        self.assertEqual(
            managed_url,
            "https://example.test/2026/05/08/example/report.pdf",
        )
        self.assertEqual(
            self.storage.url_calls,
            [
                {
                    "name": "2026/05/08/example/report.pdf",
                    "filename": "report.pdf",
                    "content_type": "application/pdf",
                    "as_attachment": True,
                }
            ],
        )
        self.assertEqual(
            self.storage.deleted_names,
            ["2026/05/08/example/report.pdf"],
        )

    def test_resource_azure_storage_raises_if_django_storages_is_unavailable(self):
        with patch("apps.common.storage._REAL_AZURE_STORAGE", None):
            with self.assertRaises(ImproperlyConfigured):
                ResourceAzureStorage()

    def test_reset_managed_storage_caches_rebuilds_cached_storage_instances(self):
        first = get_chat_storage()
        second = get_chat_storage()

        self.assertIs(first, second)

        reset_managed_storage_caches()
        rebuilt = get_chat_storage()

        self.assertIsNot(first, rebuilt)

    def test_serve_managed_file_redirects_streams_and_reports_open_failures(self):
        redirect_response = serve_managed_file(
            resolve_url=lambda *args, **kwargs: "https://blob.example.test/report.pdf?sig=abc",
            open_file=lambda storage_key: BytesIO(b"unused"),
            storage_key="2026/05/08/example/report.pdf",
            filename="report.pdf",
            mime_type="application/pdf",
            size=7,
            as_attachment=True,
        )
        self.assertEqual(redirect_response.status_code, 302)

        streamed_response = serve_managed_file(
            resolve_url=lambda *args, **kwargs: "/media/resources/report.pdf",
            open_file=lambda storage_key: BytesIO(b"payload"),
            storage_key="2026/05/08/example/report.pdf",
            filename="report.pdf",
            mime_type="application/pdf",
            size=7,
            as_attachment=True,
        )
        self.assertEqual(streamed_response.status_code, 200)
        self.assertEqual(streamed_response["Content-Type"], "application/pdf")
        self.assertEqual(streamed_response["Content-Length"], "7")

        failed_response = serve_managed_file(
            resolve_url=lambda *args, **kwargs: None,
            open_file=lambda storage_key: (_ for _ in ()).throw(FileNotFoundError("missing")),
            storage_key="2026/05/08/example/report.pdf",
            filename="report.pdf",
            mime_type="application/pdf",
            size=7,
            as_attachment=True,
            on_open_failure_detail="missing",
        )
        self.assertEqual(failed_response.status_code, 404)
        self.assertJSONEqual(failed_response.content, {"detail": "missing"})
