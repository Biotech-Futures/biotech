import io
import tempfile

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from resources.models import Resource
from users.models import User


class ResourceAPITests(APITestCase):
    def setUp(self):
        super().setUp()
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)

        self.override_media = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        self.admin = User.objects.create_user(
            email="admin@example.com",
            username="admin@example.com",
            password="testpass123",
            role="admin",
        )
        self.student = User.objects.create_user(
            email="student@example.com",
            username="student@example.com",
            password="testpass123",
            role="student",
        )

    def authenticate_as_admin(self):
        self.client.force_authenticate(user=self.admin)

    def authenticate_as_student(self):
        self.client.force_authenticate(user=self.student)

    def _create_test_image(self, name="cover.png"):
        buffer = io.BytesIO()
        image = Image.new("RGB", (2, 2), color="white")
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.read(), content_type="image/png")

    def test_list_resources_returns_only_accessible_roles(self):
        Resource.objects.create(
            title="All Users Guide",
            description="Shared resource",
            type="guide",
            role="all",
            file_url="https://example.com/all.pdf",
        )
        Resource.objects.create(
            title="Mentor Handbook",
            description="Mentor only",
            type="document",
            role="mentor",
            file_url="https://example.com/mentor.pdf",
        )
        Resource.objects.create(
            title="Student Checklist",
            description="Student specific",
            type="template",
            role="student",
            file_url="https://example.com/student.pdf",
        )

        self.authenticate_as_student()

        url = reverse("resources:resource-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

        titles = [item["title"] for item in response.data["results"]]
        self.assertIn("All Users Guide", titles)
        self.assertIn("Student Checklist", titles)
        self.assertNotIn("Mentor Handbook", titles)

    def test_admin_can_create_resource_via_upload(self):
        self.authenticate_as_admin()

        upload = SimpleUploadedFile(
            "resource.pdf",
            b"%PDF-1.4 test content",
            content_type="application/pdf",
        )

        url = reverse("resources:resource-list")
        response = self.client.post(
            url,
            {
                "title": "New Resource",
                "description": "A brand new resource",
                "type": "document",
                "role": "all",
                "file": upload,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Resource.objects.filter(title="New Resource").exists())
        resource = Resource.objects.get(title="New Resource")
        self.assertTrue(resource.file_url)
        self.assertEqual(resource.role, "all")
        self.assertEqual(resource.type, "document")

    def test_non_admin_cannot_create_resource(self):
        self.authenticate_as_student()

        upload = SimpleUploadedFile(
            "resource.pdf",
            b"%PDF-1.4 test content",
            content_type="application/pdf",
        )

        url = reverse("resources:resource-list")
        response = self.client.post(
            url,
            {
                "title": "Not Allowed",
                "type": "document",
                "role": "all",
                "file": upload,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Resource.objects.filter(title="Not Allowed").exists())

    def test_admin_can_update_cover_image(self):
        resource = Resource.objects.create(
            title="Cover Target",
            description="Needs a cover",
            type="guide",
            role="all",
            file_url="https://example.com/guide.pdf",
        )

        self.authenticate_as_admin()

        cover = self._create_test_image()
        url = reverse("resources:resource-update-cover", kwargs={"pk": resource.id})
        response = self.client.put(
            url,
            {"coverImage": cover},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resource.refresh_from_db()
        self.assertTrue(resource.cover_image)
        self.assertEqual(response.data["coverImage"], resource.cover_image)

    def test_non_admin_cannot_delete_resource(self):
        resource = Resource.objects.create(
            title="For Deletion",
            description="",
            type="guide",
            role="all",
            file_url="https://example.com/delete.pdf",
        )

        self.authenticate_as_student()
        url = reverse("resources:resource-detail", kwargs={"pk": resource.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Resource.objects.filter(pk=resource.id).exists())
