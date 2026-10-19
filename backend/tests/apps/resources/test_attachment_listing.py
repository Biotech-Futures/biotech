"""RS2: attachments are hidden from resource lists but stay reachable by ID.

An attachment is a file embedded in a page/announcement/event body. It must not
clutter the browse lists (public list, label counts, admin list), but the link
embedded in its parent content has to keep working.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.storage import get_resource_storage
from apps.resources.models import ResourceAudience, Resources, RoleAssignmentHistory, Roles
from apps.users.models import AdminScope
from tests.apps._helpers import StorageCleanupMixin

User = get_user_model()


class AttachmentListingTests(StorageCleanupMixin, TestCase):
    storage_attr = "storage"
    storage_keys_attr = "created_storage_keys"

    def setUp(self):
        self.client = APIClient()
        self.storage = get_resource_storage()
        self.created_storage_keys = []

        self.admin_user = User.objects.create_user(
            email="admin@attachments.test", password="pass123",
            first_name="Admin", last_name="User",
        )
        AdminScope.objects.create(user=self.admin_user)
        self.student = User.objects.create_user(
            email="student@attachments.test", password="pass123",
            first_name="Student", last_name="User",
        )
        self.student_role = Roles.objects.create(role_name="student")
        now = timezone.now()
        RoleAssignmentHistory.objects.create(
            user=self.student, role=self.student_role,
            valid_from=now, valid_to=now + timedelta(days=30),
        )

        self.client.force_authenticate(user=self.admin_user)
        self.file = self._upload(
            "handbook.pdf", resource_kind="file",
            resource_name="Student Handbook", resource_description="A handbook",
            role_ids=[str(self.student_role.id)], label_names=["Shared"],
        )
        # No roles sent: RS4 gives an attachment every role.
        self.attachment = self._upload(
            "hidden-brief.pdf", resource_kind="attachment",
            resource_name="Hidden Brief", label_names=["Shared"],
        )
        self.page = Resources.objects.create(
            name="Welcome Page", description="A page",
            kind=Resources.ResourceKind.PAGE, storage_key="https://example.org/welcome",
            uploaded_by=self.admin_user, visibility_scope=Resources.VisibilityScope.ROLE,
        )
        ResourceAudience.objects.create(resource=self.page, role=self.student_role)

    def _upload(self, filename, **fields):
        upload = SimpleUploadedFile(filename, b"%PDF-1.4 test", content_type="application/pdf")
        response = self.client.post(
            reverse("admin_api:resource-upload"), {"file": upload, **fields}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        resource = Resources.objects.get(id=response.data["data"]["id"])
        self.created_storage_keys.append(resource.storage_key)
        return resource

    def _public_list(self, user, **params):
        self.client.force_authenticate(user=user)
        response = self.client.get(reverse("resource-files-list"), params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    # --- public list ------------------------------------------------------

    def test_public_list_hides_attachments_from_students(self):
        data = self._public_list(self.student)
        ids = {row["id"] for row in data["results"]}
        self.assertEqual(ids, {self.file.id, self.page.id})
        self.assertEqual(data["count"], 2)

    def test_public_list_hides_attachments_from_admins(self):
        data = self._public_list(self.admin_user)
        ids = {row["id"] for row in data["results"]}
        self.assertNotIn(self.attachment.id, ids)
        self.assertEqual(data["count"], 2)

    def test_search_does_not_surface_attachments(self):
        data = self._public_list(self.student, search="Hidden Brief")
        self.assertEqual(data["results"], [])
        self.assertEqual(data["count"], 0)

    def test_attachment_is_still_reachable_by_id(self):
        # The link embedded in the parent page must keep working.
        self.client.force_authenticate(user=self.student)
        pk = {"pk": self.attachment.id}

        self.assertEqual(
            self.client.get(reverse("resource-files-detail", kwargs=pk)).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.get(reverse("resource-files-access", kwargs=pk)).status_code,
            status.HTTP_200_OK,
        )
        download = self.client.get(reverse("resource-files-download", kwargs=pk))
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(download.streaming_content), b"%PDF-1.4 test")

    # --- label counts -----------------------------------------------------

    def test_label_count_excludes_attachments(self):
        # "Shared" is on the file and the attachment; only the file counts.
        for user in (self.student, self.admin_user):
            self.client.force_authenticate(user=user)
            response = self.client.get(reverse("resource-labels-list"))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            by_name = {row["name"]: row for row in response.data}
            self.assertEqual(by_name["Shared"]["resource_count"], 1, user.email)

    # --- admin list -------------------------------------------------------

    def _admin_list(self, **params):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            reverse("admin_api:resource-list-create"), {"limit": 50, **params}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["data"]

    def test_admin_list_hides_attachments_by_default(self):
        data = self._admin_list()
        ids = {item["id"] for item in data["items"]}
        self.assertEqual(ids, {self.file.id, self.page.id})
        self.assertEqual(data["total"], 2)

    def test_admin_list_returns_attachments_when_asked(self):
        data = self._admin_list(resourceKind="attachment")
        ids = {item["id"] for item in data["items"]}
        self.assertEqual(ids, {self.attachment.id})
        self.assertEqual(data["total"], 1)

    def test_admin_detail_still_opens_attachment(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            reverse("admin_api:resource-detail", args=[self.attachment.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["resource_kind"], "attachment")
