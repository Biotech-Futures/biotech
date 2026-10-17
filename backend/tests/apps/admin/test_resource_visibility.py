"""RS4: resources are role-based only.

Covers the admin write paths (create, update, upload, remove-role), the DRF
``resource-files`` write surface, the attachment "every role" auto-fill, and
the 0011 backfill migration.
"""
from datetime import timedelta
from importlib import import_module

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.storage import get_resource_storage
from apps.groups.models import Groups
from apps.resources.models import ResourceAudience, Resources, RoleAssignmentHistory, Roles
from apps.users.models import AdminScope
from tests.apps._helpers import StorageCleanupMixin

User = get_user_model()

backfill_role_visibility = import_module(
    "apps.resources.migrations.0011_backfill_role_visibility"
).backfill_role_visibility


class _VisibilityTestBase(StorageCleanupMixin, TestCase):
    storage_attr = "storage"
    storage_keys_attr = "created_storage_keys"

    def setUp(self):
        self.client = APIClient()
        self.storage = get_resource_storage()
        self.created_storage_keys = []

        self.admin_user = User.objects.create_user(
            email="admin@visibility.test", password="pass123",
            first_name="Admin", last_name="User",
        )
        AdminScope.objects.create(user=self.admin_user)
        self.client.force_authenticate(user=self.admin_user)

        self.admin_role = Roles.objects.create(role_name="admin")
        self.student_role = Roles.objects.create(role_name="student")
        self.mentor_role = Roles.objects.create(role_name="mentor")

    def _pdf(self, name="guide.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")

    def _track(self, resource_id):
        resource = Resources.objects.get(id=resource_id)
        self.created_storage_keys.append(resource.storage_key)
        return resource

    def _role_ids(self, resource):
        return set(
            ResourceAudience.objects.filter(resource=resource).values_list("role_id", flat=True)
        )


