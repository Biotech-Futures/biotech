from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.storage import get_resource_storage
from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.resources.models import ResourceAudience, ResourceType, Resources, RoleAssignmentHistory, Roles
from apps.users.models import AdminScope


User = get_user_model()


class ResourceFileTransferTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.primary_track = Tracks.objects.create(track_name="Primary", state=self.state)
        self.secondary_track = Tracks.objects.create(track_name="Secondary", state=self.state)
        self.primary_group = Groups.objects.create(group_name="Primary Group", track=self.primary_track)

        self.global_admin = User.objects.create_user(
            email="global-admin@test.com",
            password="pass123",
            first_name="Global",
            last_name="Admin",
            track=self.primary_track,
        )
        self.track_admin = User.objects.create_user(
            email="track-admin@test.com",
            password="pass123",
            first_name="Track",
            last_name="Admin",
            track=self.primary_track,
        )
        self.mentor = User.objects.create_user(
            email="mentor@test.com",
            password="pass123",
            first_name="Mentor",
            last_name="User",
            track=self.primary_track,
        )
        self.supervisor = User.objects.create_user(
            email="supervisor@test.com",
            password="pass123",
            first_name="Supervisor",
            last_name="User",
            track=self.primary_track,
        )
        self.student = User.objects.create_user(
            email="student@test.com",
            password="pass123",
            first_name="Student",
            last_name="User",
            track=self.primary_track,
        )
        self.outsider = User.objects.create_user(
            email="outsider@test.com",
            password="pass123",
            first_name="Outside",
            last_name="User",
            track=self.secondary_track,
        )

        AdminScope.objects.create(user=self.global_admin, is_global=True)
        AdminScope.objects.create(user=self.track_admin, track=self.primary_track, is_global=False)

        self.mentor_role = Roles.objects.create(role_name="mentor")
        self.supervisor_role = Roles.objects.create(role_name="supervisor")
        self.student_role = Roles.objects.create(role_name="student")

        now = timezone.now()
        future = now + timedelta(days=365)
        RoleAssignmentHistory.objects.create(user=self.mentor, role=self.mentor_role, valid_from=now, valid_to=future)
        RoleAssignmentHistory.objects.create(
            user=self.supervisor,
            role=self.supervisor_role,
            valid_from=now,
            valid_to=future,
        )
        RoleAssignmentHistory.objects.create(user=self.student, role=self.student_role, valid_from=now, valid_to=future)

        GroupMembership.objects.create(user=self.mentor, group=self.primary_group, membership_role="mentor")
        GroupMembership.objects.create(user=self.supervisor, group=self.primary_group, membership_role="mentor")
        GroupMembership.objects.create(user=self.student, group=self.primary_group, membership_role="student")

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

    def _build_upload(
        self,
        filename="Program Guide.pdf",
        content=b"program guide payload",
        content_type="application/pdf",
    ):
        return SimpleUploadedFile(
            filename,
            content,
            content_type=content_type,
        )

    def _resource_payload(self, *, name, visibility_scope, uploaded_file=None, **overrides):
        payload = {
            "name": name,
            "description": f"{name} description",
            "type_id": str(self.resource_type.id),
            "visibility_scope": visibility_scope,
            "uploaded_file": uploaded_file or self._build_upload(filename=f"{name}.pdf"),
        }
        for key, value in overrides.items():
            if hasattr(value, "id"):
                payload[key] = str(value.id)
            else:
                payload[key] = value
        return payload

    def _post_resource(self, user, *, name, visibility_scope, **overrides):
        self.client.force_authenticate(user=user)
        response = self.client.post(
            reverse("resource-files-list"),
            self._resource_payload(name=name, visibility_scope=visibility_scope, **overrides),
            format="multipart",
        )
        resource = None
        if response.status_code == status.HTTP_201_CREATED:
            resource = Resources.objects.get(pk=response.data["id"])
            self.created_storage_keys.append(resource.storage_key)
        return response, resource

    def _create_resource(self, *, user, name, visibility_scope, audience_role=None, audience_track=None, **overrides):
        response, resource = self._post_resource(
            user,
            name=name,
            visibility_scope=visibility_scope,
            **overrides,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        if audience_role is not None or audience_track is not None:
            ResourceAudience.objects.create(
                resource=resource,
                role=audience_role,
                track=audience_track,
            )
        resource.refresh_from_db()
        return response, resource

    def test_global_admin_can_upload_resource(self):
        response, resource = self._post_resource(
            self.global_admin,
            name="Global Admin Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(self.storage.exists(resource.storage_key))
        self.assertEqual(response.data["type_name"], "document")
        self.assertEqual(response.data["uploader_name"], "Global Admin")
        self.assertTrue(response.data["file_name"].endswith(".pdf"))
        self.assertEqual(response.data["storage_status"], "managed_key")
        self.assertTrue(response.data["access_url"].endswith(reverse("resource-files-access", kwargs={"pk": resource.id})))
        self.assertTrue(response.data["download_url"].endswith(reverse("resource-files-download", kwargs={"pk": resource.id})))
        self.assertNotIn(resource.storage_key, response.data["access_url"])
        self.assertNotIn(resource.storage_key, response.data["download_url"])
        self.assertNotIn("storage_key", response.data)
        self.assertNotIn("uploader", response.data)
        self.assertNotIn("track", response.data)
        self.assertNotIn("group", response.data)
        self.assertNotIn("visibility_scope", response.data)
        self.assertNotIn("visible_roles", response.data)
        self.assertNotIn("audiences", response.data)

    def test_resource_retrieve_returns_public_shape(self):
        _, resource = self._create_resource(
            user=self.global_admin,
            name="Public Detail Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
        )

        self.client.force_authenticate(user=self.global_admin)
        response = self.client.get(reverse("resource-files-detail", kwargs={"pk": resource.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], resource.id)
        self.assertEqual(response.data["name"], "Public Detail Guide")
        self.assertEqual(response.data["type_name"], "document")
        self.assertIn("file_name", response.data)
        self.assertIn("access_url", response.data)
        self.assertIn("download_url", response.data)
        self.assertIn("storage_status", response.data)
        self.assertNotIn("storage_key", response.data)
        self.assertNotIn("uploader", response.data)
        self.assertNotIn("track", response.data)
        self.assertNotIn("group", response.data)
        self.assertNotIn("visibility_scope", response.data)
        self.assertNotIn("visible_roles", response.data)
        self.assertNotIn("audiences", response.data)

    def test_track_admin_can_upload_resource_within_assigned_track(self):
        response, resource = self._post_resource(
            self.track_admin,
            name="Track Admin Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resource.track_id, self.primary_track.id)
        self.assertEqual(response.data["uploader_name"], "Track Admin")

    def test_track_admin_cannot_upload_resource_outside_assigned_track(self):
        response, _ = self._post_resource(
            self.track_admin,
            name="Out Of Scope Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.secondary_track,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_mentor_cannot_upload_resource(self):
        response, _ = self._post_resource(
            self.mentor,
            name="Mentor Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_supervisor_cannot_upload_resource(self):
        response, _ = self._post_resource(
            self.supervisor,
            name="Supervisor Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_upload_resource(self):
        response, _ = self._post_resource(
            self.student,
            name="Student Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(RESOURCE_FILE_MAX_UPLOAD_SIZE=4)
    def test_resource_upload_rejects_files_above_max_size(self):
        response, _ = self._post_resource(
            self.global_admin,
            name="Large Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
            uploaded_file=self._build_upload(content=b"12345"),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("fields", response.data)
        self.assertIn("uploaded_file", response.data["fields"])
        self.assertIn("maximum allowed size", str(response.data["fields"]["uploaded_file"][0]))

    def test_resource_upload_rejects_disallowed_extension(self):
        response, _ = self._post_resource(
            self.global_admin,
            name="Executable Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
            uploaded_file=self._build_upload(
                filename="malware.exe",
                content_type="application/octet-stream",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("fields", response.data)
        self.assertIn("uploaded_file", response.data["fields"])
        self.assertIn("allowed file extension", str(response.data["fields"]["uploaded_file"][0]))

    def test_resource_upload_rejects_disallowed_mime_type(self):
        response, _ = self._post_resource(
            self.global_admin,
            name="Wrong Mime Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
            uploaded_file=self._build_upload(
                filename="guide.pdf",
                content_type="application/octet-stream",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("fields", response.data)
        self.assertIn("uploaded_file", response.data["fields"])
        self.assertIn("allowed content type", str(response.data["fields"]["uploaded_file"][0]))

    def test_allowed_user_can_download_visible_resource(self):
        _, resource = self._create_resource(
            user=self.global_admin,
            name="Primary Track Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
        )

        self.client.force_authenticate(user=self.track_admin)
        access_response = self.client.get(reverse("resource-files-access", kwargs={"pk": resource.id}))
        self.assertEqual(access_response.status_code, status.HTTP_200_OK)
        self.assertEqual(access_response.data["storage_status"], "managed_key")
        self.assertEqual(access_response.data["file_name"], "primary-track-guide.pdf")
        self.assertTrue(access_response.data["access_url"].endswith(reverse("resource-files-access", kwargs={"pk": resource.id})))
        self.assertTrue(access_response.data["download_url"].endswith(reverse("resource-files-download", kwargs={"pk": resource.id})))

        download_response = self.client.get(reverse("resource-files-download", kwargs={"pk": resource.id}))
        self.assertEqual(download_response.status_code, status.HTTP_200_OK)
        self.assertEqual(download_response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", download_response["Content-Disposition"])
        self.assertEqual(b"".join(download_response.streaming_content), b"program guide payload")

    def test_disallowed_user_cannot_download_restricted_resource(self):
        _, resource = self._create_resource(
            user=self.global_admin,
            name="Mentor Only Guide",
            visibility_scope=Resources.VisibilityScope.ROLE,
            audience_role=self.mentor_role,
            track=self.primary_track,
        )

        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("resource-files-download", kwargs={"pk": resource.id}))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_signed_blob_url_generation_is_not_reached_before_permission_check(self):
        _, resource = self._create_resource(
            user=self.global_admin,
            name="Restricted Guide",
            visibility_scope=Resources.VisibilityScope.ROLE,
            audience_role=self.mentor_role,
            track=self.primary_track,
        )

        self.client.force_authenticate(user=self.student)
        with patch("apps.resources.views.resolve_managed_storage_url") as resolve_storage_url:
            with patch("apps.resources.views.open_managed_resource_file") as open_storage_file:
                response = self.client.get(reverse("resource-files-download", kwargs={"pk": resource.id}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        resolve_storage_url.assert_not_called()
        open_storage_file.assert_not_called()

    @override_settings(CHAT_SANITIZER_BLACKLIST=["badword*"])
    def test_resource_serializer_returns_sanitized_file_name(self):
        response, resource = self._post_resource(
            self.global_admin,
            name="Unsafe Filename Guide",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
            uploaded_file=self._build_upload(filename="<script>badword.PDF"),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["file_name"], "redacted.pdf")
        self.assertTrue(resource.storage_key.endswith("/redacted.pdf"))

    @override_settings(CHAT_SANITIZER_BLACKLIST=["badword*"])
    def test_resource_download_uses_sanitized_content_disposition(self):
        _, resource = self._create_resource(
            user=self.global_admin,
            name="Unsafe Filename Download",
            visibility_scope=Resources.VisibilityScope.TRACK,
            track=self.primary_track,
            uploaded_file=self._build_upload(filename="<script>badword.PDF"),
        )

        self.client.force_authenticate(user=self.global_admin)
        response = self.client.get(reverse("resource-files-download", kwargs={"pk": resource.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('filename="redacted.pdf"', response["Content-Disposition"])
