from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.apps import apps as dj_apps
from datetime import datetime, timedelta
from django.utils import timezone

from apps.resources.models import Roles, RoleAssignmentHistory, ResourceRoles
import uuid

class PermissionClassesTests(TestCase):
    def setUp(self):
        get_user_model().objects.all().delete()   # clears auth users
        dj_apps.get_model("users", "User").objects.all().delete()  # clears business users

        reg_email = f"test_reg_{uuid.uuid4().hex}@example.com"
        reg_email_2 = f"test_reg_2_{uuid.uuid4().hex}@example.com"
        admin_email = f"test_admin_{uuid.uuid4().hex}@example.com"
        admin_email_2 = f"test_admin_2_{uuid.uuid4().hex}@example.com"

        self.client = APIClient()
        User = get_user_model()

        # Auth users
        self.regular = User.objects.create_user(email=reg_email_2, password="pw")
        self.admin = User.objects.create_user(email=admin_email_2, password="pw")

        # Attach admin to Django group "Admin"
        admin_group = Group.objects.create(name="Admin")
        self.admin.groups.add(admin_group)

        # Business user mapping chain (FKs required by Users model)
        Countries = dj_apps.get_model("groups", "Countries")
        CountryStates = dj_apps.get_model("groups", "CountryStates")
        Tracks = dj_apps.get_model("groups", "Tracks")
        Users = dj_apps.get_model("users", "User")

        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        track = Tracks.objects.create(track_name="Data", state=state)

        # Business users (linked by email to auth users)
        self.biz_regular = Users.objects.create(
            first_name="Reg", last_name="User",
            email=reg_email, state=state, track=track
        )
        self.biz_admin = Users.objects.create(
            first_name="Adm", last_name="User",
            email=admin_email, state=state, track=track
        )

        # Resource + Roles chain
        Resources = dj_apps.get_model("resources", "Resources")
        self.resource = Resources.objects.create(
            resource_name="Test Resource",
            resource_description="Test resource for permission tests",
            uploader_user_id=self.admin,
            upload_datetime=timezone.now() - timedelta(days=1),  # explicitly set
        )

        self.role_viewer = Roles.objects.create(role_name="viewer")
        self.role_admin = Roles.objects.create(role_name="admin")

        # Link resource to "viewer" role
        ResourceRoles.objects.create(resource=self.resource, role=self.role_viewer)

        # Active role assignment: regular user has viewer role
        RoleAssignmentHistory.objects.create(
            user=self.biz_regular,
            role=self.role_viewer,
            valid_from=timezone.make_aware(datetime(2025, 1, 1)),
            valid_to=None,
        )

    def test_group_gating(self):
        """Regular user should fail group-gated endpoint; admin succeeds."""
        # unauthenticated
        resp = self.client.get(reverse("roles-list"))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # authenticated non-admin (assuming roles-list is group-gated to Admins)
        self.client.force_authenticate(self.regular)
        resp = self.client.get(reverse("roles-list"))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # authenticated admin
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse("roles-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_resource_access(self):
        """Regular user can access resource via attached role; others blocked."""
        url = reverse("resources-detail", args=[self.resource.id])

        # unauthenticated
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # unrelated user (no role assignment)
        stranger = get_user_model().objects.create_user(email="strangigga@example.com", password="pw")
        self.client.force_authenticate(stranger)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # user with role assignment
        self.client.force_authenticate(self.regular)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)