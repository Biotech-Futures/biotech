from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.apps import apps as dj_apps
from datetime import datetime, timedelta
from django.utils import timezone

from apps.resources.models import (
    Roles,
    RoleAssignmentHistory,
    ResourceAudience,
    Resources,
)
import uuid


class PermissionClassesTests(TestCase):
    def setUp(self):
        get_user_model().objects.all().delete()

        reg_email = f"test_reg_{uuid.uuid4().hex}@example.com"
        admin_email = f"test_admin_{uuid.uuid4().hex}@example.com"

        self.client = APIClient()
        User = get_user_model()

        # The ``track`` concept was removed; geography lives on ``User.state``
        # (a nullable FK to groups.CountryStates) and is not exercised by these
        # permission tests, so we skip it entirely.
        self.regular = User.objects.create_user(
            email=reg_email,
            password="pw",
            first_name="Reg",
            last_name="User",
        )
        self.admin = User.objects.create_user(
            email=admin_email,
            password="pw",
            first_name="Adm",
            last_name="User",
        )

        # IsResourceAdmin (used by RoleViewSet.create) checks
        # ``apps.common.rbac.is_admin`` — any AdminScope row means "admin".
        AdminScope = dj_apps.get_model("users", "AdminScope")
        AdminScope.objects.create(user=self.admin)

        # Resource + Roles chain. Default visibility_scope is "role", so access
        # is gated on the resource's role audiences.
        self.resource = Resources.objects.create(
            name="Test Resource",
            description="Test resource for permission tests",
            uploaded_by=self.admin,
            uploaded_at=timezone.now() - timedelta(days=1),
        )

        self.role_viewer = Roles.objects.create(role_name="viewer")
        self.role_admin = Roles.objects.create(role_name="admin")

        # Link resource to the "viewer" role audience.
        ResourceAudience.objects.create(resource=self.resource, role=self.role_viewer)

        # Active role assignment: regular user has the viewer role.
        RoleAssignmentHistory.objects.create(
            user=self.regular,
            role=self.role_viewer,
            valid_from=timezone.make_aware(datetime(2025, 1, 1)),
            valid_to=None,
        )

    def test_group_gating(self):
        """Regular user can list roles, but only admin can create/modify."""
        # unauthenticated - denied
        resp = self.client.get(reverse("roles-list"))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # authenticated regular user - can list roles
        self.client.force_authenticate(self.regular)
        resp = self.client.get(reverse("roles-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # authenticated admin - can also list roles
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse("roles-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # regular user cannot create roles
        self.client.force_authenticate(self.regular)
        resp = self.client.post(reverse("roles-list"), {"role_name": "test_role"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # admin can create roles
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse("roles-list"), {"role_name": "test_role2"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_resource_access(self):
        """Test resource access requires authentication and a matching role."""
        url = reverse("resource-files-detail", args=[self.resource.id])

        # unauthenticated
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # unrelated user (no role assignment)
        stranger = get_user_model().objects.create_user(email="strangigga@example.com", password="pw")
        self.client.force_authenticate(stranger)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # user with matching role assignment
        self.client.force_authenticate(self.regular)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
