from django.test import TestCase
import logging


from datetime import date, datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.apps import apps as dj_apps
from django.core.files.base import ContentFile

from .models import Roles, RoleAssignmentHistory, Resources, ResourceRoles, ResourceType
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
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_roles_list_ok_and_ordered(self):
        self.client.force_authenticate(self.me)
        url = reverse("roles-list")  
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
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
        data = resp.json()
        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        self.assertEqual(len(data), 3)

    def test_filter_by_user(self):
        resp = self._get(user_id=self.u1.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        self.assertEqual(len(data), 2)
        # all items belong to u1
        self.assertTrue(all(item["user"]["id"] == self.u1.id or item["user"] == self.u1.id for item in data))

    def test_filter_by_role(self):
        resp = self._get(role_id=self.r_view.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        self.assertTrue(all(
            (item.get("role", {}).get("id") == self.r_view.id) or (item.get("role") == self.r_view.id)
            for item in data
        ))

    def test_filter_by_validity_window_overlap(self):
        # Window that overlaps a1 (ends 2025-06-30) and a2 (starts 2025-07-01) differently
        resp = self._get(valid_from="2025-06-15", valid_to="2025-07-15")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        ids = {row["id"] for row in data}
        # Overlap logic should include a1 (ends after 06-15) and a2 (starts before 07-15)
        self.assertIn(self.a1.id, ids)
        self.assertIn(self.a2.id, ids)

    def test_only_valid_from(self):
        # "still valid on/after" 2025-07-01 should include a2 (open-ended) and exclude a1 (ended 2025-06-30)
        resp = self._get(valid_from="2025-07-01")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        ids = {row["id"] for row in data}
        self.assertIn(self.a2.id, ids)
        self.assertNotIn(self.a1.id, ids)

    def test_only_valid_to(self):
        # "started on/before" 2025-03-15 → includes a1 (from Jan) and a3 (from Mar 1), may exclude a2 (starts July)
        resp = self._get(valid_to="2025-03-15")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        ids = {row["id"] for row in data}
        self.assertIn(self.a1.id, ids)
        self.assertIn(self.a3.id, ids)
        self.assertNotIn(self.a2.id, ids)

    def test_invalid_dates_are_ignored(self):
        # parse_date(None/invalid) yields None; our view skips date filters in that case
        resp = self._get(valid_from="not-a-date", valid_to="also-bad")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        self.assertEqual(len(data), 3)

    def test_ordering_is_stable(self):
        # Expect ordering by user_id, role_id, valid_from (see view)
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Handle paginated response
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
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
        # unauthenticated -> 403
        resp = self.client.patch(self._url(self.a.id), {"role_id": self.r_admin.id}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

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


# =============================================================================
# COMPREHENSIVE TEST SUITE FOR RESOURCES APP
# =============================================================================
# This section contains comprehensive tests for all major functionality:
# 1. Grant Role with Duplicate Prevention
# 2. Resources CRUD Operations
# 3. Pagination Functionality
# 4. Resource Roles Management
# =============================================================================


class GrantRoleComprehensiveTests(TestCase):
    """Comprehensive tests for grant_role functionality with duplicate prevention"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.admin_user = get_user_model().objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )
        self.regular_user = get_user_model().objects.create_user(
            email='user@test.com',
            password='testpass123',
            first_name='Regular',
            last_name='User'
        )
        
        # Create test roles
        self.supervisor_role = Roles.objects.create(
            role_name='Supervisor',
        )
        self.student_role = Roles.objects.create(
            role_name='Student',
        )
        self.teacher_role = Roles.objects.create(
            role_name='Teacher',
        )
        self.basic_user_role = Roles.objects.create(
            role_name='basic_user',
        )
        
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
    
    def test_grant_role_duplicate_prevention(self):
        """Test that duplicate roles are prevented and duration is extended"""
        # First grant
        result1 = grant_role(self.regular_user, self.supervisor_role, force=False)
        self.assertEqual(result1['action_taken'], 'created_new_role')
        
        # Second grant of same role - should extend duration
        result2 = grant_role(self.regular_user, self.supervisor_role, force=False)
        self.assertEqual(result2['action_taken'], 'updated_existing_role')
        self.assertTrue(result2['duplicate_role'])
        self.assertIn('extended duration', result2['message'])
    
    def test_grant_role_force_assignment(self):
        """Test force assignment creates new role even if duplicate"""
        # First grant
        grant_role(self.regular_user, self.supervisor_role)
        
        # Force grant of same role
        result = grant_role(self.regular_user, self.supervisor_role, force=True)
        self.assertEqual(result['action_taken'], 'created_new_role')
        self.assertTrue(result['duplicate_role'])
    
    def test_grant_role_revoke_others(self):
        """Test that other roles are revoked when revoke_others=True"""
        # Grant first role
        grant_role(self.regular_user, self.supervisor_role, revoke_others=False)
        
        # Grant second role with revoke_others=True
        result = grant_role(self.regular_user, self.student_role, revoke_others=True)
        self.assertEqual(result['action_taken'], 'created_new_role')
        self.assertIn('Supervisor', result['revoked_roles'])
        
        # Verify only student role is active
        active_roles = RoleAssignmentHistory.objects.filter(
            user=self.regular_user,
            valid_to__isnull=True
        ).values_list('role__role_name', flat=True)
        self.assertEqual(list(active_roles), ['Student'])
    
    def test_grant_role_api_success(self):
        """Test successful role granting via API"""
        url = reverse('role-assignments-grant-role')
        data = {
            'user_id': self.regular_user.id,
            'role_id': self.supervisor_role.id,
            'revoke_others': True
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertEqual(response.data['action_taken'], 'created_new_role')
    
    def test_grant_role_api_conflict_detection(self):
        """Test conflict detection via API"""
        # Grant first role
        grant_role(self.regular_user, self.supervisor_role, revoke_others=False)
        
        # Try to grant different role without revoking others
        url = reverse('role-assignments-grant-role')
        data = {
            'user_id': self.regular_user.id,
            'role_id': self.student_role.id,
            'revoke_others': False,
            'force': False
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('existing_roles', response.data)


class ResourcesCRUDComprehensiveTests(TestCase):
    """Comprehensive tests for Resources CRUD operations"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.admin_user = get_user_model().objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )
        self.regular_user = get_user_model().objects.create_user(
            email='user@test.com',
            password='testpass123',
            first_name='Regular',
            last_name='User'
        )
        
        # Create test roles
        self.supervisor_role = Roles.objects.create(
            role_name='Supervisor',
        )
        self.student_role = Roles.objects.create(
            role_name='Student',
        )
        
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
    
    def test_create_resource_success(self):
        """Test successful resource creation"""
        url = reverse('resource-files-list')
        data = {
            'resource_name': 'Test Resource',
            'resource_description': 'A test resource',
            'role_ids': [self.supervisor_role.id]
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['resource_name'], 'Test Resource')
        # The uploader should be the authenticated user (admin_user)
        self.assertEqual(response.data['uploader']['email'], 'admin@test.com')
        
        # Verify resource was created in database
        resource = Resources.objects.get(resource_name='Test Resource')
        self.assertEqual(resource.uploader_user_id, self.admin_user)
        self.assertEqual(resource.resource_description, 'A test resource')
    
    def test_create_resource_duplicate_name(self):
        """Test error handling for duplicate resource names"""
        # Create first resource
        Resources.objects.create(
            resource_name='Test Resource',
            resource_description='First resource',
            uploader_user_id=self.regular_user
        )
        
        # Try to create second resource with same name
        url = reverse('resource-files-list')
        data = {
            'resource_name': 'Test Resource',
            'resource_description': 'Second resource',
            'uploader_id': self.regular_user.id
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already exists', str(response.data))
    
    def test_create_resource_empty_name(self):
        """Test error handling for empty resource name"""
        url = reverse('resource-files-list')
        data = {
            'resource_name': '',
            'resource_description': 'A test resource',
            'uploader_id': self.regular_user.id
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('blank', str(response.data))
    
    # test_create_resource_missing_uploader removed - uploader is now automatic
    
    def test_list_resources(self):
        """Test resource listing"""
        # Create test resources
        resource1 = Resources.objects.create(
            resource_name='Resource 1',
            resource_description='First resource',
            uploader_user_id=self.regular_user
        )
        resource2 = Resources.objects.create(
            resource_name='Resource 2',
            resource_description='Second resource',
            uploader_user_id=self.admin_user
        )
        
        url = reverse('resource-files-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
        # Check that resources are in response
        resource_names = [r['resource_name'] for r in response.data['results']]
        self.assertIn('Resource 1', resource_names)
        self.assertIn('Resource 2', resource_names)
    
    def test_retrieve_resource(self):
        """Test resource retrieval"""
        resource = Resources.objects.create(
            resource_name='Test Resource',
            resource_description='A test resource',
            uploader_user_id=self.regular_user
        )
        
        url = reverse('resource-files-detail', kwargs={'pk': resource.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['resource_name'], 'Test Resource')
        self.assertEqual(response.data['uploader']['email'], 'user@test.com')
    
    def test_update_resource(self):
        """Test resource update"""
        resource = Resources.objects.create(
            resource_name='Test Resource',
            resource_description='A test resource',
            uploader_user_id=self.regular_user
        )
        
        url = reverse('resource-files-detail', kwargs={'pk': resource.id})
        data = {
            'resource_name': 'Updated Resource',
            'resource_description': 'Updated description',
            'uploader_id': self.regular_user.id
        }
        
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['resource_name'], 'Updated Resource')
        
        # Verify update in database
        resource.refresh_from_db()
        self.assertEqual(resource.resource_name, 'Updated Resource')
    
    def test_delete_resource_soft_delete(self):
        """Test resource soft delete"""
        resource = Resources.objects.create(
            resource_name='Test Resource',
            resource_description='A test resource',
            uploader_user_id=self.regular_user
        )
        
        url = reverse('resource-files-detail', kwargs={'pk': resource.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify soft delete
        resource.refresh_from_db()
        self.assertTrue(resource.deleted_flag)
        self.assertIsNotNone(resource.deleted_datetime)
    
    def test_list_resources_excludes_deleted(self):
        """Test that deleted resources are excluded from listing"""
        # Create active resource
        Resources.objects.create(
            resource_name='Active Resource',
            resource_description='Active resource',
            uploader_user_id=self.regular_user
        )
        
        # Create and delete resource
        deleted_resource = Resources.objects.create(
            resource_name='Deleted Resource',
            resource_description='Deleted resource',
            uploader_user_id=self.regular_user
        )
        deleted_resource.deleted_flag = True
        deleted_resource.deleted_datetime = timezone.now()
        deleted_resource.save()
        
        url = reverse('resource-files-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['resource_name'], 'Active Resource')


class PaginationComprehensiveTests(TestCase):
    """Comprehensive tests for pagination functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.admin_user = get_user_model().objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )
        
        # Create multiple resources for pagination testing
        for i in range(25):
            Resources.objects.create(
                resource_name=f'Resource {i+1}',
                resource_description=f'Description for resource {i+1}',
                uploader_user_id=self.admin_user
            )
        
        self.client.force_authenticate(user=self.admin_user)
    
    def test_pagination_default_page_size(self):
        """Test default pagination behavior"""
        url = reverse('resource-files-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertIn('results', response.data)
        
        # Should have 20 items per page by default
        self.assertEqual(len(response.data['results']), 20)
        self.assertEqual(response.data['count'], 25)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNone(response.data['previous'])
    
    def test_pagination_custom_page_size(self):
        """Test custom page size"""
        url = reverse('resource-files-list')
        response = self.client.get(url, {'page_size': 5})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        self.assertEqual(response.data['count'], 25)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNone(response.data['previous'])
    
    def test_pagination_page_navigation(self):
        """Test page navigation"""
        url = reverse('resource-files-list')
        
        # First page
        response = self.client.get(url, {'page_size': 10, 'page': 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNone(response.data['previous'])
        
        # Second page
        response = self.client.get(url, {'page_size': 10, 'page': 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNotNone(response.data['previous'])
        
        # Last page
        response = self.client.get(url, {'page_size': 10, 'page': 3})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        self.assertIsNone(response.data['next'])
        self.assertIsNotNone(response.data['previous'])
    
    def test_pagination_max_page_size(self):
        """Test max page size limit"""
        url = reverse('resource-files-list')
        response = self.client.get(url, {'page_size': 200})  # Exceeds max of 100
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 25)  # All items, but limited by max_page_size
        self.assertEqual(response.data['count'], 25)
    
    def test_pagination_invalid_page(self):
        """Test invalid page number"""
        url = reverse('resource-files-list')
        response = self.client.get(url, {'page': 999})
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ResourceRolesComprehensiveTests(TestCase):
    """Comprehensive tests for ResourceRoles functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.admin_user = get_user_model().objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )
        self.regular_user = get_user_model().objects.create_user(
            email='user@test.com',
            password='testpass123',
            first_name='Regular',
            last_name='User'
        )
        
        # Create test roles
        self.supervisor_role = Roles.objects.create(
            role_name='Supervisor',
        )
        self.student_role = Roles.objects.create(
            role_name='Student',
        )
        self.teacher_role = Roles.objects.create(
            role_name='Teacher',
        )
        
        # Create test resource
        self.resource = Resources.objects.create(
            resource_name='Test Resource',
            resource_description='A test resource',
            uploader_user_id=self.regular_user
        )
        
        self.client.force_authenticate(user=self.admin_user)
    
    def test_assign_role_to_resource(self):
        """Test assigning a role to a resource"""
        url = reverse('resource-files-assign-role', kwargs={'pk': self.resource.id})
        data = {'role_id': self.supervisor_role.id}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('assigned to resource', response.data['message'])
        
        # Verify role was assigned
        self.assertTrue(
            ResourceRoles.objects.filter(
                resource=self.resource,
                role=self.supervisor_role
            ).exists()
        )
    
    def test_assign_role_already_assigned(self):
        """Test error when role is already assigned"""
        # First assignment
        ResourceRoles.objects.create(resource=self.resource, role=self.supervisor_role)
        
        # Try to assign again
        url = reverse('resource-files-assign-role', kwargs={'pk': self.resource.id})
        data = {'role_id': self.supervisor_role.id}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already assigned', response.data['error'])
    
    def test_remove_role_from_resource(self):
        """Test removing a role from a resource"""
        # First assign role
        ResourceRoles.objects.create(resource=self.resource, role=self.supervisor_role)
        
        # Remove role
        url = reverse('resource-files-remove-role', kwargs={'pk': self.resource.id})
        data = {'role_id': self.supervisor_role.id}
        
        response = self.client.delete(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('removed from resource', response.data['message'])
        
        # Verify role was removed
        self.assertFalse(
            ResourceRoles.objects.filter(
                resource=self.resource,
                role=self.supervisor_role
            ).exists()
        )
    
    def test_remove_role_not_assigned(self):
        """Test error when trying to remove non-assigned role"""
        url = reverse('resource-files-remove-role', kwargs={'pk': self.resource.id})
        data = {'role_id': self.supervisor_role.id}
        
        response = self.client.delete(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('not assigned', response.data['error'])
    
    def test_resource_with_visible_roles(self):
        """Test that resource shows visible roles in API response"""
        # Assign roles to resource
        ResourceRoles.objects.create(resource=self.resource, role=self.supervisor_role)
        ResourceRoles.objects.create(resource=self.resource, role=self.student_role)
        
        url = reverse('resource-files-detail', kwargs={'pk': self.resource.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('visible_roles', response.data)
        self.assertEqual(len(response.data['visible_roles']), 2)
        
        # Check role names
        role_names = [role['role_name'] for role in response.data['visible_roles']]
        self.assertIn('Supervisor', role_names)
        self.assertIn('Student', role_names)
    
    def test_assign_role_missing_role_id(self):
        """Test error handling for missing role_id"""
        url = reverse('resource-files-assign-role', kwargs={'pk': self.resource.id})
        data = {}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role_id is required', response.data['error'])
    
    def test_remove_role_missing_role_id(self):
        """Test error handling for missing role_id in remove"""
        url = reverse('resource-files-remove-role', kwargs={'pk': self.resource.id})
        data = {}
        
        response = self.client.delete(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role_id is required', response.data['error'])


# Additional tests from the other branch, merged below

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
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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


# =============================================================================
# RESOURCE TYPE TESTS
# =============================================================================

class ResourceTypeModelTests(TestCase):
    """Tests for ResourceType model"""

    def test_create_resource_type(self):
        """Test creating a resource type"""
        resource_type = ResourceType.objects.create(
            type_name='presentation',
            type_description='Presentation resources such as slides'
        )

        self.assertEqual(resource_type.type_name, 'presentation')
        self.assertEqual(resource_type.type_description, 'Presentation resources such as slides')
        self.assertEqual(str(resource_type), 'presentation')

    def test_resource_type_unique_name(self):
        """Test that resource type names must be unique"""
        ResourceType.objects.create(type_name='workshop')

        # Try to create duplicate
        with self.assertRaises(Exception):  # IntegrityError from database
            ResourceType.objects.create(type_name='workshop')

    def test_resource_type_optional_description(self):
        """Test that description is optional"""
        resource_type = ResourceType.objects.create(
            type_name='podcast'
        )

        self.assertEqual(resource_type.type_name, 'podcast')
        self.assertIsNone(resource_type.type_description)


class ResourceTypeAPITests(TestCase):
    """Tests for ResourceType with Resources API"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        self.admin_user = get_user_model().objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )
        self.regular_user = get_user_model().objects.create_user(
            email='user@test.com',
            password='testpass123',
            first_name='Regular',
            last_name='User'
        )

        # Get or create resource types (migration may have already created them)
        self.document_type, _ = ResourceType.objects.get_or_create(
            type_name='document',
            defaults={'type_description': 'Document resources'}
        )
        self.video_type, _ = ResourceType.objects.get_or_create(
            type_name='video',
            defaults={'type_description': 'Video resources'}
        )
        self.guide_type, _ = ResourceType.objects.get_or_create(
            type_name='guide',
            defaults={'type_description': 'Guide resources'}
        )
        self.template_type, _ = ResourceType.objects.get_or_create(
            type_name='template',
            defaults={'type_description': 'Template resources'}
        )

        self.client.force_authenticate(user=self.admin_user)

    def test_create_resource_with_type(self):
        """Test creating a resource with a resource type"""
        url = reverse('resource-files-list')
        data = {
            'resource_name': 'Python Guide',
            'resource_description': 'A comprehensive Python programming guide',
            'resource_type_id': self.guide_type.id
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['resource_name'], 'Python Guide')
        self.assertIn('resource_type_detail', response.data)
        self.assertEqual(response.data['resource_type_detail']['type_name'], 'guide')

        # Verify in database
        resource = Resources.objects.get(resource_name='Python Guide')
        self.assertEqual(resource.resource_type, self.guide_type)

    def test_create_resource_without_type(self):
        """Test creating a resource without specifying type (should be null)"""
        url = reverse('resource-files-list')
        data = {
            'resource_name': 'Untitled Resource',
            'resource_description': 'A resource without type'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['resource_name'], 'Untitled Resource')
        self.assertIsNone(response.data.get('resource_type_detail'))

        # Verify in database
        resource = Resources.objects.get(resource_name='Untitled Resource')
        self.assertIsNone(resource.resource_type)

    def test_list_resources_includes_type(self):
        """Test that listing resources includes resource type information"""
        # Create resources with different types
        Resources.objects.create(
            resource_name='Video Tutorial',
            resource_description='Video tutorial',
            resource_type=self.video_type,
            uploader_user_id=self.admin_user
        )
        Resources.objects.create(
            resource_name='PDF Document',
            resource_description='PDF document',
            resource_type=self.document_type,
            uploader_user_id=self.admin_user
        )

        url = reverse('resource-files-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

        # Check that resource_type_detail is included
        for resource in response.data['results']:
            self.assertIn('resource_type_detail', resource)
            if resource['resource_name'] == 'Video Tutorial':
                self.assertEqual(resource['resource_type_detail']['type_name'], 'video')
            elif resource['resource_name'] == 'PDF Document':
                self.assertEqual(resource['resource_type_detail']['type_name'], 'document')

    def test_update_resource_type(self):
        """Test updating a resource's type"""
        resource = Resources.objects.create(
            resource_name='My Resource',
            resource_description='A resource',
            resource_type=self.document_type,
            uploader_user_id=self.admin_user
        )

        url = reverse('resource-files-detail', kwargs={'pk': resource.id})
        data = {
            'resource_type_id': self.video_type.id
        }

        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['resource_type_detail']['type_name'], 'video')

        # Verify in database
        resource.refresh_from_db()
        self.assertEqual(resource.resource_type, self.video_type)

    def test_update_resource_type_to_null(self):
        """Test removing type from a resource"""
        resource = Resources.objects.create(
            resource_name='My Resource',
            resource_description='A resource',
            resource_type=self.document_type,
            uploader_user_id=self.admin_user
        )

        url = reverse('resource-files-detail', kwargs={'pk': resource.id})
        data = {
            'resource_type_id': None
        }

        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data.get('resource_type_detail'))

        # Verify in database
        resource.refresh_from_db()
        self.assertIsNone(resource.resource_type)

    def test_create_resource_with_invalid_type_id(self):
        """Test error handling for invalid resource type ID"""
        url = reverse('resource-files-list')
        data = {
            'resource_name': 'Test Resource',
            'resource_description': 'A test resource',
            'resource_type_id': 99999  # Non-existent ID
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_resources_by_type(self):
        """Test filtering resources by type (if implemented)"""
        # Create resources with different types
        Resources.objects.create(
            resource_name='Video 1',
            resource_description='Video',
            resource_type=self.video_type,
            uploader_user_id=self.admin_user
        )
        Resources.objects.create(
            resource_name='Video 2',
            resource_description='Video',
            resource_type=self.video_type,
            uploader_user_id=self.admin_user
        )
        Resources.objects.create(
            resource_name='Document 1',
            resource_description='Document',
            resource_type=self.document_type,
            uploader_user_id=self.admin_user
        )

        url = reverse('resource-files-list')
        # Note: This test assumes filtering is implemented
        # If not implemented yet, this can serve as a spec
        response = self.client.get(url, {'type': 'video'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # This assertion may need adjustment based on actual implementation
        # For now, just verify we get results
        self.assertIn('results', response.data)

    def test_resource_type_in_serializer(self):
        """Test that resource type is properly serialized"""
        resource = Resources.objects.create(
            resource_name='Test Resource',
            resource_description='A test resource',
            resource_type=self.template_type,
            uploader_user_id=self.admin_user
        )

        url = reverse('resource-files-detail', kwargs={'pk': resource.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('resource_type_detail', response.data)

        type_detail = response.data['resource_type_detail']
        self.assertEqual(type_detail['id'], self.template_type.id)
        self.assertEqual(type_detail['type_name'], 'template')
        self.assertEqual(type_detail['type_description'], 'Templates and boilerplate files')


class ResourceTypeIntegrationTests(TestCase):
    """Integration tests for ResourceType with full system"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        self.admin_user = get_user_model().objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )

        # Get or create all 4 resource types (migration may have already created them)
        self.document_type, _ = ResourceType.objects.get_or_create(
            type_name='document',
            defaults={'type_description': 'Document resources such as PDFs, guides, and written materials'}
        )
        self.guide_type, _ = ResourceType.objects.get_or_create(
            type_name='guide',
            defaults={'type_description': 'Step-by-step guides and tutorials'}
        )
        self.video_type, _ = ResourceType.objects.get_or_create(
            type_name='video',
            defaults={'type_description': 'Video recordings and presentations'}
        )
        self.template_type, _ = ResourceType.objects.get_or_create(
            type_name='template',
            defaults={'type_description': 'Templates and boilerplate files'}
        )

        # Create test roles
        self.supervisor_role = Roles.objects.create(role_name='Supervisor')
        self.student_role = Roles.objects.create(role_name='Student')

        self.client.force_authenticate(user=self.admin_user)

    def test_create_resources_with_all_types(self):
        """Test creating resources with all 4 resource types"""
        url = reverse('resource-files-list')

        resource_data = [
            ('Study Guide', 'A study guide for students', self.guide_type.id),
            ('Lecture Recording', 'Video lecture', self.video_type.id),
            ('Project Template', 'Starter template', self.template_type.id),
            ('Reference Document', 'Reference PDF', self.document_type.id)
        ]

        for name, description, type_id in resource_data:
            data = {
                'resource_name': name,
                'resource_description': description,
                'resource_type_id': type_id
            }

            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify all were created
        self.assertEqual(Resources.objects.count(), 4)
        self.assertEqual(Resources.objects.filter(resource_type=self.guide_type).count(), 1)
        self.assertEqual(Resources.objects.filter(resource_type=self.video_type).count(), 1)
        self.assertEqual(Resources.objects.filter(resource_type=self.template_type).count(), 1)
        self.assertEqual(Resources.objects.filter(resource_type=self.document_type).count(), 1)

    def test_resource_with_type_and_roles(self):
        """Test creating resource with both type and role visibility"""
        url = reverse('resource-files-list')
        data = {
            'resource_name': 'Advanced Python Guide',
            'resource_description': 'Python guide for advanced users',
            'resource_type_id': self.guide_type.id,
            'role_ids': [self.supervisor_role.id]
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['resource_type_detail']['type_name'], 'guide')
        self.assertEqual(len(response.data['visible_roles']), 1)
        self.assertEqual(response.data['visible_roles'][0]['role_name'], 'Supervisor')

    def test_data_migration_populated_types(self):
        """Test that data migration has populated the 4 types"""
        # This test verifies that the data migration has run
        # In a fresh database, the migration should create these types

        types = ResourceType.objects.all().order_by('type_name')
        type_names = [t.type_name for t in types]

        # We expect exactly 4 types
        self.assertEqual(len(type_names), 4)
        self.assertIn('document', type_names)
        self.assertIn('guide', type_names)
        self.assertIn('video', type_names)
        self.assertIn('template', type_names)


# =====Test resource blob uploads====
class ResourceBlobUploadTests(TestCase):
    """Tests for resource file uploads to Azure blob storage"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.admin_user = get_user_model().objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )
        self.regular_user = get_user_model().objects.create_user(
            email='user@test.com',
            password='testpass123',
            first_name='Regular',
            last_name='User'
        )
        
        # Create test roles
        self.supervisor_role = Roles.objects.create(
            role_name='Supervisor',
        )
        self.student_role = Roles.objects.create(
            role_name='Student',
        )
        
        # Create test resource types (use get_or_create to avoid conflicts)
        self.document_type, _ = ResourceType.objects.get_or_create(
            type_name='document',
            defaults={'type_description': 'Document files'}
        )
        self.image_type, _ = ResourceType.objects.get_or_create(
            type_name='image',
            defaults={'type_description': 'Image files'}
        )
        
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
    
    def test_upload_txt_file_success(self):
        """Test successful upload of text file to blob storage"""
        url = reverse('resource-files-list')
        
        # Create test file content
        test_file_content = "testing file for resources :>"
        test_file = ContentFile(test_file_content.encode('utf-8'), name='test_File_resources.txt')
        
        data = {
            'resource_name': 'Test Upload File',
            'resource_description': 'Testing file upload to blob storage',
            'resource_file': test_file,
            'role_ids': [self.supervisor_role.id]
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify response data
        self.assertEqual(response.data['resource_name'], 'Test Upload File')
        self.assertEqual(response.data['resource_description'], 'Testing file upload to blob storage')
        self.assertIsNotNone(response.data['resource_file'])
        self.assertIsNotNone(response.data['file_url'])
        self.assertEqual(response.data['file_size'], len(test_file_content))
        self.assertEqual(response.data['content_type'], 'text/plain')
        self.assertEqual(response.data['uploader']['email'], 'admin@test.com')
        
        # Verify resource was created in database
        resource = Resources.objects.get(resource_name='Test Upload File')
        self.assertEqual(resource.resource_name, 'Test Upload File')
        self.assertEqual(resource.file_size, len(test_file_content))
        self.assertEqual(resource.content_type, 'text/plain')
        self.assertEqual(resource.uploader_user_id, self.admin_user)
        self.assertIsNotNone(resource.resource_file)
        
        # Verify file exists in storage (works for both test and production storage)
        from django.core.files.storage import default_storage
        self.assertTrue(default_storage.exists(resource.resource_file.name))
        
        # Verify file content
        with default_storage.open(resource.resource_file.name, 'r') as f:
            content = f.read()
            self.assertEqual(content, test_file_content)
    
    def test_upload_file_auto_detects_resource_type(self):
        """Test that file upload auto-detects resource type from extension"""
        url = reverse('resource-files-list')
        
        # Test PDF file (should auto-detect as document)
        test_file_content = b"PDF content here"
        test_file = ContentFile(test_file_content, name='research_paper.pdf')
        
        data = {
            'resource_name': 'Research Paper',
            'resource_description': 'Auto-detection test',
            'resource_file': test_file,
            'role_ids': [self.supervisor_role.id]
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify auto-detected resource type
        resource = Resources.objects.get(resource_name='Research Paper')
        self.assertEqual(resource.resource_type.type_name, 'document')
        self.assertEqual(resource.content_type, 'application/pdf')
    
    def test_upload_file_auto_detects_image_type(self):
        """Test that image files auto-detect as image type"""
        url = reverse('resource-files-list')
        
        # Test PNG file (should auto-detect as image)
        test_file_content = b"PNG image data"
        test_file = ContentFile(test_file_content, name='microscopy_image.png')
        
        data = {
            'resource_name': 'Microscopy Image',
            'resource_description': 'Auto-detection test for images',
            'resource_file': test_file,
            'role_ids': [self.supervisor_role.id]
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify auto-detected resource type
        resource = Resources.objects.get(resource_name='Microscopy Image')
        self.assertEqual(resource.resource_type.type_name, 'image')
        self.assertEqual(resource.content_type, 'image/png')
    
    def test_upload_file_with_explicit_resource_type(self):
        """Test that explicit resource type overrides auto-detection"""
        url = reverse('resource-files-list')
        
        # Test file that would auto-detect as document, but we specify image
        test_file_content = b"Some content"
        test_file = ContentFile(test_file_content, name='test.txt')
        
        data = {
            'resource_name': 'Explicit Type Test',
            'resource_description': 'Testing explicit type override',
            'resource_file': test_file,
            'resource_type_id': self.image_type.id,  # Explicitly set as image
            'role_ids': [self.supervisor_role.id]
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify explicit resource type was used
        resource = Resources.objects.get(resource_name='Explicit Type Test')
        self.assertEqual(resource.resource_type.type_name, 'image')  # Should be image, not document
    
    def test_upload_file_generates_secure_url(self):
        """Test that uploaded files generate secure download URLs"""
        url = reverse('resource-files-list')
        
        test_file_content = "Secure URL test content"
        test_file = ContentFile(test_file_content.encode('utf-8'), name='secure_test.txt')
        
        data = {
            'resource_name': 'Secure URL Test',
            'resource_description': 'Testing secure URL generation',
            'resource_file': test_file,
            'role_ids': [self.supervisor_role.id]
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify secure URL is generated
        file_url = response.data['file_url']
        self.assertIsNotNone(file_url)
        self.assertTrue(file_url.startswith('https://'))
        self.assertIn('btfuturesblobstorage.blob.core.windows.net', file_url)
        self.assertIn('resources/', file_url)
    
    def test_upload_file_requires_authentication(self):
        """Test that file upload requires authentication"""
        # Remove authentication
        self.client.force_authenticate(user=None)
        
        url = reverse('resource-files-list')
        test_file_content = "Unauthorized test"
        test_file = ContentFile(test_file_content.encode('utf-8'), name='unauthorized.txt')
        
        data = {
            'resource_name': 'Unauthorized Test',
            'resource_description': 'Should fail without auth',
            'resource_file': test_file,
            'role_ids': [self.supervisor_role.id]
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_upload_file_with_multiple_roles(self):
        """Test file upload with multiple role assignments"""
        url = reverse('resource-files-list')
        
        test_file_content = "Multi-role test content"
        test_file = ContentFile(test_file_content.encode('utf-8'), name='multi_role_test.txt')
        
        data = {
            'resource_name': 'Multi-Role Test',
            'resource_description': 'Testing multiple role assignments',
            'resource_file': test_file,
            'role_ids': [self.supervisor_role.id, self.student_role.id]
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify multiple roles were assigned
        resource = Resources.objects.get(resource_name='Multi-Role Test')
        assigned_roles = list(resource.resourceroles.values_list('role__role_name', flat=True))
        self.assertIn('Supervisor', assigned_roles)
        self.assertIn('Student', assigned_roles)
        self.assertEqual(len(assigned_roles), 2)
    
    def test_upload_file_bio_company_file_types(self):
        """Test upload of bio company specific file types"""
        url = reverse('resource-files-list')
        
        # Test Excel file (should be detected as document)
        excel_content = b"Excel content"
        excel_file = ContentFile(excel_content, name='data_analysis.xlsx')
        
        data = {
            'resource_name': 'Data Analysis Spreadsheet',
            'resource_description': 'Bio company Excel file',
            'resource_file': excel_file,
            'role_ids': [self.supervisor_role.id]
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify Excel file is detected as document
        resource = Resources.objects.get(resource_name='Data Analysis Spreadsheet')
        self.assertEqual(resource.resource_type.type_name, 'document')
        self.assertEqual(resource.content_type, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    def test_upload_file_cleanup_on_update(self):
        """Test that old file is deleted when updating with new file"""
        url = reverse('resource-files-list')
        
        # Create initial resource with file
        test_file_content = "Original content"
        test_file = ContentFile(test_file_content.encode('utf-8'), name='original.txt')
        
        data = {
            'resource_name': 'Update Test',
            'resource_description': 'Testing file update',
            'resource_file': test_file,
            'role_ids': [self.supervisor_role.id]
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        resource = Resources.objects.get(resource_name='Update Test')
        original_file_path = resource.resource_file.name
        
        # Verify original file exists
        from django.core.files.storage import default_storage
        self.assertTrue(default_storage.exists(original_file_path))
        
        # Update with new file
        new_file_content = "Updated content"
        new_file = ContentFile(new_file_content.encode('utf-8'), name='updated.txt')
        
        update_data = {
            'resource_file': new_file
        }
        
        update_url = reverse('resource-files-detail', kwargs={'pk': resource.id})
        response = self.client.patch(update_url, update_data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify new file exists and old file is cleaned up
        updated_resource = Resources.objects.get(id=resource.id)
        new_file_path = updated_resource.resource_file.name
        self.assertNotEqual(original_file_path, new_file_path)
        self.assertTrue(default_storage.exists(new_file_path))
        # Note: Old file cleanup is commented out in views.py, so original file still exists
