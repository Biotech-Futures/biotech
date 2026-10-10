from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.resources.models import (
    ResourceAudience,
    ResourceType,
    Resources,
    Roles,
)
from apps.users.models import AdminScope
from tests.apps._helpers import StorageCleanupMixin

User = get_user_model()


class RecordedSessionTests(StorageCleanupMixin, TestCase):
    storage_attr = "storage"
    storage_keys_attr = "created_storage_keys"

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="pass123",
            first_name="Admin",
            last_name="User",
        )
        AdminScope.objects.create(user=self.admin)

        self.student = User.objects.create_user(
            email="student@test.com",
            password="pass123",
            first_name="Student",
            last_name="User",
        )

        self.student_role = Roles.objects.create(role_name="Student")
        self.mentor_role = Roles.objects.create(role_name="Mentor")

        self.recorded_session_type, _ = ResourceType.objects.get_or_create(
            type_name="Recorded Session",
            defaults={"type_description": "Recorded session video and presentation slides"},
        )
        self.document_type, _ = ResourceType.objects.get_or_create(
            type_name="document",
            defaults={"type_description": "Document resources"},
        )

    def test_upload_recorded_session_with_video_and_slides(self):
        self.client.force_authenticate(user=self.admin)
        video_file = SimpleUploadedFile("workshop.mp4", b"fake video content", content_type="video/mp4")
        slides_file = SimpleUploadedFile("slides.pdf", b"%PDF-1.4 fake slides", content_type="application/pdf")

        response = self.client.post(
            "/api/v1/admin/resource/upload/",
            {
                "name": "Workshop 1 Recording",
                "description": "Introduction to Biotech",
                "kind": "file",
                "resource_type_id": self.recorded_session_type.id,
                "role_ids": [self.student_role.id],
                "file": video_file,
                "slides_file": slides_file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        res_data = response.data.get("data")
        self.assertIsNotNone(res_data)
        self.assertTrue(res_data["has_slides"])
        self.assertEqual(res_data["slides_mime_type"], "application/pdf")
        self.assertIsNotNone(res_data["slides_storage_key"])

        # Check DB directly
        resource = Resources.objects.get(id=res_data["id"])
        self.assertIsNotNone(resource.slides_storage_key)
        self.assertEqual(resource.slides_mime_type, "application/pdf")

    def test_upload_recorded_session_without_slides(self):
        self.client.force_authenticate(user=self.admin)
        video_file = SimpleUploadedFile("workshop.mp4", b"fake video content", content_type="video/mp4")

        response = self.client.post(
            "/api/v1/admin/resource/upload/",
            {
                "name": "Workshop 2 Recording",
                "description": "Video only session",
                "kind": "file",
                "resource_type_id": self.recorded_session_type.id,
                "role_ids": [self.student_role.id],
                "file": video_file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        res_data = response.data.get("data")
        self.assertFalse(res_data["has_slides"])
        self.assertIsNone(res_data["slides_storage_key"])

    def test_upload_recorded_session_rejects_non_pdf_slides(self):
        self.client.force_authenticate(user=self.admin)
        video_file = SimpleUploadedFile("workshop.mp4", b"fake video content", content_type="video/mp4")
        bad_slides = SimpleUploadedFile("slides.txt", b"plain text slides", content_type="text/plain")

        response = self.client.post(
            "/api/v1/admin/resource/upload/",
            {
                "name": "Workshop Bad Slides",
                "description": "Invalid slides format",
                "kind": "file",
                "resource_type_id": self.recorded_session_type.id,
                "role_ids": [self.student_role.id],
                "file": video_file,
                "slides_file": bad_slides,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_slides_rejected_for_non_recorded_session(self):
        self.client.force_authenticate(user=self.admin)
        doc_file = SimpleUploadedFile("document.pdf", b"%PDF-1.4 doc", content_type="application/pdf")
        slides_file = SimpleUploadedFile("slides.pdf", b"%PDF-1.4 slides", content_type="application/pdf")

        response = self.client.post(
            "/api/v1/admin/resource/upload/",
            {
                "name": "Document Resource",
                "description": "Not a recorded session",
                "kind": "file",
                "resource_type_id": self.document_type.id,
                "role_ids": [self.student_role.id],
                "file": doc_file,
                "slides_file": slides_file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_recorded_session_cannot_be_page(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/v1/admin/resource/",
            {
                "resource_name": "Page Session",
                "resource_description": "Page cannot be a recorded session",
                "resource_kind": "page",
                "resource_type_id": self.recorded_session_type.id,
                "visibility_scope": "role_based",
                "role_ids": [self.student_role.id],
                "content_html": "<p>Content</p>",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_replace_slides_file_via_admin(self):
        self.client.force_authenticate(user=self.admin)
        video_file = SimpleUploadedFile("workshop.mp4", b"fake video content", content_type="video/mp4")

        upload_resp = self.client.post(
            "/api/v1/admin/resource/upload/",
            {
                "name": "Workshop to Update",
                "description": "Initial without slides",
                "kind": "file",
                "resource_type_id": self.recorded_session_type.id,
                "role_ids": [self.student_role.id],
                "file": video_file,
            },
            format="multipart",
        )
        resource_id = upload_resp.data["data"]["id"]

        new_slides = SimpleUploadedFile("attached_slides.pdf", b"%PDF-1.4 updated slides", content_type="application/pdf")
        replace_resp = self.client.post(
            f"/api/v1/admin/resource/{resource_id}/upload/",
            {"slides_file": new_slides},
            format="multipart",
        )

        self.assertEqual(replace_resp.status_code, status.HTTP_200_OK)
        res_data = replace_resp.data["data"]
        self.assertTrue(res_data["has_slides"])
        self.assertEqual(res_data["slides_mime_type"], "application/pdf")

    def test_download_and_access_with_field_selector(self):
        self.client.force_authenticate(user=self.admin)
        video_file = SimpleUploadedFile("workshop.mp4", b"video bytes content", content_type="video/mp4")
        slides_file = SimpleUploadedFile("slides.pdf", b"%PDF-1.4 slides bytes", content_type="application/pdf")

        upload_resp = self.client.post(
            "/api/v1/admin/resource/upload/",
            {
                "name": "Dual File Session",
                "description": "Both video and slides",
                "kind": "file",
                "resource_type_id": self.recorded_session_type.id,
                "role_ids": [self.student_role.id],
                "file": video_file,
                "slides_file": slides_file,
            },
            format="multipart",
        )
        resource_id = upload_resp.data["data"]["id"]

        # Public download endpoint default (video)
        dl_default = self.client.get(f"/resources/resource-files/{resource_id}/download/")
        self.assertEqual(dl_default.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(dl_default.streaming_content), b"video bytes content")

        # Public download endpoint slides
        dl_slides = self.client.get(f"/resources/resource-files/{resource_id}/download/?field=slides")
        self.assertEqual(dl_slides.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(dl_slides.streaming_content), b"%PDF-1.4 slides bytes")

        # Public access endpoint slides
        acc_slides = self.client.get(f"/resources/resource-files/{resource_id}/access/?field=slides")
        self.assertEqual(acc_slides.status_code, status.HTTP_200_OK)
        self.assertTrue(acc_slides.data["has_slides"])
        self.assertIn("field=slides", acc_slides.data["download_url"])

        # Public download endpoint slides on resource without slides -> 404
        no_slides_resp = self.client.post(
            "/api/v1/admin/resource/upload/",
            {
                "name": "Video Only Session 2",
                "description": "No slides",
                "kind": "file",
                "resource_type_id": self.recorded_session_type.id,
                "role_ids": [self.student_role.id],
                "file": SimpleUploadedFile("only_video.mp4", b"video content", content_type="video/mp4"),
            },
            format="multipart",
        )
        no_slides_id = no_slides_resp.data["data"]["id"]
        dl_no_slides = self.client.get(f"/resources/resource-files/{no_slides_id}/download/?field=slides")
        self.assertEqual(dl_no_slides.status_code, status.HTTP_404_NOT_FOUND)
