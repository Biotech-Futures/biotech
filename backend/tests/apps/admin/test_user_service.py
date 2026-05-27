from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.admin.services.user import (
    query_users, query_user_by_id, query_tracks,
    create_user, update_user, update_status, delete_user,
    has_ungrouped_students,
)
from apps.admin.scope_utils import get_admin_track_ids
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership, Tracks
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import StudentProfile, MentorProfile, User
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

    def test_update_user_always_sets_student_join_permission(self):
        result = update_user(
            self.user.id,
            {
                "firstName": "Chen",
                "lastName": "Supervisor",
                "role": "student",
                "track": "AUS-NSW",
                "schoolName": "Test School",
                "yearLevel": 10,
                "interests": ["Biotechnology"],
                "joinPermissionReceived": False,
            },
        )

        self.assertEqual(result["msg"], "User updated successfully")
        profile = StudentProfile.objects.get(user=self.user)
        self.assertTrue(profile.has_join_permission)
        self.assertTrue(result["data"]["joinPermissionReceived"])

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


class AdminUserServiceCreateUserTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=state)

    def test_create_student_user(self):
        result = create_user({
            "email": "student@example.com",
            "firstName": "Alice",
            "lastName": "Student",
            "role": "student",
            "track": "AUS-NSW",
            "schoolName": "Test High School",
            "yearLevel": 10,
            "interests": ["Biotech"],
        })

        self.assertEqual(result["msg"], "User created successfully")
        self.assertIsNotNone(result["data"])
        self.assertEqual(result["data"]["email"], "student@example.com")
        self.assertEqual(result["data"]["role"], "student")

    def test_create_student_missing_school_returns_error(self):
        result = create_user({
            "email": "student2@example.com",
            "firstName": "Bob",
            "lastName": "Student",
            "role": "student",
            "track": "AUS-NSW",
            "yearLevel": 10,
        })

        self.assertEqual(result["msg"], "School is required for student users")
        self.assertIsNone(result["data"])

    def test_create_mentor_user(self):
        result = create_user({
            "email": "mentor@example.com",
            "firstName": "Mina",
            "lastName": "Mentor",
            "role": "mentor",
            "track": "AUS-NSW",
            "mentorInstitution": "UNSW",
            "mentorReason": "Want to help",
            "mentorMaxGroupCount": 3,
            "interests": ["Education"],
        })

        self.assertEqual(result["msg"], "User created successfully")
        self.assertEqual(result["data"]["role"], "mentor")

    def test_create_duplicate_email_returns_error(self):
        User.objects.create_user(
            email="dup@example.com", first_name="Dup", password="testpass"
        )
        result = create_user({
            "email": "dup@example.com",
            "firstName": "Dup",
            "lastName": "User",
            "role": "student",
            "track": "AUS-NSW",
            "schoolName": "School",
            "yearLevel": 10,
        })

        self.assertEqual(result["msg"], "Email already exists")

    def test_create_admin_global_user(self):
        result = create_user({
            "email": "admin-global@example.com",
            "firstName": "Global",
            "lastName": "Admin",
            "role": "admin",
            "adminIsGlobal": True,
        })

        self.assertEqual(result["msg"], "User created successfully")
        self.assertTrue(result["data"]["adminIsGlobal"])

    def test_create_admin_missing_scope_returns_error(self):
        result = create_user({
            "email": "admin-bad@example.com",
            "firstName": "Bad",
            "lastName": "Admin",
            "role": "admin",
            "adminIsGlobal": False,
            "adminTracks": [],
        })

        self.assertEqual(result["msg"], "Select global admin or at least one admin track for admin users")


class AdminUserServiceStatusTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        track = Tracks.objects.create(track_name="AUS-NSW", state=state)
        self.user = User.objects.create_user(
            email="status@example.com", first_name="Test", last_name="User",
            track=track, password="testpass",
            is_active=True,
        )
        role, _ = Roles.objects.get_or_create(role_name="student")
        RoleAssignmentHistory.objects.create(user=self.user, role=role, valid_from=timezone.now())

    def test_update_status_deactivate(self):
        result = update_status(self.user.id, False)
        self.assertIn("deactivated", result["msg"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_update_status_reactivate(self):
        self.user.is_active = False
        self.user.save()
        result = update_status(self.user.id, True)
        self.assertIn("activated", result["msg"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_update_status_nonexistent_user(self):
        result = update_status(9999, False)
        self.assertEqual(result["msg"], "User not found")
        self.assertIsNone(result["data"])

    def test_delete_user(self):
        uid = self.user.id
        result = delete_user(uid)
        self.assertIn("successfully", result["msg"])
        self.assertFalse(User.objects.filter(id=uid).exists())

    def test_delete_nonexistent_user(self):
        result = delete_user(9999)
        self.assertEqual(result["msg"], "User not found")


class AdminUserServiceQueryTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=state)
        self.admin_user = User.objects.create_user(
            email="admin@example.com", first_name="Admin", password="testpass",
        )
        AdminScope.objects.create(user=self.admin_user, is_global=True)

    def test_query_user_by_id_found(self):
        user = User.objects.create_user(
            email="findme@example.com", first_name="Find", last_name="Me",
            track=self.track, password="testpass",
        )
        result = query_user_by_id(user.id)
        self.assertEqual(result["msg"], "User retrieved successfully")
        self.assertEqual(result["data"]["email"], "findme@example.com")

    def test_query_user_by_id_not_found(self):
        result = query_user_by_id(9999)
        self.assertEqual(result["msg"], "User not found")
        self.assertIsNone(result["data"])

    def test_query_tracks_returns_unarchived(self):
        archived = Tracks.objects.create(track_name="ARCHIVED", state=CountryStates.objects.first())
        archived.is_archived = True
        archived.save()
        result = query_tracks(requesting_user=self.admin_user)
        names = [t["trackName"] for t in result["data"]]
        self.assertIn("AUS-NSW", names)
        self.assertNotIn("ARCHIVED", names)

    def test_has_ungrouped_students_true(self):
        user = User.objects.create_user(
            email="alone@example.com", first_name="Alone", last_name="Student",
            track=self.track, password="testpass",
        )
        StudentProfile.objects.create(user=user, pg_first_name="P", pg_last_name="S", parent_guardian_flag=True, school_name="Test School", year_lvl="10")
        self.assertTrue(has_ungrouped_students())

    def test_has_ungrouped_students_false_when_all_grouped(self):
        user = User.objects.create_user(
            email="grouped@example.com", first_name="Grouped", last_name="Student",
            track=self.track, password="testpass",
        )
        StudentProfile.objects.create(user=user, pg_first_name="P", pg_last_name="S", parent_guardian_flag=True, school_name="Test School", year_lvl="10")
        group = Groups.objects.create(group_name="Test Group", track=self.track)
        GroupMembership.objects.create(user=user, group=group, membership_role="student")
        self.assertFalse(has_ungrouped_students())

    def test_query_users_search_by_email(self):
        User.objects.create_user(
            email="unique-email@example.com", first_name="Unique", last_name="User",
            track=self.track, password="testpass",
        )
        result = query_users(search="unique-email", requesting_user=self.admin_user)
        self.assertEqual(result["data"]["total"], 1)
        self.assertEqual(result["data"]["items"][0]["email"], "unique-email@example.com")
