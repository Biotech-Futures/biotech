from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.test import TestCase
from unittest.mock import patch

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

    @patch("apps.resources.services.upload.upload_file")
    def test_admin_resource_upload_uses_resources_package(self, upload_file_mock):
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
        self.assertTrue(resource.storage_key.endswith("-guide.pdf"))
        self.assertTrue(
            ResourceAudience.objects.filter(resource=resource, role=self.role).exists()
        )
        upload_file_mock.assert_called_once()

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

    def test_resource_attachment_upload_returns_file_url_as_primary_url(self):
        upload = SimpleUploadedFile(
            "brief.pdf",
            b"attached file content",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("admin_api:resource-attachment-upload"),
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        resource = Resources.objects.get(id=response.data["data"]["id"])
        expected_resource_path = f"/media/resource_attachments/{resource.storage_key.removeprefix('resource_attachments/')}"
        expected_download_path = reverse(
            "admin_api:resource-attachment-download",
            args=[resource.id],
        )
        self.assertEqual(response.data["data"]["url"], f"http://testserver{expected_resource_path}")
        self.assertEqual(
            response.data["data"]["resourceUrl"],
            f"http://testserver{expected_resource_path}",
        )
        self.assertTrue(response.data["data"]["downloadUrl"].endswith(expected_download_path))
        self.assertNotEqual(response.data["data"]["resourceUrl"], response.data["data"]["downloadUrl"])

    @patch("apps.admin.services.resource.download_file_text")
    @patch("apps.admin.services.resource.upload_file")
    def test_admin_page_resource_returns_content_html(
        self,
        upload_file_mock,
        download_file_text_mock,
    ):
        download_file_text_mock.return_value = "<p>Hello page</p>"

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

        response = self.client.get(reverse("admin_api:resource-detail", args=[resource.id]))

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

        response = self.client.get(reverse("admin_api:resource-download", args=[resource.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/html")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="test.html"',
        )
        self.assertEqual(response.content, b"<h1>Download me</h1>")
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
