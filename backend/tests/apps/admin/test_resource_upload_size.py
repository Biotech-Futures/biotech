"""RS5: soft upload size limit, and full validation on file replace.

A file over RESOURCE_FILE_MAX_UPLOAD_SIZE is accepted only with
acknowledged_oversized=true. The flag bypasses the size check only: the type
allow-list and the executable-signature check always run. Replacing a file
goes through the same checks as a new upload, before anything is stored.
"""
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework import serializers, status
from rest_framework.test import APIClient

from apps.common.storage import get_resource_storage
from apps.common.upload_validation import is_truthy_flag, validate_uploaded_file
from apps.resources.models import Resources, Roles
from apps.users.models import AdminScope
from tests.apps._helpers import StorageCleanupMixin

User = get_user_model()

MAX_SIZE = 16
SMALL_PDF = b"%PDF-1.4 small"          # 14 bytes: under the limit
LARGE_PDF = b"%PDF-1.4 " + b"x" * 40    # 49 bytes: over the limit


def _file(name, content, content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


class UploadValidationFlagTests(SimpleTestCase):
    def _validate(self, uploaded_file, **kwargs):
        return validate_uploaded_file(
            uploaded_file,
            max_size=MAX_SIZE,
            allowed_extensions=("pdf",),
            allowed_mime_types=("application/pdf",),
            field_label="Resource file",
            **kwargs,
        )

    def test_oversized_rejected_without_acknowledgement(self):
        with self.assertRaisesMessage(serializers.ValidationError, "maximum allowed size"):
            self._validate(_file("big.pdf", LARGE_PDF))

    def test_acknowledgement_bypasses_size_only(self):
        self._validate(_file("big.pdf", LARGE_PDF), acknowledged_oversized=True)
        with self.assertRaisesMessage(serializers.ValidationError, "allowed file extension"):
            self._validate(_file("big.zip", LARGE_PDF, "application/zip"), acknowledged_oversized=True)
        with self.assertRaisesMessage(serializers.ValidationError, "executable signature"):
            self._validate(_file("big.pdf", b"MZ" + LARGE_PDF), acknowledged_oversized=True)

    def test_is_truthy_flag(self):
        for value in (True, "true", "TRUE", " True ", "1", "yes", "on"):
            self.assertTrue(is_truthy_flag(value), value)
        for value in (False, "false", "False", "0", "no", "", None):
            self.assertFalse(is_truthy_flag(value), value)


@override_settings(RESOURCE_FILE_MAX_UPLOAD_SIZE=MAX_SIZE)
class AdminUploadSizeTests(StorageCleanupMixin, TestCase):
    storage_attr = "storage"
    storage_keys_attr = "created_storage_keys"

    def setUp(self):
        self.client = APIClient()
        self.storage = get_resource_storage()
        self.created_storage_keys = []
        self.admin_user = User.objects.create_user(
            email="admin@upload-size.test", password="pass123",
            first_name="Admin", last_name="User",
        )
        AdminScope.objects.create(user=self.admin_user)
        self.client.force_authenticate(user=self.admin_user)
        self.role = Roles.objects.create(role_name="student")

    def _create(self, upload, **fields):
        response = self.client.post(
            reverse("admin_api:resource-upload"),
            {
                "file": upload,
                "resource_name": fields.pop("resource_name", "Sized Upload"),
                "resource_description": "Upload size test",
                "role_ids": [str(self.role.id)],
                **fields,
            },
            format="multipart",
        )
        if response.status_code == status.HTTP_201_CREATED:
            resource = Resources.objects.get(id=response.data["data"]["id"])
            self.created_storage_keys.append(resource.storage_key)
        return response

    # --- create -----------------------------------------------------------

    def test_create_oversized_without_flag_is_rejected(self):
        response = self._create(_file("big.pdf", LARGE_PDF))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Resources.objects.filter(name="Sized Upload").exists())

    def test_create_oversized_with_false_flag_is_rejected(self):
        response = self._create(_file("big.pdf", LARGE_PDF), acknowledged_oversized="false")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_oversized_with_flag_is_accepted(self):
        response = self._create(_file("big.pdf", LARGE_PDF), acknowledged_oversized="true")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        resource = Resources.objects.get(name="Sized Upload")
        self.assertEqual(resource.file_size, len(LARGE_PDF))

    def test_create_disallowed_extension_rejected_even_with_flag(self):
        response = self._create(
            _file("bundle.zip", LARGE_PDF, "application/zip"), acknowledged_oversized="true"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Resources.objects.filter(name="Sized Upload").exists())

    def test_resource_files_api_accepts_flag(self):
        # The DRF endpoint's serializer reads the flag from a QueryDict.
        response = self.client.post(
            reverse("resource-files-list"),
            {
                "name": "Api Big File",
                "description": "Via resource-files",
                "role_ids": [str(self.role.id)],
                "uploaded_file": _file("big.pdf", LARGE_PDF),
                "acknowledged_oversized": "true",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.created_storage_keys.append(Resources.objects.get(id=response.data["id"]).storage_key)

    # --- replace ----------------------------------------------------------

    def _existing_resource(self):
        response = self._create(_file("original.pdf", SMALL_PDF), resource_name="Replaceable")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Resources.objects.get(name="Replaceable")

    def _replace(self, resource, upload, **fields):
        return self.client.post(
            reverse("admin_api:resource-file-replace", args=[resource.id]),
            {"file": upload, **fields},
            format="multipart",
        )

    def _mock_storage(self, get_resource_storage_mock):
        stored = {}
        storage = Mock()

        def fake_save(name, content):
            stored["bytes"] = content.read()
            return name

        storage.save.side_effect = fake_save
        get_resource_storage_mock.return_value = storage
        return storage, stored

    @patch("apps.admin.services.resource.get_resource_storage")
    def test_replace_oversized_without_flag_is_rejected(self, get_resource_storage_mock):
        resource = self._existing_resource()
        storage, _ = self._mock_storage(get_resource_storage_mock)

        response = self._replace(resource, _file("big.pdf", LARGE_PDF))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # A readable reason, not a dict, so the admin form can show it.
        self.assertIsInstance(response.data["msg"], str)
        self.assertIn("maximum allowed size", response.data["msg"])
        storage.save.assert_not_called()
        resource.refresh_from_db()
        self.assertEqual(resource.file_size, len(SMALL_PDF))

    @patch("apps.admin.services.resource.get_resource_storage")
    def test_replace_oversized_with_flag_is_accepted(self, get_resource_storage_mock):
        resource = self._existing_resource()
        _, stored = self._mock_storage(get_resource_storage_mock)

        response = self._replace(
            resource, _file("big.pdf", LARGE_PDF), acknowledged_oversized="true"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(stored["bytes"], LARGE_PDF)
        resource.refresh_from_db()
        self.assertEqual(resource.file_size, len(LARGE_PDF))

    @patch("apps.admin.services.resource.get_resource_storage")
    def test_replace_disallowed_extension_rejected_even_with_flag(self, get_resource_storage_mock):
        resource = self._existing_resource()
        storage, _ = self._mock_storage(get_resource_storage_mock)

        response = self._replace(
            resource, _file("bundle.zip", SMALL_PDF, "application/zip"),
            acknowledged_oversized="true",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("allowed file extension", response.data["msg"])
        storage.save.assert_not_called()

    @patch("apps.admin.services.resource.get_resource_storage")
    def test_replace_executable_signature_is_rejected(self, get_resource_storage_mock):
        resource = self._existing_resource()
        storage, _ = self._mock_storage(get_resource_storage_mock)

        # Named and typed as a PDF, but the bytes start like a Windows .exe.
        response = self._replace(resource, _file("slides.pdf", b"MZ\x90\x00fake"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("executable signature", response.data["msg"])
        storage.save.assert_not_called()
        resource.refresh_from_db()
        self.assertEqual(resource.file_size, len(SMALL_PDF))

    @patch("apps.admin.services.resource.get_resource_storage")
    def test_replace_normal_valid_file_still_works(self, get_resource_storage_mock):
        resource = self._existing_resource()
        _, stored = self._mock_storage(get_resource_storage_mock)

        response = self._replace(resource, _file("updated.pdf", b"%PDF-1.4 new"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(stored["bytes"], b"%PDF-1.4 new")
        resource.refresh_from_db()
        self.assertEqual(resource.file_size, len(b"%PDF-1.4 new"))
        self.assertEqual(resource.file_mime_type, "application/pdf")