class AdminCreateVisibilityTests(_VisibilityTestBase):
    def _create_page(self, **overrides):
        payload = {
            "resource_kind": "page",
            "resource_name": "Handbook",
            "resource_description": "Page resource",
            "visibility_scope": "role_based",
            "role_ids": [self.student_role.id],
            "content_html": "<p>Hello</p>",
        }
        payload.update(overrides)
        return self.client.post(reverse("admin_api:resource-list-create"), payload, format="json")

    def test_global_visibility_is_rejected(self):
        response = self._create_page(visibility_scope="global")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("visibility_scope", response.data["errors"])
        self.assertFalse(Resources.objects.filter(name="Handbook").exists())

    def test_public_visibility_is_rejected(self):
        response = self._create_page(visibility_scope="public")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Resources.objects.filter(name="Handbook").exists())

    def test_missing_role_ids_is_rejected(self):
        payload_without_roles = {
            "resource_kind": "page",
            "resource_name": "Handbook",
            "resource_description": "Page resource",
            "visibility_scope": "role_based",
            "content_html": "<p>Hello</p>",
        }
        response = self.client.post(
            reverse("admin_api:resource-list-create"), payload_without_roles, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role_ids", response.data["errors"])

    def test_empty_role_ids_is_rejected(self):
        response = self._create_page(role_ids=[])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role_ids", response.data["errors"])

    def test_admin_role_alone_does_not_count(self):
        # The admin role is added automatically, so choosing only it means
        # the admin chose no audience at all.
        response = self._create_page(role_ids=[self.admin_role.id])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role_ids", response.data["errors"])

    def test_valid_create_stores_canonical_role_scope(self):
        response = self._create_page()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        resource = self._track(response.data["data"]["id"])
        # The model value, not the "role_based" API token.
        self.assertEqual(resource.visibility_scope, Resources.VisibilityScope.ROLE)
        self.assertEqual(self._role_ids(resource), {self.student_role.id, self.admin_role.id})


class AdminUpdateVisibilityTests(_VisibilityTestBase):
    def setUp(self):
        super().setUp()
        self.resource = Resources.objects.create(
            name="Existing", description="Existing resource",
            uploaded_by=self.admin_user, visibility_scope=Resources.VisibilityScope.ROLE,
        )
        ResourceAudience.objects.create(resource=self.resource, role=self.student_role)
        self.url = reverse("admin_api:resource-detail", args=[self.resource.id])

    def test_update_to_global_is_rejected(self):
        response = self.client.put(
            self.url,
            {"visibility_scope": "global", "role_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.visibility_scope, Resources.VisibilityScope.ROLE)
        self.assertEqual(self._role_ids(self.resource), {self.student_role.id})

    def test_update_with_empty_roles_is_rejected(self):
        response = self.client.put(
            self.url,
            {"visibility_scope": "role_based", "role_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self._role_ids(self.resource), {self.student_role.id})

    def test_valid_update_stores_canonical_role_scope(self):
        # A legacy row still holding the literal "role_based" token.
        Resources.objects.filter(id=self.resource.id).update(visibility_scope="role_based")

        response = self.client.put(
            self.url,
            {"visibility_scope": "role_based", "role_ids": [self.mentor_role.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.visibility_scope, Resources.VisibilityScope.ROLE)
        self.assertEqual(self._role_ids(self.resource), {self.mentor_role.id, self.admin_role.id})

    def test_rename_without_touching_visibility_is_not_blocked(self):
        # A plain metadata edit must not be forced to re-send roles.
        response = self.client.put(
            self.url,
            {"resource_name": "Renamed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.name, "Renamed")
        self.assertEqual(self.resource.visibility_scope, Resources.VisibilityScope.ROLE)
        self.assertEqual(self._role_ids(self.resource), {self.student_role.id})

    def test_legacy_global_row_still_lists(self):
        # Only writes reject global; reads tolerate rows the backfill hasn't touched.
        Resources.objects.create(
            name="Legacy Global", description="Saved before RS4",
            uploaded_by=self.admin_user, visibility_scope="global",
        )
        response = self.client.get(reverse("admin_api:resource-list-create"), {"limit": 50})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["resource_name"] for item in response.data["data"]["items"]]
        self.assertIn("Legacy Global", names)


class AdminRemoveRoleTests(_VisibilityTestBase):
    def setUp(self):
        super().setUp()
        self.resource = Resources.objects.create(
            name="Scoped", description="Scoped resource",
            uploaded_by=self.admin_user, visibility_scope=Resources.VisibilityScope.ROLE,
        )
        ResourceAudience.objects.create(resource=self.resource, role=self.admin_role)
        ResourceAudience.objects.create(resource=self.resource, role=self.student_role)
        self.url = reverse("admin_api:resource-remove-role", args=[self.resource.id])

    def test_removing_last_non_admin_role_is_blocked(self):
        response = self.client.delete(self.url, {"roleId": self.student_role.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("at least one role", str(response.data["msg"]))
        self.assertEqual(self._role_ids(self.resource), {self.admin_role.id, self.student_role.id})

    def test_removing_a_role_when_another_remains_is_allowed(self):
        ResourceAudience.objects.create(resource=self.resource, role=self.mentor_role)

        response = self.client.delete(self.url, {"roleId": self.student_role.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._role_ids(self.resource), {self.admin_role.id, self.mentor_role.id})


class AdminUploadVisibilityTests(_VisibilityTestBase):
    def _upload(self, **fields):
        return self.client.post(reverse("admin_api:resource-upload"), fields, format="multipart")

    def test_attachment_without_roles_gets_every_role(self):
        response = self._upload(file=self._pdf("brief.pdf"), resource_kind="attachment")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        resource = self._track(response.data["data"]["id"])
        self.assertEqual(resource.visibility_scope, Resources.VisibilityScope.ROLE)
        audience = list(
            ResourceAudience.objects.filter(resource=resource).values_list("role_id", flat=True)
        )
        # Exactly one row per role, no duplicates.
        self.assertCountEqual(
            audience, [self.admin_role.id, self.student_role.id, self.mentor_role.id]
        )

    def test_attachment_with_roles_uses_only_those_roles(self):
        response = self._upload(
            file=self._pdf("brief.pdf"),
            resource_kind="attachment",
            role_ids=[str(self.mentor_role.id)],
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        resource = self._track(response.data["data"]["id"])
        self.assertEqual(self._role_ids(resource), {self.mentor_role.id})

    def test_student_can_access_and_download_auto_filled_attachment(self):
        response = self._upload(file=self._pdf("brief.pdf"), resource_kind="attachment")
        resource = self._track(response.data["data"]["id"])

        student = User.objects.create_user(
            email="student@visibility.test", password="pass123",
            first_name="Student", last_name="User",
        )
        now = timezone.now()
        RoleAssignmentHistory.objects.create(
            user=student, role=self.student_role,
            valid_from=now, valid_to=now + timedelta(days=30),
        )
        self.client.force_authenticate(user=student)

        access = self.client.get(reverse("resource-files-access", kwargs={"pk": resource.id}))
        self.assertEqual(access.status_code, status.HTTP_200_OK)
        download = self.client.get(reverse("resource-files-download", kwargs={"pk": resource.id}))
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        self.assertEqual(b"".join(download.streaming_content), b"%PDF-1.4 test")

    def test_file_upload_without_roles_is_rejected(self):
        # The every-role auto-fill is for attachments only.
        response = self._upload(
            file=self._pdf("guide.pdf"),
            resource_kind="file",
            resource_name="No Roles",
            resource_description="Should be rejected",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Resources.objects.filter(name="No Roles").exists())

    def test_file_upload_with_global_visibility_is_rejected(self):
        response = self._upload(
            file=self._pdf("guide.pdf"),
            resource_name="Global Upload",
            resource_description="Should be rejected",
            visibility_scope="global",
            role_ids=[str(self.student_role.id)],
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Resources.objects.filter(name="Global Upload").exists())


class ResourceFilesApiVisibilityTests(_VisibilityTestBase):
    """The DRF resource-files write surface enforces the same rules."""

    def _post(self, **fields):
        payload = {
            "name": "Api Resource",
            "description": "Created through the resources API",
            "uploaded_file": self._pdf("api.pdf"),
        }
        payload.update(fields)
        response = self.client.post(reverse("resource-files-list"), payload, format="multipart")
        if response.status_code == status.HTTP_201_CREATED:
            self._track(response.data["id"])
        return response

    def test_public_scope_is_rejected(self):
        response = self._post(visibility_scope="public", role_ids=[str(self.student_role.id)])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_role_scope_with_role_ids_omitted_is_rejected(self):
        response = self._post(visibility_scope="role")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_role_scope_with_roles_is_accepted(self):
        response = self._post(visibility_scope="role", role_ids=[str(self.student_role.id)])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_group_scope_is_unaffected(self):
        group = Groups.objects.create(group_name="Team A")
        response = self._post(visibility_scope="group", group=str(group.id))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class BackfillRoleVisibilityMigrationTests(_VisibilityTestBase):
    def _resource(self, name, scope, kind=Resources.ResourceKind.FILE, group=None):
        return Resources.objects.create(
            name=name, description=name, kind=kind, group=group,
            uploaded_by=self.admin_user, visibility_scope=scope,
        )

    def test_backfill(self):
        public_file = self._resource("Public File", "public")
        global_page = self._resource("Global Page", "global", kind=Resources.ResourceKind.PAGE)
        # Already has one role: must not get a duplicate row for it.
        ResourceAudience.objects.create(resource=global_page, role=self.student_role)
        public_attachment = self._resource(
            "Public Attachment", "public", kind=Resources.ResourceKind.ATTACHMENT
        )
        legacy_role_based = self._resource("Legacy Role Based", "role_based")
        ResourceAudience.objects.create(resource=legacy_role_based, role=self.mentor_role)
        group = Groups.objects.create(group_name="Team B")
        group_scoped = self._resource("Group Scoped", "group", group=group)

        backfill_role_visibility(django_apps, None)

        every_role = [self.admin_role.id, self.student_role.id, self.mentor_role.id]
        for resource in (public_file, global_page, public_attachment):
            resource.refresh_from_db()
            self.assertEqual(resource.visibility_scope, "role", resource.name)
            self.assertCountEqual(
                ResourceAudience.objects.filter(resource=resource).values_list("role_id", flat=True),
                every_role,
                resource.name,
            )

        legacy_role_based.refresh_from_db()
        self.assertEqual(legacy_role_based.visibility_scope, "role")
        self.assertEqual(self._role_ids(legacy_role_based), {self.mentor_role.id})

        group_scoped.refresh_from_db()
        self.assertEqual(group_scoped.visibility_scope, "group")
        self.assertEqual(self._role_ids(group_scoped), set())
