from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.admin.services.user import (
    query_users, query_user_by_id, query_states,
    create_user, update_user, update_status, bulk_update_status,
    bulk_update_status_by_filter, delete_user, bulk_delete_users,
    bulk_delete_users_by_filter, has_ungrouped_students, bulk_create_users,
)
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import StudentProfile, MentorProfile, User
from apps.users.models.admin_scope import AdminScope


class AdminUserServiceTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=country, state_name="NSW")
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
        AdminScope.objects.create(user=self.admin_user)

    def test_update_user_assigns_incoming_role_when_current_role_is_missing(self):
        result = update_user(
            self.user.id,
            {
                "firstName": "Chen",
                "lastName": "Supervisor",
                "role": "admin",
                "interests": [],
                "joinPermissionReceived": False,
            },
        )

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertEqual(result["data"]["role"], "admin")
        self.assertTrue(result["data"]["isAdmin"])
        self.assertTrue(
            RoleAssignmentHistory.objects.filter(
                user=self.user,
                role__role_name="admin",
                valid_to__isnull=True,
            ).exists()
        )
        self.assertTrue(
            AdminScope.objects.filter(user=self.user).exists()
        )

    def test_update_user_to_admin_creates_single_admin_scope(self):
        result = update_user(
            self.user.id,
            {
                "firstName": "Chen",
                "lastName": "Supervisor",
                "role": "admin",
                "interests": [],
                "joinPermissionReceived": False,
            },
        )

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertTrue(result["data"]["isAdmin"])
        self.assertEqual(
            AdminScope.objects.filter(user=self.user).count(), 1
        )

    def test_update_user_demoting_admin_clears_admin_scope(self):
        AdminScope.objects.create(user=self.user)
        result = update_user(
            self.user.id,
            {
                "firstName": "Chen",
                "lastName": "Supervisor",
                "role": "student",
                "schoolName": "Test School",
                "yearLevel": 10,
                "interests": ["Biotechnology"],
                "joinPermissionReceived": False,
            },
        )

        self.assertEqual(result["msg"], "User updated successfully")
        self.assertFalse(result["data"]["isAdmin"])
        self.assertFalse(AdminScope.objects.filter(user=self.user).exists())

    def test_update_user_always_sets_student_join_permission(self):
        result = update_user(
            self.user.id,
            {
                "firstName": "Chen",
                "lastName": "Supervisor",
                "role": "student",
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
        group = Groups.objects.create(group_name="Active Group")
        deleted_group = Groups.objects.create(
            group_name="Deleted Group",
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
            state=self.state,
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
        AdminScope.objects.create(user=self.admin_user)
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
        self.state = CountryStates.objects.create(country=country, state_name="NSW")

    def test_create_student_user(self):
        result = create_user({
            "email": "student@example.com",
            "firstName": "Alice",
            "lastName": "Student",
            "role": "student",
            "state": "NSW",
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
            "state": "NSW",
            "yearLevel": 10,
        })

        self.assertEqual(result["msg"], "School is required for student users")
        self.assertIsNone(result["data"])

    def test_create_student_missing_state_returns_error(self):
        result = create_user({
            "email": "student3@example.com",
            "firstName": "Cara",
            "lastName": "Student",
            "role": "student",
            "schoolName": "Test High School",
            "yearLevel": 10,
            "interests": ["Biotech"],
        })

        self.assertEqual(result["msg"], "State is required")
        self.assertIsNone(result["data"])

    def test_create_mentor_user(self):
        result = create_user({
            "email": "mentor@example.com",
            "firstName": "Mina",
            "lastName": "Mentor",
            "role": "mentor",
            "state": "NSW",
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
            "state": "NSW",
            "schoolName": "School",
            "yearLevel": 10,
        })

        self.assertEqual(result["msg"], "Email already exists")

    def test_create_admin_user(self):
        result = create_user({
            "email": "admin-global@example.com",
            "firstName": "Global",
            "lastName": "Admin",
            "role": "admin",
        })

        self.assertEqual(result["msg"], "User created successfully")
        self.assertTrue(result["data"]["isAdmin"])
        self.assertTrue(
            AdminScope.objects.filter(user_id=result["data"]["id"]).exists()
        )


class AdminUserServiceStatusTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.user = User.objects.create_user(
            email="status@example.com", first_name="Test", last_name="User",
            state=state, password="testpass",
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


class AdminUserServiceBulkStatusTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.users = [
            User.objects.create_user(
                email=f"bulk{i}@example.com", first_name=f"Bulk{i}", last_name="User",
                state=state, password="testpass", is_active=True,
            )
            for i in range(3)
        ]
        self.admin_user = User.objects.create_user(
            email="bulkadmin@example.com", first_name="Ada", last_name="Admin",
            password="testpass",
        )
        AdminScope.objects.create(user=self.admin_user)

    def test_bulk_deactivate_updates_all(self):
        ids = [u.id for u in self.users]
        result = bulk_update_status(ids, False, initiated_by=self.admin_user)

        self.assertEqual(sorted(result["data"]["updatedIds"]), sorted(ids))
        self.assertIn("3 user(s) deactivated", result["msg"])
        for user in self.users:
            user.refresh_from_db()
            self.assertFalse(user.is_active)
            self.assertEqual(user.account_status, "deactivated")

    def test_bulk_activate_reports_unchanged(self):
        self.users[0].is_active = False
        self.users[0].account_status = "deactivated"
        self.users[0].save()
        ids = [u.id for u in self.users]

        result = bulk_update_status(ids, True, initiated_by=self.admin_user)

        self.assertEqual(result["data"]["updatedIds"], [self.users[0].id])
        self.assertEqual(
            sorted(result["data"]["unchangedIds"]),
            sorted([self.users[1].id, self.users[2].id]),
        )
        self.users[0].refresh_from_db()
        self.assertTrue(self.users[0].is_active)

    def test_bulk_deactivate_skips_initiator(self):
        ids = [self.users[0].id, self.admin_user.id]
        result = bulk_update_status(ids, False, initiated_by=self.admin_user)

        self.assertTrue(result["data"]["skippedSelf"])
        self.assertEqual(result["data"]["updatedIds"], [self.users[0].id])
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)

    def test_bulk_status_reports_missing_ids(self):
        result = bulk_update_status([self.users[0].id, 99999], False)

        self.assertEqual(result["data"]["updatedIds"], [self.users[0].id])
        self.assertEqual(result["data"]["notFoundIds"], [99999])
        self.assertIn("1 not found", result["msg"])

    def test_bulk_status_rejects_empty_list(self):
        result = bulk_update_status([], False)
        self.assertIsNone(result["data"])

    def test_bulk_status_rejects_non_integer_ids(self):
        result = bulk_update_status(["abc"], False)
        self.assertIsNone(result["data"])

    def test_bulk_status_endpoint(self):
        client = APIClient()
        client.force_authenticate(user=self.admin_user)
        ids = [u.id for u in self.users]

        response = client.patch(
            "/api/v1/admin/user/bulk-status/",
            {"userIds": ids, "isActive": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(sorted(response.data["data"]["updatedIds"]), sorted(ids))

    def test_bulk_status_endpoint_requires_user_ids(self):
        client = APIClient()
        client.force_authenticate(user=self.admin_user)

        response = client.patch(
            "/api/v1/admin/user/bulk-status/",
            {"isActive": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_by_filter_updates_all_matching(self):
        # The 3 bulk users are in NSW; the admin has no state and is excluded.
        result = bulk_update_status_by_filter(
            {"state": "NSW"}, False, initiated_by=self.admin_user
        )

        ids = [u.id for u in self.users]
        self.assertEqual(sorted(result["data"]["updatedIds"]), sorted(ids))
        for user in self.users:
            user.refresh_from_db()
            self.assertFalse(user.is_active)

    def test_bulk_by_filter_respects_exclusions(self):
        excluded = self.users[0].id
        result = bulk_update_status_by_filter(
            {"state": "NSW"}, False, exclude_ids=[excluded],
            initiated_by=self.admin_user,
        )

        self.assertNotIn(excluded, result["data"]["updatedIds"])
        self.assertEqual(len(result["data"]["updatedIds"]), 2)
        self.users[0].refresh_from_db()
        self.assertTrue(self.users[0].is_active)

    def test_bulk_by_filter_no_matches_returns_empty(self):
        result = bulk_update_status_by_filter(
            {"state": "VIC"}, False, initiated_by=self.admin_user
        )

        self.assertEqual(result["data"]["updatedIds"], [])

    def test_bulk_status_endpoint_select_all(self):
        client = APIClient()
        client.force_authenticate(user=self.admin_user)

        response = client.patch(
            "/api/v1/admin/user/bulk-status/",
            {"selectAll": True, "isActive": False, "filters": {"state": "NSW"}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [u.id for u in self.users]
        self.assertEqual(sorted(response.data["data"]["updatedIds"]), sorted(ids))

    def test_bulk_status_endpoint_select_all_requires_is_active(self):
        client = APIClient()
        client.force_authenticate(user=self.admin_user)

        response = client.patch(
            "/api/v1/admin/user/bulk-status/",
            {"selectAll": True, "filters": {"state": "NSW"}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AdminUserServiceQueryTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=country, state_name="NSW")
        self.admin_user = User.objects.create_user(
            email="admin@example.com", first_name="Admin", password="testpass",
        )
        AdminScope.objects.create(user=self.admin_user)

    def test_query_user_by_id_found(self):
        user = User.objects.create_user(
            email="findme@example.com", first_name="Find", last_name="Me",
            state=self.state, password="testpass",
        )
        result = query_user_by_id(user.id)
        self.assertEqual(result["msg"], "User retrieved successfully")
        self.assertEqual(result["data"]["email"], "findme@example.com")

    def test_query_user_by_id_not_found(self):
        result = query_user_by_id(9999)
        self.assertEqual(result["msg"], "User not found")
        self.assertIsNone(result["data"])

    def test_query_states_returns_states(self):
        vic = CountryStates.objects.create(
            country=self.state.country, state_name="VIC"
        )
        result = query_states(requesting_user=self.admin_user)
        names = [s["stateName"] for s in result["data"]]
        self.assertIn("NSW", names)
        self.assertIn("VIC", names)
        nsw = next(s for s in result["data"] if s["stateName"] == "NSW")
        self.assertEqual(nsw["countryName"], "Australia")

    def test_has_ungrouped_students_true(self):
        user = User.objects.create_user(
            email="alone@example.com", first_name="Alone", last_name="Student",
            state=self.state, password="testpass",
        )
        StudentProfile.objects.create(user=user, pg_first_name="P", pg_last_name="S", parent_guardian_flag=True, school_name="Test School", year_lvl="10")
        self.assertTrue(has_ungrouped_students())

    def test_has_ungrouped_students_false_when_all_grouped(self):
        user = User.objects.create_user(
            email="grouped@example.com", first_name="Grouped", last_name="Student",
            state=self.state, password="testpass",
        )
        StudentProfile.objects.create(user=user, pg_first_name="P", pg_last_name="S", parent_guardian_flag=True, school_name="Test School", year_lvl="10")
        group = Groups.objects.create(group_name="Test Group")
        GroupMembership.objects.create(user=user, group=group, membership_role="student")
        self.assertFalse(has_ungrouped_students())

    def test_query_users_search_by_email(self):
        User.objects.create_user(
            email="unique-email@example.com", first_name="Unique", last_name="User",
            state=self.state, password="testpass",
        )
        result = query_users(search="unique-email", requesting_user=self.admin_user)
        self.assertEqual(result["data"]["total"], 1)
        self.assertEqual(result["data"]["items"][0]["email"], "unique-email@example.com")


STUDENT_ROLE = GroupMembership.MembershipRoleChoices.STUDENT
SUPERVISOR_ROLE = GroupMembership.MembershipRoleChoices.SUPERVISOR
MENTOR_ROLE = GroupMembership.MembershipRoleChoices.MENTOR


class AdminUserServiceCoRegistrationTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=country, state_name="NSW")

    def _student(self, email, group_number=None, **overrides):
        row = {
            "email": email,
            "firstName": "Test",
            "lastName": email.split("@")[0],
            "role": "student",
            "state": "NSW",
            "schoolName": "Test High School",
            "yearLevel": 10,
            "interests": ["Biotech"],
        }
        if group_number is not None:
            row["groupNumber"] = group_number
        row.update(overrides)
        return row

    def _mentor(self, email, group_number=None):
        row = {
            "email": email,
            "firstName": "Mentor",
            "lastName": email.split("@")[0],
            "role": "mentor",
            "state": "NSW",
            "mentorInstitution": "UNSW",
            "mentorReason": "Want to help",
            "mentorMaxGroupCount": 3,
            "interests": ["Biotech"],
        }
        if group_number is not None:
            row["groupNumber"] = group_number
        return row

    def test_students_sharing_group_number_are_grouped(self):
        result = bulk_create_users(
            [self._student("a@example.com", "1"), self._student("b@example.com", "1")],
            "",
        )
        co = result["data"]["coRegistration"]
        self.assertEqual(len(co["groupsCreated"]), 1)
        self.assertEqual(co["groupsCreated"][0]["name"], "Co-registered Group 1")
        self.assertEqual(co["groupsCreated"][0]["memberCount"], 2)
        group = Groups.objects.get(group_name="Co-registered Group 1")
        self.assertEqual(
            GroupMembership.objects.filter(
                group=group, membership_role=STUDENT_ROLE, left_at__isnull=True
            ).count(),
            2,
        )

    def test_co_registered_students_leave_the_matching_pool(self):
        self.assertFalse(has_ungrouped_students())
        bulk_create_users(
            [self._student("a@example.com", "1"), self._student("b@example.com", "1")],
            "",
        )
        # Both now have an active membership, so the auto-matcher's pool excludes them.
        self.assertFalse(has_ungrouped_students())

    def test_blank_group_number_leaves_student_ungrouped(self):
        result = bulk_create_users([self._student("solo@example.com")], "")
        self.assertNotIn("coRegistration", result["data"])
        self.assertFalse(Groups.objects.exists())
        self.assertTrue(has_ungrouped_students())

    def test_lone_group_number_creates_no_group(self):
        result = bulk_create_users([self._student("solo@example.com", "9")], "")
        self.assertNotIn("coRegistration", result["data"])
        self.assertFalse(Groups.objects.exists())
        self.assertTrue(has_ungrouped_students())

    def test_oversized_group_kept_together_with_warning(self):
        rows = [self._student(f"s{i}@example.com", "3") for i in range(6)]
        result = bulk_create_users(rows, "")
        co = result["data"]["coRegistration"]
        self.assertEqual(len(co["groupsCreated"]), 1)
        self.assertEqual(co["groupsCreated"][0]["memberCount"], 6)
        self.assertEqual(len(co["warnings"]), 1)
        self.assertIn("6 members", co["warnings"][0])

    def test_group_number_ignored_for_non_student_rows(self):
        # The mentor shares group "1" but must not be counted as a co-registered member.
        result = bulk_create_users(
            [
                self._mentor("m@example.com", "1"),
                self._student("a@example.com", "1"),
                self._student("b@example.com", "1"),
            ],
            "",
        )
        self.assertEqual(result["data"]["coRegistration"]["groupsCreated"][0]["memberCount"], 2)
        group = Groups.objects.get(group_name="Co-registered Group 1")
        self.assertFalse(
            GroupMembership.objects.filter(group=group, membership_role=MENTOR_ROLE).exists()
        )

    def test_group_name_collision_gets_unique_suffix(self):
        Groups.objects.create(group_name="Co-registered Group 1")
        result = bulk_create_users(
            [self._student("a@example.com", "1"), self._student("b@example.com", "1")],
            "",
        )
        self.assertEqual(
            result["data"]["coRegistration"]["groupsCreated"][0]["name"],
            "Co-registered Group 1 (2)",
        )

    def test_supervisor_synced_into_co_registration_group(self):
        result = bulk_create_users(
            [
                {
                    "email": "sup@example.com",
                    "firstName": "Sam",
                    "lastName": "Supervisor",
                    "role": "supervisor",
                    "state": "NSW",
                    "supervisorSchoolName": "Test High School",
                },
                self._student("a@example.com", "1", supervisorEmail="sup@example.com"),
                self._student("b@example.com", "1", supervisorEmail="sup@example.com"),
            ],
            "",
        )
        group = Groups.objects.get(group_name="Co-registered Group 1")
        sup_user = User.objects.get(email="sup@example.com")
        self.assertTrue(
            GroupMembership.objects.filter(
                group=group,
                user=sup_user,
                membership_role=SUPERVISOR_ROLE,
                left_at__isnull=True,
            ).exists()
        )


class AdminUserServiceBulkDeleteTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user(email="a@example.com", first_name="A", password="x")
        self.b = User.objects.create_user(email="b@example.com", first_name="B", password="x")
        self.admin = User.objects.create_user(email="admin@example.com", first_name="Ad", password="x")

    def test_bulk_delete_removes_users(self):
        result = bulk_delete_users([self.a.id, self.b.id])
        self.assertCountEqual(result["data"]["deletedIds"], [self.a.id, self.b.id])
        self.assertFalse(User.objects.filter(id__in=[self.a.id, self.b.id]).exists())

    def test_bulk_delete_skips_own_account(self):
        result = bulk_delete_users([self.a.id, self.admin.id], initiated_by=self.admin)
        self.assertTrue(result["data"]["skippedSelf"])
        self.assertEqual(result["data"]["deletedIds"], [self.a.id])
        self.assertTrue(User.objects.filter(id=self.admin.id).exists())

    def test_bulk_delete_reports_not_found(self):
        result = bulk_delete_users([self.a.id, 999999])
        self.assertEqual(result["data"]["deletedIds"], [self.a.id])
        self.assertEqual(result["data"]["notFoundIds"], [999999])

    def test_bulk_delete_rejects_empty(self):
        result = bulk_delete_users([])
        self.assertIsNone(result["data"])

    def test_bulk_delete_by_filter_deletes_all_matching(self):
        result = bulk_delete_users_by_filter({"search": "example.com"})
        self.assertCountEqual(
            result["data"]["deletedIds"], [self.a.id, self.b.id, self.admin.id]
        )
        self.assertEqual(User.objects.count(), 0)

    def test_bulk_delete_by_filter_excludes_and_skips_self(self):
        result = bulk_delete_users_by_filter(
            {"search": "example.com"},
            exclude_ids=[self.b.id],
            initiated_by=self.admin,
        )
        self.assertEqual(result["data"]["deletedIds"], [self.a.id])
        self.assertTrue(result["data"]["skippedSelf"])
        self.assertTrue(User.objects.filter(id=self.b.id).exists())  # excluded
        self.assertTrue(User.objects.filter(id=self.admin.id).exists())  # self

    def test_bulk_delete_by_filter_empty_match(self):
        result = bulk_delete_users_by_filter({"search": "no-such-user-zzz"})
        self.assertEqual(result["data"]["deletedIds"], [])
        self.assertEqual(User.objects.count(), 3)

    def test_delete_user_referenced_by_protected_record_is_not_deleted(self):
        from apps.chat.models.messages import Messages
        group = Groups.objects.create(group_name="Protect G")
        Messages.objects.create(sender_user=self.a, group=group, message_text="hi")
        result = delete_user(self.a.id)
        self.assertIsNone(result["data"])
        self.assertIn("cannot be deleted", result["msg"])
        self.assertTrue(User.objects.filter(id=self.a.id).exists())

    def test_bulk_delete_reports_protected_as_failed(self):
        from apps.chat.models.messages import Messages
        group = Groups.objects.create(group_name="Protect G2")
        Messages.objects.create(sender_user=self.a, group=group, message_text="hi")
        result = bulk_delete_users([self.a.id, self.b.id])
        self.assertEqual(result["data"]["deletedIds"], [self.b.id])
        self.assertEqual(result["data"]["failedIds"], [self.a.id])
        self.assertTrue(User.objects.filter(id=self.a.id).exists())
        self.assertFalse(User.objects.filter(id=self.b.id).exists())

    def test_bulk_delete_by_filter_protects_admins(self):
        AdminScope.objects.create(user=self.admin)
        result = bulk_delete_users_by_filter({"search": "example.com"})
        self.assertCountEqual(result["data"]["deletedIds"], [self.a.id, self.b.id])
        self.assertEqual(result["data"]["skippedAdmins"], 1)
        self.assertTrue(User.objects.filter(id=self.admin.id).exists())

    def test_bulk_delete_by_filter_refuses_when_set_grew(self):
        # Admin reviewed fewer than now match -> refuse rather than sweep in extras.
        result = bulk_delete_users_by_filter({"search": "example.com"}, expected_count=2)
        self.assertIsNone(result["data"])
        self.assertEqual(User.objects.count(), 3)
