from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.resources.models import ResourceType, Resources
from apps.common.storage import get_resource_storage


User = get_user_model()


class ResourceFileTransferTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="uploader@test.com",
            password="pass123",
            first_name="Upload",
            last_name="User",
            is_staff=True,
        )
        self.non_admin = User.objects.create_user(
            email="reader@test.com",
            password="pass123",
        )
        self.client.force_authenticate(user=self.user)
        self.resource_type = ResourceType.objects.create(
            type_name="document",
            type_description="Document resources",
        )
        self.created_storage_keys = []
        self.storage = get_resource_storage()

    def tearDown(self):
        for storage_key in self.created_storage_keys:
            if storage_key and self.storage.exists(storage_key):
                self.storage.delete(storage_key)

    def _upload_resource(self):
        upload = SimpleUploadedFile(
            "Program Guide.pdf",
            b"program guide payload",
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("resource-files-list"),
            {
                "name": "Program Guide",
                "description": "Current mentoring guide",
                "type_id": str(self.resource_type.id),
                "visibility_scope": Resources.VisibilityScope.PUBLIC,
                "uploaded_file": upload,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        resource = Resources.objects.get(pk=response.data["id"])
        self.created_storage_keys.append(resource.storage_key)
        return response, resource

    def test_create_resource_with_uploaded_file_stores_managed_file(self):
        response, resource = self._upload_resource()

        self.assertEqual(response.data["name"], "Program Guide")
        self.assertEqual(response.data["storage_status"], "managed_key")
        self.assertIsNotNone(response.data["download_url"])
        self.assertEqual(response.data["file_mime_type"], "application/pdf")
        self.assertEqual(response.data["file_size"], len(b"program guide payload"))
        self.assertTrue(self.storage.exists(resource.storage_key))

    def test_non_admin_cannot_upload_resource_file(self):
        self.client.force_authenticate(user=self.non_admin)
        upload = SimpleUploadedFile(
            "Program Guide.pdf",
            b"program guide payload",
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("resource-files-list"),
            {
                "name": "Program Guide",
                "description": "Current mentoring guide",
                "type_id": str(self.resource_type.id),
                "visibility_scope": Resources.VisibilityScope.PUBLIC,
                "uploaded_file": upload,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_access_and_download_work_for_managed_file_uploads(self):
        _, resource = self._upload_resource()

        access_response = self.client.get(reverse("resource-files-access", kwargs={"pk": resource.id}))
        self.assertEqual(access_response.status_code, status.HTTP_200_OK)
        self.assertEqual(access_response.data["access_mode"], "managed_file")
        self.assertTrue(access_response.data["download_url"].endswith(reverse("resource-files-download", kwargs={"pk": resource.id})))

        download_response = self.client.get(reverse("resource-files-download", kwargs={"pk": resource.id}))
        self.assertEqual(download_response.status_code, status.HTTP_200_OK)
        self.assertEqual(download_response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", download_response["Content-Disposition"])
        self.assertEqual(b"".join(download_response.streaming_content), b"program guide payload")
