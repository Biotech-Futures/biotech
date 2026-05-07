from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from apps.chat.utils import reset_pattern_cache
from apps.common.storage import ManagedFileService


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
        self.storage = _FakeManagedStorage()
        self.service = ManagedFileService(lambda: self.storage)

    def tearDown(self):
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
