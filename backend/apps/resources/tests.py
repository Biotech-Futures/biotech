from django.test import TestCase
import logging


from datetime import date, datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.apps import apps as dj_apps

from .models import Roles, RoleAssignmentHistory
from .services.roles import grant_role, revoke_role, ensure_user_has_role, create_role
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError

# Create your tests here.
class RolesApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()           
        User = get_user_model()

        # Auth user to hit endpoints guarded by IsAuthenticated
        self.me = User.objects.create_user(password="pw12345", email = "test_email@gmail.com")

        # Some roles (unordered on purpose to check ordering in response)
        self.viewer = Roles.objects.create(role_name="viewer")
        self.admin = Roles.objects.create(role_name="admin")

    def test_roles_requires_auth(self):
        url = reverse("roles-list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_roles_list_ok_and_ordered(self):
        self.client.force_authenticate(self.me)
        url = reverse("roles-list")  
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual([r["role_name"] for r in data], ["admin", "viewer"])


class RoleAssignmentsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Auth user (whatever your AUTH_USER_MODEL is)
        AuthUser = get_user_model()
        self.me = AuthUser.objects.create_user(password="pw12345", email = "test_email@gmail.com")
        self.client.force_authenticate(self.me)

        User = dj_apps.get_model('users', 'User')
        Countries = dj_apps.get_model('groups', 'Countries')
        CountryStates = dj_apps.get_model('groups', 'CountryStates')
        Tracks = dj_apps.get_model('groups', 'Tracks')

        # Step 1: Minimal chain to satisfy FKs
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        track = Tracks.objects.create(track_name="Data Science", state=state)

        self.r_admin = Roles.objects.create(role_name="admin")
        self.r_view  = Roles.objects.create(role_name="viewer")

        # Step 2: Create Users with required fields
        self.u1 = User.objects.create(
            first_name="Alice",
            last_name="Tester",
            email="u1@example.com",
            track=track,
            state=state,
        )

        self.u2 = User.objects.create(
            first_name="Bob",
            last_name="Tester",
            email="u2@example.com",
            track=track,
            state=state,
        )

        # Step 3: Create role assignment history (with timezone-aware datetimes)
        self.a1 = RoleAssignmentHistory.objects.create(
            user=self.u1,
            role=self.r_admin,
            valid_from=timezone.make_aware(datetime(2025, 1, 1)),
            valid_to=timezone.make_aware(datetime(2025, 6, 30)),
        )
        self.a2 = RoleAssignmentHistory.objects.create(
            user=self.u1,
            role=self.r_view,
            valid_from=timezone.make_aware(datetime(2025, 7, 1)),
            valid_to=None,
        )
        self.a3 = RoleAssignmentHistory.objects.create(
            user=self.u2,
            role=self.r_view,
            valid_from=timezone.make_aware(datetime(2025, 3, 1)),
            valid_to=timezone.make_aware(datetime(2025, 3, 31)),
        )

    def _get(self, **params):
        url = reverse("role-assignments-list")  # -> /resources/role-assignments/
        return self.client.get(url, params)

    def test_list_all(self):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json()), 3)

    def test_filter_by_user(self):
        resp = self._get(user_id=self.u1.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data), 2)
        # all items belong to u1
        self.assertTrue(all(item["user"]["id"] == self.u1.id or item["user"] == self.u1.id for item in data))

    def test_filter_by_role(self):
        resp = self._get(role_id=self.r_view.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertTrue(all(
            (item.get("role", {}).get("id") == self.r_view.id) or (item.get("role") == self.r_view.id)
            for item in data
        ))

    def test_filter_by_validity_window_overlap(self):
        # Window that overlaps a1 (ends 2025-06-30) and a2 (starts 2025-07-01) differently
        resp = self._get(valid_from="2025-06-15", valid_to="2025-07-15")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in resp.json()}
        # Overlap logic should include a1 (ends after 06-15) and a2 (starts before 07-15)
        self.assertIn(self.a1.id, ids)
        self.assertIn(self.a2.id, ids)

    def test_only_valid_from(self):
        # “still valid on/after” 2025-07-01 should include a2 (open-ended) and exclude a1 (ended 2025-06-30)
        resp = self._get(valid_from="2025-07-01")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in resp.json()}
        self.assertIn(self.a2.id, ids)
        self.assertNotIn(self.a1.id, ids)

    def test_only_valid_to(self):
        # “started on/before” 2025-03-15 → includes a1 (from Jan) and a3 (from Mar 1), may exclude a2 (starts July)
        resp = self._get(valid_to="2025-03-15")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in resp.json()}
        self.assertIn(self.a1.id, ids)
        self.assertIn(self.a3.id, ids)
        self.assertNotIn(self.a2.id, ids)

    def test_invalid_dates_are_ignored(self):
        # parse_date(None/invalid) yields None; our view skips date filters in that case
        resp = self._get(valid_from="not-a-date", valid_to="also-bad")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json()), 3)

    def test_ordering_is_stable(self):
        # Expect ordering by user_id, role_id, valid_from (see view)
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Quick sanity: first element should be the smallest (user_id, role_id, valid_from)
        # Not strict equality check (since PKs depend on DB), but check monotonic non-decreasing triplets
        def key(row):
            # Handle nested vs PK-only serializers gracefully
            user_id = row["user"]["id"] if isinstance(row.get("user"), dict) else row.get("user")
            role_id = row["role"]["id"] if isinstance(row.get("role"), dict) else row.get("role")
            return (user_id, role_id, row["valid_from"])
        keys = [key(r) for r in data]
        self.assertEqual(keys, sorted(keys))

class RoleManagementApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Reader (not staff)
        self.user = get_user_model().objects.create_user(password="pw12345", email = "test_email@gmail.com")
        # Admin
        self.admin = get_user_model().objects.create_user(password="pw123456", email = "admin_test_email@gmail.com", is_staff = True)

    def test_create_requires_admin(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(reverse("roles-list"), {"role_name": "Editor"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_update_delete_happy_path(self):
        self.client.force_authenticate(self.admin)

        # create
        r = self.client.post(reverse("roles-list"), {"role_name": "Editor"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        rid = r.json()["id"]

        # patch (partial)
        r = self.client.patch(reverse("roles-detail", args=[rid]), {"role_name": "EditorPlus"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()["role_name"], "EditorPlus")

        # uniqueness (case-insensitive)
        self.client.post(reverse("roles-list"), {"role_name": "Viewer"}, format="json")
        r = self.client.patch(reverse("roles-detail", args=[rid]), {"role_name": "viewer"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

        # delete
        r = self.client.delete(reverse("roles-detail", args=[rid]))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)

class RoleAssignmentPatchApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        AuthUser = get_user_model()
        # admin vs non-admin
        self.non_admin = AuthUser.objects.create_user(email="reader@example.com", password="pw")
        self.admin = AuthUser.objects.create_user(email="admin@example.com", password="pw", is_staff=True)

        # FK chain for Users
        Countries = dj_apps.get_model('groups', 'Countries')
        CountryStates = dj_apps.get_model('groups', 'CountryStates')
        Tracks = dj_apps.get_model('groups', 'Tracks')
        Users = dj_apps.get_model('users', 'User')

        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        track = Tracks.objects.create(track_name="Data Science", state=state)

        self.u1 = Users.objects.create(first_name="A", last_name="U", email="u1@example.com", track=track, state=state)

        self.r_admin = Roles.objects.create(role_name="admin")
        self.r_view  = Roles.objects.create(role_name="viewer")

        # Active assignment (open-ended)
        self.a = RoleAssignmentHistory.objects.create(
            user=self.u1,
            role=self.r_view,
            valid_from=timezone.make_aware(datetime(2025, 1, 1)),
            valid_to=None,
        )

    def _url(self, pk):
        return reverse("role-assignments-detail", args=[pk])

    def test_patch_requires_admin(self):
        # unauthenticated -> 401
        resp = self.client.patch(self._url(self.a.id), {"role_id": self.r_admin.id}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # non-admin -> 403
        self.client.force_authenticate(self.non_admin)
        resp = self.client.patch(self._url(self.a.id), {"role_id": self.r_admin.id}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_change_role(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(self._url(self.a.id), {"role_id": self.r_admin.id}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["role"]["id"], self.r_admin.id)

    def test_patch_close_assignment_with_valid_to(self):
        self.client.force_authenticate(self.admin)
        close_dt = timezone.make_aware(datetime(2025, 6, 30))
        resp = self.client.patch(self._url(self.a.id), {"valid_to": close_dt.isoformat()}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(resp.json()["valid_to"])

    def test_patch_invalid_date_order(self):
        self.client.force_authenticate(self.admin)
        # valid_to before valid_from -> 400
        bad_dt = timezone.make_aware(datetime(2024, 12, 31))
        resp = self.client.patch(self._url(self.a.id), {"valid_to": bad_dt.isoformat()}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)



    # ===============================REVOKE ROLES FUNCTIONS===============================
# if not Roles.objects.filter(role_name='basic_user').exists():
#     basic_role = Roles.objects.create(role_name='basic_user')
#     print(f"Created role: {basic_role.role_name}")
# else:
#     print("basic_user role already exists")
# logger = logging.getLogger(__name__) 

class TestRevokeUserRole(TestCase):
    def setUp(self):  # Changed from setup_users_and_roles
        """Set up test data for revoke_user_role tests"""
        # Create FK chain for Users
        Countries = dj_apps.get_model('groups', 'Countries')
        CountryStates = dj_apps.get_model('groups', 'CountryStates')
        Tracks = dj_apps.get_model('groups', 'Tracks')
        Users = dj_apps.get_model('users', 'User')

        # Create required FK objects
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="Data Science", state=self.state)

        # Create test user 
        self.user = Users.objects.create(
            first_name="John",
            last_name="Doe",
            email="user@test.com",
            track=self.track,
            state=self.state,
        )

        # Create test roles
        self.student = Roles.objects.create(role_name="student")
        self.mentor = Roles.objects.create(role_name="mentor")
        self.basic = Roles.objects.create(role_name="basic_user")

    def setup_users_and_roles(self, db):
        # Users
        self.user = User.objects.create(email="user@test.com", password="pw12345")
        # Roles
        self.student = Roles.objects.create(role_name="student")
        self.mentor = Roles.objects.create(role_name="mentor")
        self.basic = Roles.objects.create(role_name="basic_user")

    def test_revoke_closes_history_and_removes_group(self):
        grant_role(self.user, self.student)
        assert RoleAssignmentHistory.objects.filter(user=self.user, role=self.student, valid_to__isnull=True).exists()
        assert self.user.groups.filter(name="student").exists()

        revoke_role(self.user, self.student)

        hist = RoleAssignmentHistory.objects.get(user=self.user, role=self.student)
        assert hist.valid_to is not None
        assert not self.user.groups.filter(name="student").exists()

    def test_revoke_assigns_default_if_no_other_roles(self):
        grant_role(self.user, self.student)
        revoke_role(self.user, self.student)

        # student role closed
        assert not RoleAssignmentHistory.objects.filter(user=self.user, role=self.student, valid_to__isnull=True).exists()
        # default role active
        assert RoleAssignmentHistory.objects.filter(user=self.user, role=self.basic, valid_to__isnull=True).exists()
        assert self.user.groups.filter(name="basic_user").exists()

    def test_revoke_does_not_assign_default_if_other_active_roles(self):
        grant_role(self.user, self.student)
        grant_role(self.user, self.mentor)

        revoke_role(self.user, self.student)

        # mentor role still active
        assert RoleAssignmentHistory.objects.filter(user=self.user, role=self.mentor, valid_to__isnull=True).exists()
        # no basic_user assigned
        assert not RoleAssignmentHistory.objects.filter(user=self.user, role=self.basic, valid_to__isnull=True).exists()

    def test_revoke_is_idempotent(self):
        grant_role(self.user, self.student)
        revoke_role(self.user, self.student)
        # second revoke should not break anything
        revoke_role(self.user, self.student)

        hist = RoleAssignmentHistory.objects.get(user=self.user, role=self.student)
        assert hist.valid_to is not None
        assert not self.user.groups.filter(name="student").exists()

    def test_revoke_backdated_end_date(self):
        start_time = timezone.now()
        grant_role(self.user, self.student, start=start_time)
        backdated_end = start_time + timezone.timedelta(days=1)

        revoke_role(self.user, self.student, end=backdated_end)

        hist = RoleAssignmentHistory.objects.get(user=self.user, role=self.student)
        assert hist.valid_to is not None
        assert hist.valid_to >= backdated_end

    # User = get_user_model()

    # # Get your admin user
    # user = User.objects.get(email='test@gmail.com')
    # print(f"Testing with user: {user.email}")

    # # Get or create a role
    # role = Roles.objects.first()
    # if not role:
    #     role = Roles.objects.create(role_name='test_role')
    #     print(f"Created role: {role.role_name}")
    # else:
    #     print(f"Using role: {role.role_name}")

    # # Test grant
    # print("\n=== GRANTING ROLE ===")
    # grant_role(user, role)
    # print("Role granted")

    # # Check groups
    # print(f"User groups: {list(user.groups.all())}")

    # # Test revoke
    # print("\n=== REVOKING ROLE ===")
    # revoke_role(user, role)
    # print("Role revoked")

    # # Check groups again
    # print(f"User groups after revoke: {list(user.groups.all())}")

    # # Check history
    # from apps.resources.models import RoleAssignmentHistory
    # history = RoleAssignmentHistory.objects.filter(user=user, role=role)
    # print(f"\nRole history entries: {history.count()}")
    # for entry in history:
    #     print(f"  - {entry.valid_from} to {entry.valid_to or 'present'}")


class CreateRoleServiceTests(TestCase):
    """Test the create_role service function"""

    def test_create_role_success(self):
        """Test successful role creation"""
        role_name = "test_mentor"
        role = create_role(role_name)

        # Verify role was created
        self.assertEqual(role.role_name, role_name)
        self.assertTrue(Roles.objects.filter(role_name=role_name).exists())

        # Verify Django group was created
        self.assertTrue(Group.objects.filter(name=role_name).exists())

    def test_create_role_empty_name_fails(self):
        """Test that empty role name raises ValidationError"""
        with self.assertRaises(ValidationError) as cm:
            create_role("")
        self.assertIn("Role name cannot be empty", str(cm.exception))

        with self.assertRaises(ValidationError) as cm:
            create_role("   ")  # whitespace only
        self.assertIn("Role name cannot be empty", str(cm.exception))

        with self.assertRaises(ValidationError) as cm:
            create_role(None)
        self.assertIn("Role name cannot be empty", str(cm.exception))

    def test_create_role_duplicate_fails(self):
        """Test that duplicate role name raises ValidationError"""
        role_name = "duplicate_role"

        # Create first role
        create_role(role_name)

        # Try to create duplicate (should fail)
        with self.assertRaises(ValidationError) as cm:
            create_role(role_name)
        self.assertIn("already exists", str(cm.exception))

    def test_create_role_case_insensitive_duplicate_fails(self):
        """Test that case-insensitive duplicate role name raises ValidationError"""
        # Create role with lowercase
        create_role("mentor")

        # Try to create with different case (should fail)
        with self.assertRaises(ValidationError) as cm:
            create_role("MENTOR")
        self.assertIn("already exists", str(cm.exception))

        with self.assertRaises(ValidationError) as cm:
            create_role("Mentor")
        self.assertIn("already exists", str(cm.exception))

    def test_create_role_strips_whitespace(self):
        """Test that role name whitespace is stripped"""
        role = create_role("  admin_role  ")
        self.assertEqual(role.role_name, "admin_role")

    def test_create_role_transaction_rollback_on_error(self):
        """Test that transaction is rolled back if Django group creation fails"""
        # This is harder to test directly, but we can verify state after error
        role_name = "test_transaction"

        # Create role successfully first
        role = create_role(role_name)
        initial_role_count = Roles.objects.count()
        initial_group_count = Group.objects.count()

        # Try to create duplicate (should fail and not increase counts)
        with self.assertRaises(ValidationError):
            create_role(role_name)

        self.assertEqual(Roles.objects.count(), initial_role_count)
        self.assertEqual(Group.objects.count(), initial_group_count)


class CreateRoleAPITests(TestCase):
    """Test the POST /api/v1/roles/ endpoint"""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()

        # Regular user (not admin)
        self.user = User.objects.create_user(
            email="user@test.com",
            password="testpass123"
        )

        # Admin user
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="adminpass123",
            is_staff=True
        )

    def test_create_role_unauthenticated_fails(self):
        """Test that unauthenticated requests are rejected"""
        url = reverse("v1-roles-list")  # /resources/api/v1/roles/
        data = {"role_name": "new_role"}

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_role_non_admin_fails(self):
        """Test that non-admin users cannot create roles"""
        self.client.force_authenticate(user=self.user)
        url = reverse("v1-roles-list")
        data = {"role_name": "new_role"}

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_role_admin_success(self):
        """Test successful role creation by admin"""
        self.client.force_authenticate(user=self.admin)
        url = reverse("v1-roles-list")
        data = {"role_name": "mentor"}

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check response data
        response_data = response.json()
        self.assertEqual(response_data["role_name"], "mentor")
        self.assertIn("id", response_data)

        # Verify role was created in database
        self.assertTrue(Roles.objects.filter(role_name="mentor").exists())

        # Verify Django group was created
        self.assertTrue(Group.objects.filter(name="mentor").exists())

    def test_create_role_empty_name_fails(self):
        """Test that empty role name is rejected"""
        self.client.force_authenticate(user=self.admin)
        url = reverse("v1-roles-list")

        # Test empty string 
        response = self.client.post(url, {"role_name": ""}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Serializer validation returns different format
        response_data = response.json()
        self.assertTrue("role_name" in response_data or "error" in response_data)

        # Test whitespace only 
        response = self.client.post(url, {"role_name": "   "}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_role_duplicate_fails(self):
        """Test that duplicate role name is rejected"""
        self.client.force_authenticate(user=self.admin)
        url = reverse("v1-roles-list")
        data = {"role_name": "duplicate_test"}

        # Create first role
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Try to create duplicate 
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()

        has_error = "role_name" in response_data or "error" in response_data
        self.assertTrue(has_error)

        # Check that the error mentions duplicates/exists
        error_text = str(response_data).lower()
        self.assertIn("already exists", error_text)

    def test_create_role_case_insensitive_duplicate_fails(self):
        """Test that case-insensitive duplicate is rejected"""
        self.client.force_authenticate(user=self.admin)
        url = reverse("v1-roles-list")

        # Create role with lowercase
        response = self.client.post(url, {"role_name": "admin"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Try to create with uppercase - this triggers serializer validation
        response = self.client.post(url, {"role_name": "ADMIN"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        # Could be either serializer format {"role_name": ["error message"]} or service format {"error": "message"}
        has_error = "role_name" in response_data or "error" in response_data
        self.assertTrue(has_error)

        # Check that the error mentions duplicates/exists
        error_text = str(response_data).lower()
        self.assertIn("already exists", error_text)

    def test_create_role_missing_role_name_fails(self):
        """Test that missing role_name field is rejected"""
        self.client.force_authenticate(user=self.admin)
        url = reverse("v1-roles-list")

        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_role_whitespace_stripped(self):
        """Test that role name whitespace is properly stripped"""
        self.client.force_authenticate(user=self.admin)
        url = reverse("v1-roles-list")
        data = {"role_name": "  student_mentor  "}

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that whitespace was stripped in response and database
        self.assertEqual(response.json()["role_name"], "student_mentor")
        role = Roles.objects.get(id=response.json()["id"])
        self.assertEqual(role.role_name, "student_mentor")

    def test_create_role_both_endpoints_work(self):
        """Test that both original and v1 endpoints work"""
        self.client.force_authenticate(user=self.admin)

        # Test v1 endpoint
        v1_url = reverse("v1-roles-list")  # /resources/api/v1/roles/
        response = self.client.post(v1_url, {"role_name": "v1_role"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Test original endpoint
        original_url = reverse("roles-list")  # /resources/roles/
        response = self.client.post(original_url, {"role_name": "original_role"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify both roles exist
        self.assertTrue(Roles.objects.filter(role_name="v1_role").exists())
        self.assertTrue(Roles.objects.filter(role_name="original_role").exists())


class CreateRoleIntegrationTests(TestCase):
    """Integration tests for role creation with other systems"""

    def setUp(self):
        self.client = APIClient()
        User = get_user_model()

        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="adminpass123",
            is_staff=True
        )

    def test_created_role_can_be_assigned_to_user(self):
        """Test that a newly created role can be assigned to users"""
        # Create FK chain for Users
        Countries = dj_apps.get_model('groups', 'Countries')
        CountryStates = dj_apps.get_model('groups', 'CountryStates')
        Tracks = dj_apps.get_model('groups', 'Tracks')
        Users = dj_apps.get_model('users', 'User')

        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        track = Tracks.objects.create(track_name="Data Science", state=state)

        user = Users.objects.create(
            first_name="Test",
            last_name="User",
            email="testuser@test.com",
            track=track,
            state=state
        )

        # Create role via API
        self.client.force_authenticate(user=self.admin)
        url = reverse("v1-roles-list")
        response = self.client.post(url, {"role_name": "integration_mentor"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Get the created role
        role = Roles.objects.get(role_name="integration_mentor")

        # Assign role to user using service layer
        grant_role(user, role)

        # Verify user has the role
        self.assertTrue(
            RoleAssignmentHistory.objects.filter(
                user=user,
                role=role,
                valid_to__isnull=True
            ).exists()
        )

        # Verify user is in corresponding Django group
        self.assertTrue(user.groups.filter(name="integration_mentor").exists())

    def test_created_role_serializer_validation_still_works(self):
        """Test that serializer validation still works after service layer integration"""
        self.client.force_authenticate(user=self.admin)
        url = reverse("v1-roles-list")

        # Create role
        response = self.client.post(url, {"role_name": "validation_test"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Try to create role with same name (serializer should catch this)
        response = self.client.post(url, {"role_name": "validation_test"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Check that error mentions duplicates/exists (format may vary)
        response_data = response.json()
        error_text = str(response_data).lower()
        self.assertIn("already exists", error_text)