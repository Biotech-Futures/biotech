from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.test import TestCase, override_settings
from unittest.mock import Mock, patch

from apps.groups.models import Countries, CountryStates, Tracks
from apps.resources.models import ResourceAudience, Resources, ResourceType, Roles
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

    def _mock_blob_service(self, blob_service_client_mock, chunks, content_type):
        download_stream = Mock()
        download_stream.chunks.return_value = chunks
        download_stream.readall.return_value = b"".join(chunks)
        blob_properties = Mock()
        blob_properties.content_settings.content_type = content_type
        blob_properties.size = sum(len(chunk) for chunk in chunks)

        blob_client = Mock()
        blob_client.exists.return_value = True
        blob_client.get_blob_properties.return_value = blob_properties
        blob_client.download_blob.return_value = download_stream

        container_client = Mock()
        container_client.get_blob_client.return_value = blob_client

        blob_service = Mock()
        blob_service.get_container_client.return_value = container_client
        blob_service_client_mock.from_connection_string.return_value = blob_service
        blob_service_client_mock.return_value = blob_service
        return container_client, blob_client

    def test_admin_resource_upload_uses_resources_package(self):
        upload = SimpleUploadedFile(
            "guide.pdf",
            b"test file content",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("admin_api:resource-upload"),
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
        self.assertTrue(resource.storage_key.endswith("/guide.pdf"))
        self.assertTrue(
            ResourceAudience.objects.filter(resource=resource, role=self.role).exists()
        )

    def test_admin_resource_upload_requires_file(self):
        response = self.client.post(
            reverse("admin_api:resource-upload"),
            {
                "resource_name": "Missing File",
                "resource_description": "No file attached",
                "visibility_scope": "global",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "No file was uploaded.")

    def test_resource_upload_preserves_attachment_kind(self):
        upload = SimpleUploadedFile(
            "brief.pdf",
            b"attached file content",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("admin_api:resource-upload"),
            {
                "file": upload,
                "resource_kind": "attachment",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["resource_kind"], "attachment")

        resource = Resources.objects.get(name="brief.pdf")
        self.assertEqual(resource.kind, Resources.ResourceKind.ATTACHMENT)
        self.assertEqual(resource.file_mime_type, "application/pdf")
        self.assertEqual(resource.file_size, len(b"attached file content"))

    @patch("apps.admin.services.resource.BlobServiceClient")
    def test_resource_file_access_streams_uploaded_file(
        self,
        blob_service_client_mock,
    ):
        upload = SimpleUploadedFile(
            "brief.pdf",
            b"attached file content",
            content_type="application/pdf",
        )
        upload_response = self.client.post(
            reverse("admin_api:resource-upload"),
            {
                "file": upload,
                "resource_name": "Brief",
                "resource_description": "A brief file",
            },
            format="multipart",
        )
        resource_id = upload_response.data["data"]["id"]
        self._mock_blob_service(
            blob_service_client_mock,
            [b"attached file content"],
            "application/pdf",
        )

        response = self.client.get(reverse("admin_api:resource-access", args=[resource_id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Content-Disposition"], 'inline; filename="brief.pdf"')
        self.assertEqual(response["Content-Length"], str(len(b"attached file content")))
        self.assertEqual(b"".join(response.streaming_content), b"attached file content")

    @patch("apps.admin.services.resource.download_file_bytes")
    def test_resource_file_download_uses_original_file_extension(
        self,
        download_file_bytes_mock,
    ):
        download_file_bytes_mock.return_value = b"attached file content"
        upload = SimpleUploadedFile(
            "brief.pdf",
            b"attached file content",
            content_type="application/pdf",
        )
        upload_response = self.client.post(
            reverse("admin_api:resource-upload"),
            {
                "file": upload,
                "resource_name": "Brief",
                "resource_description": "A brief file",
            },
            format="multipart",
        )
        resource_id = upload_response.data["data"]["id"]

        response = self.client.get(
            reverse("admin_api:resource-download", args=[resource_id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('filename="brief.pdf"', response["Content-Disposition"])

    @patch("apps.admin.services.resource.download_file_bytes")
    def test_resource_file_download_supports_inline_query_param(
        self,
        download_file_bytes_mock,
    ):
        # ``?inline=1`` lets the admin UI preview PDFs in a tab using the
        # same query convention as the user-facing resource endpoint.
        download_file_bytes_mock.return_value = b"attached file content"
        upload = SimpleUploadedFile(
            "brief.pdf",
            b"attached file content",
            content_type="application/pdf",
        )
        upload_response = self.client.post(
            reverse("admin_api:resource-upload"),
            {
                "file": upload,
                "resource_name": "Brief",
                "resource_description": "A brief file",
            },
            format="multipart",
        )
        resource_id = upload_response.data["data"]["id"]

        response = self.client.get(
            reverse("admin_api:resource-download", args=[resource_id]),
            {"inline": "1"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(
            response["Content-Disposition"], 'inline; filename="brief.pdf"'
        )

    def test_admin_page_resource_returns_content_html(self):
        response = self.client.post(
            reverse("admin_api:resource-list-create"),
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
        self.assertTrue(resource.storage_key.endswith("/admin-page.html"))

    def test_admin_page_resource_detail_reads_stored_content_html(self):
        create_response = self.client.post(
            reverse("admin_api:resource-list-create"),
            {
                "resource_kind": "page",
                "resource_name": "Stored Page",
                "resource_description": "Existing page resource",
                "visibility_scope": "role_based",
                "role_ids": [self.role.id],
                "content_html": "<h1>Stored page</h1>",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        resource_id = create_response.data["data"]["id"]

        response = self.client.get(reverse("admin_api:resource-detail", args=[resource_id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["content_html"], "<h1>Stored page</h1>")

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

        response = self.client.get(reverse("admin_api:resource-download", args=[resource.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/html")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="test.html"',
        )
        self.assertEqual(response.content, b"<h1>Download me</h1>")
        download_file_bytes_mock.assert_called_once_with(resource.storage_key)

    @patch("apps.admin.services.resource.BlobServiceClient")
    def test_admin_page_resource_access_streams_inline_content(
        self,
        blob_service_client_mock,
    ):
        container_client, blob_client = self._mock_blob_service(
            blob_service_client_mock,
            [b"<h1>Open ", b"me</h1>"],
            "text/html",
        )
        resource = Resources.objects.create(
            name="Access Page",
            description="Existing page resource",
            kind=Resources.ResourceKind.PAGE,
            uploaded_by=self.admin_user,
            storage_key="resources/1778844292421-18-open.html",
            file_mime_type="text/html",
            file_size=16,
        )

        response = self.client.get(reverse("admin_api:resource-access", args=[resource.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/html")
        self.assertEqual(response["Content-Disposition"], 'inline; filename="open.html"')
        self.assertEqual(response["Cache-Control"], "private, max-age=300")
        self.assertEqual(response["Content-Length"], "16")
        self.assertEqual(b"".join(response.streaming_content), b"<h1>Open me</h1>")
        container_client.get_blob_client.assert_called_once_with(resource.storage_key)
        blob_client.download_blob.assert_called_once_with()

    @patch("apps.admin.services.resource.BlobServiceClient")
    def test_admin_file_resource_access_streams_inline_file(
        self,
        blob_service_client_mock,
    ):
        self._mock_blob_service(
            blob_service_client_mock,
            [b"%PDF-file-content"],
            "application/pdf",
        )
        resource = Resources.objects.create(
            name="Access File",
            description="Existing file resource",
            kind=Resources.ResourceKind.FILE,
            uploaded_by=self.admin_user,
            storage_key="resources/1778844292421-19-file.pdf",
            file_mime_type="application/pdf",
            file_size=1024,
        )

        response = self.client.get(reverse("admin_api:resource-access", args=[resource.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Content-Disposition"], 'inline; filename="file.pdf"')
        self.assertEqual(response["Content-Length"], "1024")
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-file-content")

    @override_settings(
        AZURE_STORAGE_CONTAINER_NAME="",
        AZURE_CONNECTION_STRING="",
        AZURE_STORAGE_CONNECTION_STRING="",
        AZURE_RESOURCE_CONTAINER="resource-files",
        AZURE_CONTAINER="media",
    )
    @patch("apps.admin.services.resource.BlobServiceClient")
    def test_admin_resource_access_falls_back_to_legacy_container(
        self,
        blob_service_client_mock,
    ):
        missing_blob_client = Mock()
        missing_blob_client.exists.return_value = False

        legacy_stream = Mock()
        legacy_stream.chunks.return_value = [b"legacy content"]
        legacy_properties = Mock()
        legacy_properties.content_settings.content_type = "application/pdf"
        legacy_properties.size = len(b"legacy content")

        legacy_blob_client = Mock()
        legacy_blob_client.exists.return_value = True
        legacy_blob_client.get_blob_properties.return_value = legacy_properties
        legacy_blob_client.download_blob.return_value = legacy_stream

        resource_container = Mock()
        resource_container.get_blob_client.return_value = missing_blob_client
        legacy_container = Mock()
        legacy_container.get_blob_client.return_value = legacy_blob_client
        blob_service = Mock()
        blob_service.get_container_client.side_effect = [resource_container, legacy_container]
        blob_service_client_mock.return_value = blob_service

        resource = Resources.objects.create(
            name="Legacy Container File",
            description="Uploaded before resource container split",
            kind=Resources.ResourceKind.FILE,
            uploaded_by=self.admin_user,
            storage_key="resources/1778844292421-42-file.pdf",
            file_mime_type="application/pdf",
            file_size=len(b"legacy content"),
        )

        response = self.client.get(reverse("admin_api:resource-access", args=[resource.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(response.streaming_content), b"legacy content")
        self.assertEqual(
            [call.args[0] for call in blob_service.get_container_client.call_args_list],
            ["resource-files", "media"],
        )
        legacy_blob_client.download_blob.assert_called_once_with()

    @override_settings(
        AZURE_STORAGE_CONTAINER_NAME="",
        AZURE_CONNECTION_STRING="",
        AZURE_STORAGE_CONNECTION_STRING="",
        AZURE_RESOURCE_CONTAINER="resource-files",
        AZURE_CONTAINER="media",
    )
    @patch("apps.admin.services.resource.BlobServiceClient")
    @patch("apps.admin.services.resource.download_file_bytes")
    def test_admin_resource_download_falls_back_to_resource_container(
        self,
        download_file_bytes_mock,
        blob_service_client_mock,
    ):
        download_file_bytes_mock.side_effect = RuntimeError("legacy container missing")

        download_stream = Mock()
        download_stream.readall.return_value = b"resource container content"
        blob_client = Mock()
        blob_client.exists.return_value = True
        blob_client.download_blob.return_value = download_stream

        container_client = Mock()
        container_client.get_blob_client.return_value = blob_client
        blob_service = Mock()
        blob_service.get_container_client.return_value = container_client
        blob_service_client_mock.return_value = blob_service

        resource = Resources.objects.create(
            name="Resource Container File",
            description="Uploaded through managed resource storage",
            kind=Resources.ResourceKind.FILE,
            uploaded_by=self.admin_user,
            storage_key="2026/05/16/abc/file.pdf",
            file_mime_type="application/pdf",
            file_size=len(b"resource container content"),
        )

        response = self.client.get(reverse("admin_api:resource-download", args=[resource.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content, b"resource container content")
        download_file_bytes_mock.assert_called_once_with(resource.storage_key)

    def test_resource_list_accepts_adminweb_track_and_type_filters(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        nsw_track = Tracks.objects.create(track_name="AUS-NSW", state=state)
        vic_track = Tracks.objects.create(track_name="AUS-VIC", state=state)
        document_type = ResourceType.objects.create(type_name="document")
        video_type = ResourceType.objects.create(type_name="video")

        matching_resource = Resources.objects.create(
            name="Matching Resource",
            description="Visible when both filters are applied",
            type=document_type,
            track=nsw_track,
            uploaded_by=self.admin_user,
        )
        Resources.objects.create(
            name="Wrong Track",
            description="Same type but different track",
            type=document_type,
            track=vic_track,
            uploaded_by=self.admin_user,
        )
        Resources.objects.create(
            name="Wrong Type",
            description="Same track but different type",
            type=video_type,
            track=nsw_track,
            uploaded_by=self.admin_user,
        )

        response = self.client.get(
            reverse("admin_api:resource-list-create"),
            {"track_id": nsw_track.id, "resource_type": "document"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["total"], 1)
        self.assertEqual(
            response.data["data"]["items"][0]["id"],
            matching_resource.id,
        )
