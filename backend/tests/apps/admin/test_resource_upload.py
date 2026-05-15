from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.test import TestCase
from unittest.mock import patch

from apps.resources.models import ResourceAudience, Resources, Roles
from apps.users.models import AdminScope


class AdminResourceUploadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = get_user_model().objects.create_user(
            email="admin@example.com",
            password="testpass123",
            first_name="Admin",
            last_name="User",
            is_staff=True,
        )
        AdminScope.objects.create(user=self.admin_user, is_global=True)
        self.client.force_authenticate(user=self.admin_user)
        self.role = Roles.objects.create(role_name="Student")

    @patch("apps.resources.services.upload.upload_file")
    def test_admin_resource_upload_uses_resources_package(self, upload_file_mock):
        upload = SimpleUploadedFile(
            "guide.pdf",
            b"test file content",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("resource-upload"),
            {
                "file": upload,
                "resource_name": "Admin Upload",
                "resource_description": "Uploaded through admin v1",
                "visibility_scope": "role_based",
                "role_ids": [str(self.role.id)],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["resource_name"], "Admin Upload")
        self.assertEqual(response.data["data"]["visibility_scope"], "role_based")

        resource = Resources.objects.get(name="Admin Upload")
        self.assertEqual(resource.uploaded_by, self.admin_user)
        self.assertEqual(resource.kind, Resources.ResourceKind.FILE)
        self.assertEqual(resource.file_mime_type, "application/pdf")
        self.assertEqual(resource.file_size, len(b"test file content"))
        self.assertEqual(resource.visibility_scope, Resources.VisibilityScope.ROLE)
        self.assertTrue(resource.storage_key.endswith("-guide.pdf"))
        self.assertTrue(
            ResourceAudience.objects.filter(resource=resource, role=self.role).exists()
        )
        upload_file_mock.assert_called_once()

    def test_admin_resource_upload_requires_file(self):
        response = self.client.post(
            reverse("resource-upload"),
            {
                "resource_name": "Missing File",
                "resource_description": "No file attached",
                "visibility_scope": "global",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "No file was uploaded.")

    @patch("apps.admin.services.resource.download_file_text")
    @patch("apps.admin.services.resource.upload_file")
    def test_admin_page_resource_returns_content_html(
        self,
        upload_file_mock,
        download_file_text_mock,
    ):
        download_file_text_mock.return_value = "<p>Hello page</p>"

        response = self.client.post(
            reverse("resource-list-create"),
            {
                "resource_kind": "page",
                "resource_name": "Admin Page",
                "resource_description": "Rendered in the admin detail drawer",
                "visibility_scope": "role_based",
                "role_ids": [self.role.id],
                "content_html": "<p>Hello page</p>",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["resource_kind"], "page")
        self.assertEqual(response.data["data"]["content_html"], "<p>Hello page</p>")

        resource = Resources.objects.get(name="Admin Page")
        self.assertEqual(resource.file_mime_type, "text/html")
        self.assertEqual(resource.file_size, len(b"<p>Hello page</p>"))
        upload_file_mock.assert_called_once()
        download_file_text_mock.assert_called_once_with(resource.storage_key)

    @patch("apps.admin.services.resource.download_file_text")
    def test_admin_page_resource_detail_reads_stored_content_html(
        self,
        download_file_text_mock,
    ):
        download_file_text_mock.return_value = "<h1>Stored page</h1>"
        resource = Resources.objects.create(
            name="Stored Page",
            description="Existing page resource",
            kind=Resources.ResourceKind.PAGE,
            uploaded_by=self.admin_user,
            storage_key="resources/stored-page.html",
            file_mime_type="text/html",
            file_size=20,
        )

        response = self.client.get(reverse("resource-detail", args=[resource.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["content_html"], "<h1>Stored page</h1>")
        download_file_text_mock.assert_called_once_with("resources/stored-page.html")

    @patch("apps.admin.services.resource.download_file_bytes")
    def test_admin_page_resource_download_returns_html_attachment(
        self,
        download_file_bytes_mock,
    ):
        download_file_bytes_mock.return_value = b"<h1>Download me</h1>"
        resource = Resources.objects.create(
            name="Download Page",
            description="Existing page resource",
            kind=Resources.ResourceKind.PAGE,
            uploaded_by=self.admin_user,
            storage_key="resources/1778844292421-17-test.html",
            file_mime_type="text/html",
            file_size=20,
        )

        response = self.client.get(reverse("resource-download", args=[resource.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/html")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="test.html"',
        )
        self.assertEqual(response.content, b"<h1>Download me</h1>")
        download_file_bytes_mock.assert_called_once_with(resource.storage_key)
