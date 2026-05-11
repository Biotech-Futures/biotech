from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.admin.services.user import query_users, update_user
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership, Tracks
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import StudentProfile, User
from apps.users.models.admin_scope import AdminScope


class AdminUserServiceTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=state)
        self.user = User.objects.create_user(
            email="supervisor@example.com",
            first_name="Chen",
            last_name="Supervisor",
            password="testpass",
        )
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            first_name="Ada",
            last_name="Admin",
            password="testpass",
        )
        AdminScope.objects.create(user=self.admin_user, is_global=True)

    def test_update_user_assigns_incoming_role_when_current_role_is_missing(self):
        result = update_user(
            self.user.id,
            {
                "firstName": "Chen",
                "lastName": "Supervisor",
                "role": "admin",
                "track": None,
                "adminTracks": ["AUS-NSW"],
                "interests": [],
                "joinPermissionReceived": False,
            },
        )

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertEqual(result["data"]["role"], "admin")
        self.assertEqual(result["data"]["adminTracks"], ["AUS-NSW"])
        self.assertTrue(
            RoleAssignmentHistory.objects.filter(
                user=self.user,
                role__role_name="admin",
                valid_to__isnull=True,
            ).exists()
        )
        self.assertTrue(
            AdminScope.objects.filter(user=self.user, track=self.track).exists()
        )

    def test_update_user_can_assign_global_admin_scope(self):
        result = update_user(
            self.user.id,
            {
                "firstName": "Chen",
                "lastName": "Supervisor",
                "role": "admin",
                "track": None,
                "adminIsGlobal": True,
                "adminTracks": [],
                "interests": [],
                "joinPermissionReceived": False,
            },
        )

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertTrue(result["data"]["adminIsGlobal"])
        self.assertEqual(result["data"]["adminTracks"], ["AUS-NSW"])
        self.assertTrue(
            AdminScope.objects.filter(
                user=self.user,
                is_global=True,
                track__isnull=True,
            ).exists()
        )

    def test_query_users_filters_students_with_active_group(self):
        grouped_student = self._create_student("grouped@example.com", "Grouped")
        ungrouped_student = self._create_student("ungrouped@example.com", "Ungrouped")
        left_student = self._create_student("left@example.com", "Left")
        deleted_group_student = self._create_student("deleted@example.com", "Deleted")
        now = timezone.now()
        group = Groups.objects.create(group_name="Active Group", track=self.track)
        deleted_group = Groups.objects.create(
            group_name="Deleted Group",
            track=self.track,
            created_at=now,
            deleted_at=now,
        )
        GroupMembership.objects.create(
            user=grouped_student,
            group=group,
            membership_role="student",
        )
        GroupMembership.objects.create(
            user=left_student,
            group=group,
            membership_role="student",
            joined_at=now,
            left_at=now,
        )
        GroupMembership.objects.create(
            user=deleted_group_student,
            group=deleted_group,
            membership_role="student",
        )

        result = query_users(
            role="student",
            in_group="yes",
            requesting_user=self.admin_user,
        )

        self.assertEqual(result["data"]["total"], 1)
        self.assertEqual(
            [item["email"] for item in result["data"]["items"]],
            [grouped_student.email],
        )
        self.assertEqual(result["data"]["items"][0]["groupName"], group.group_name)

        no_group_result = query_users(
            role="student",
            in_group="no",
            requesting_user=self.admin_user,
        )

        self.assertEqual(no_group_result["data"]["total"], 3)
        self.assertCountEqual(
            [item["email"] for item in no_group_result["data"]["items"]],
            [
                ungrouped_student.email,
                left_student.email,
                deleted_group_student.email,
            ],
        )

    def _create_student(self, email, last_name):
        user = User.objects.create_user(
            email=email,
            first_name="Student",
            last_name=last_name,
            password="testpass",
            track=self.track,
        )
        role, _ = Roles.objects.get_or_create(role_name="student")
        RoleAssignmentHistory.objects.create(
            user=user,
            role=role,
            valid_from=timezone.now(),
        )
        StudentProfile.objects.create(
            user=user,
            pg_first_name="Parent",
            pg_last_name=last_name,
            parent_guardian_flag=True,
            school_name="Test School",
            year_lvl="10",
            has_join_permission=True,
        )
        return user


class AdminUserBulkCreateViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="bulk-admin@example.com",
            first_name="Bulk",
            last_name="Admin",
            password="testpass",
        )
        AdminScope.objects.create(user=self.admin_user, is_global=True)
        self.client.force_authenticate(user=self.admin_user)
        self.url = "/api/v1/admin/user/bulk/"
        self.payload = [
            {
                "firstName": "Ava",
                "lastName": "Nguyen",
                "email": "ava.nguyen@example.com",
                "role": "student",
            }
        ]

    @patch("apps.admin.views.bulk_create_users")
    def test_accepts_json_array_payload(self, mock_bulk_create_users):
        mock_bulk_create_users.return_value = {
            "msg": "Bulk import complete: 1 created, 0 skipped",
            "data": {"created": [], "skipped": []},
        }

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_bulk_create_users.assert_called_once_with(self.payload, "")

    @patch("apps.admin.views.bulk_create_users")
    def test_accepts_wrapped_users_payload_for_compatibility(self, mock_bulk_create_users):
        mock_bulk_create_users.return_value = {
            "msg": "Bulk import complete: 1 created, 0 skipped",
            "data": {"created": [], "skipped": []},
        }

        response = self.client.post(
            self.url,
            {"users": self.payload},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_bulk_create_users.assert_called_once_with(self.payload, "")

    @patch("apps.admin.views.bulk_create_users")
    def test_rejects_non_array_payload(self, mock_bulk_create_users):
        response = self.client.post(self.url, {"email": "bad@example.com"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["msg"], "Expected a JSON array of users")
        mock_bulk_create_users.assert_not_called()
