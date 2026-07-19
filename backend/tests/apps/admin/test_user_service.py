from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.admin.services.user import (
    query_users, query_user_by_id, query_countries, query_states,
    fetch_user_by_id,
    create_user, update_user, update_status, bulk_update_status,
    bulk_update_status_by_filter, delete_user, bulk_delete_users,
    bulk_delete_users_by_filter, has_ungrouped_students, bulk_create_users,
)
from apps.groups.models import (
    Countries, CountryStates, GroupAutoNameUnavailable, Groups, GroupMembership,
)
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import StudentProfile, MentorProfile, User, StudentSupervisor
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

    @patch("apps.admin.views.bulk_create_users")
    def test_rejects_string_body(self, mock_bulk_create_users):
        response = self.client.post(self.url, '"nope"', content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_bulk_create_users.assert_not_called()

    @patch("apps.admin.views.bulk_create_users")
    def test_rejects_empty_array(self, mock_bulk_create_users):
        response = self.client.post(self.url, [], format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_bulk_create_users.assert_not_called()

    @patch("apps.admin.views.bulk_create_users")
    def test_rejects_non_object_row(self, mock_bulk_create_users):
        response = self.client.post(self.url, ["not-an-object"], format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Row 1", response.data["msg"])
        mock_bulk_create_users.assert_not_called()

    @patch("apps.admin.views.bulk_create_users")
    def test_rejects_missing_email(self, mock_bulk_create_users):
        response = self.client.post(self.url, [{"role": "student"}], format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["msg"])
        mock_bulk_create_users.assert_not_called()

    @patch("apps.admin.views.bulk_create_users")
    def test_rejects_invalid_email(self, mock_bulk_create_users):
        response = self.client.post(
            self.url,
            [self.payload[0], {"email": "not-an-email", "role": "student"}],
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Row 2", response.data["msg"])
        self.assertIn("email", response.data["msg"])
        mock_bulk_create_users.assert_not_called()

    @patch("apps.admin.views.bulk_create_users")
    def test_rejects_unknown_role(self, mock_bulk_create_users):
        response = self.client.post(
            self.url,
            [{"email": "teach@example.com", "role": "teacher"}],
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data["msg"])
        mock_bulk_create_users.assert_not_called()

    @patch("apps.admin.views.bulk_create_users")
    def test_rejects_container_group_number(self, mock_bulk_create_users):
        # A list/dict group number is meaningless and would crash the service.
        for bad in (["1"], {"n": 1}):
            with self.subTest(groupNumber=bad):
                response = self.client.post(
                    self.url,
                    [{"email": "ava@example.com", "role": "student", "groupNumber": bad}],
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("groupNumber", response.data["msg"])
        mock_bulk_create_users.assert_not_called()

    @patch("apps.admin.views.bulk_create_users")
    def test_allows_scalar_group_numbers(self, mock_bulk_create_users):
        # A "group number" is naturally numeric; the service str()-coerces it.
        mock_bulk_create_users.return_value = {"msg": "ok", "data": {}}
        for ok in (None, "", "7", 7):
            with self.subTest(groupNumber=ok):
                response = self.client.post(
                    self.url,
                    [{"email": "ava@example.com", "role": "student", "groupNumber": ok}],
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_201_CREATED)


    def test_valid_payload_still_imports(self):
        response = self.client.post(self.url, [_full_student_row()], format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["skipped"], [])
        user = User.objects.get(email="ava.full@example.com")
        profile = StudentProfile.objects.get(user_id=user.id)
        self.assertEqual(profile.school_name, "Sydney High")
        self.assertEqual(profile.year_lvl, "10")
        self.assertEqual(user.country.country_name, "Australia")
        self.assertEqual(user.state.state_name, "NSW")

    @patch("apps.admin.views.bulk_create_users")
    def test_full_key_set_reaches_service_untouched(self, mock_bulk_create_users):
        """Regression guard: the serializer must not drop keys it doesn't declare."""
        mock_bulk_create_users.return_value = {"msg": "ok", "data": {}}
        row = _full_student_row()

        response = self.client.post(self.url, [row], format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sent_rows = mock_bulk_create_users.call_args.args[0]
        self.assertEqual(sent_rows, [row])
        self.assertEqual(set(sent_rows[0]), set(row))


def _full_student_row():
    """Every key add_users_by_role / _apply_co_registration read off a student row."""
    return {
        "email": "ava.full@example.com",
        "firstName": "Ava",
        "lastName": "Nguyen",
        "role": "student",
        "country": "Australia",
        "state": "NSW",
        "schoolName": "Sydney High",
        "yearLevel": "10",
        "interests": ["Biotech"],
        "groupNumber": "7",
        "guardianFirstName": "Gina",
        "guardianLastName": "Nguyen",
        "guardianEmail": "gina@example.com",
        "supervisorFirstName": "Sam",
        "supervisorLastName": "Super",
        "supervisorEmail": "sam@example.com",
        "joinpermResponseId": "R_123",
        "active": True,
    }


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

    def test_create_student_missing_country_returns_error(self):
        result = create_user({
            "email": "student3@example.com",
            "firstName": "Cara",
            "lastName": "Student",
            "role": "student",
            "schoolName": "Test High School",
            "yearLevel": 10,
            "interests": ["Biotech"],
        })

        self.assertEqual(result["msg"], "Country is required")
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
        self.assertEqual(co["groupsCreated"][0]["memberCount"], 2)
        group = Groups.objects.get()
        self.assertEqual(group.group_name, f"BTF_C{group.id:04d}")
        self.assertEqual(group.group_name, co["groupsCreated"][0]["name"])
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

    def test_numeric_group_number_groups_students(self):
        # A JSON int group number must group, not crash _apply_co_registration.
        result = bulk_create_users(
            [self._student("a@example.com", 7), self._student("b@example.com", 7)],
            "",
        )
        co = result["data"]["coRegistration"]
        self.assertEqual(len(co["groupsCreated"]), 1)
        self.assertEqual(co["groupsCreated"][0]["memberCount"], 2)

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
        group = Groups.objects.get()
        self.assertFalse(
            GroupMembership.objects.filter(group=group, membership_role=MENTOR_ROLE).exists()
        )

    def test_co_registered_groups_get_unique_btf_c_names(self):
        result = bulk_create_users(
            [
                self._student("a@example.com", "1"),
                self._student("b@example.com", "1"),
                self._student("c@example.com", "2"),
                self._student("d@example.com", "2"),
            ],
            "",
        )
        names = [g["name"] for g in result["data"]["coRegistration"]["groupsCreated"]]
        self.assertEqual(len(names), 2)
        for group in Groups.objects.all():
            self.assertEqual(group.group_name, f"BTF_C{group.id:04d}")
            self.assertIn(group.group_name, names)
        self.assertEqual(len(set(names)), 2)  # pk-derived, so no two collide

    def test_co_registration_name_collision_degrades_to_a_warning(self):
        # Hand-name a group into the BTF_C slot the co-registered group would claim.
        # The probe row consumes a pk itself, so the next insert lands at probe + 2.
        probe_id = Groups.objects.create(group_name="collision-probe").id
        squatted = f"BTF_C{probe_id + 2:04d}"
        Groups.objects.create(group_name=squatted)

        result = bulk_create_users(
            [self._student("a@example.com", "1"), self._student("b@example.com", "1")],
            "",
        )

        # The import itself still succeeds -- both students were created.
        self.assertEqual(len(result["data"]["created"]), 2)
        co = result["data"]["coRegistration"]
        self.assertEqual(co["groupsCreated"], [])
        self.assertEqual(len(co["warnings"]), 1)
        self.assertIn("left ungrouped", co["warnings"][0])
        self.assertEqual(Groups.objects.count(), 2)  # probe + squatter only
        self.assertFalse(Groups.objects.filter(group_name__startswith="BTF_new-").exists())
        self.assertTrue(has_ungrouped_students())

    def test_one_failed_co_registration_group_does_not_block_the_next(self):
        # Which pk a rolled-back insert frees up is backend-specific (SQLite reuses
        # it, Postgres does not), so drive the failure directly.
        real = Groups.create_auto_named
        calls = []

        def fail_first(marker=""):
            calls.append(marker)
            if len(calls) == 1:
                raise GroupAutoNameUnavailable("BTF_C0001")
            return real(marker=marker)

        with patch.object(Groups, "create_auto_named", side_effect=fail_first):
            result = bulk_create_users(
                [
                    self._student("a@example.com", "1"),
                    self._student("b@example.com", "1"),
                    self._student("c@example.com", "2"),
                    self._student("d@example.com", "2"),
                ],
                "",
            )

        co = result["data"]["coRegistration"]
        self.assertEqual(len(co["groupsCreated"]), 1)
        self.assertEqual(len(co["warnings"]), 1)
        self.assertIn("left ungrouped", co["warnings"][0])
        group = Groups.objects.get()
        self.assertEqual(group.group_name, f"BTF_C{group.id:04d}")
        self.assertEqual(
            GroupMembership.objects.filter(group=group, left_at__isnull=True).count(), 2
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
        group = Groups.objects.get()
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

    def test_force_delete_purges_protecting_records_and_deletes_user(self):
        from datetime import timedelta
        from apps.chat.models import Messages
        from apps.resources.models import Resources
        from apps.workshops.models import Workshops
        from apps.admin.models import MatchRun

        group = Groups.objects.create(group_name="Force G")
        Messages.objects.create(sender_user=self.a, group=group, message_text="hi")
        Resources.objects.create(name="R", description="d", uploaded_by=self.a)
        Workshops.objects.create(
            workshop_name="W", start_datetime=timezone.now(),
            duration=timedelta(hours=1), location="Zoom",
            host_user=self.a, group=group,
        )
        MatchRun.objects.create(admin_user=self.a, run_type="auto", payload={}, result={})

        result = delete_user(self.a.id, force=True)

        self.assertEqual(result["msg"], "User deleted successfully")
        self.assertFalse(User.objects.filter(id=self.a.id).exists())
        self.assertFalse(Messages.objects.filter(sender_user_id=self.a.id).exists())
        self.assertFalse(Resources.objects.filter(uploaded_by_id=self.a.id).exists())
        self.assertFalse(Workshops.objects.filter(host_user_id=self.a.id).exists())
        self.assertFalse(MatchRun.objects.filter(admin_user_id=self.a.id).exists())

    def test_bulk_delete_force_deletes_protected_users(self):
        from apps.chat.models import Messages
        group = Groups.objects.create(group_name="Force G2")
        Messages.objects.create(sender_user=self.a, group=group, message_text="hi")
        result = bulk_delete_users([self.a.id, self.b.id], force=True)
        self.assertCountEqual(result["data"]["deletedIds"], [self.a.id, self.b.id])
        self.assertEqual(result["data"]["failedIds"], [])
        self.assertFalse(User.objects.filter(id__in=[self.a.id, self.b.id]).exists())

    def test_force_delete_by_filter_still_protects_admins(self):
        # force purges PROTECT blockers but must NOT override the admin-protection guard.
        from apps.chat.models import Messages
        AdminScope.objects.create(user=self.admin)
        group = Groups.objects.create(group_name="Force G3")
        Messages.objects.create(sender_user=self.admin, group=group, message_text="hi")
        result = bulk_delete_users_by_filter({"search": "example.com"}, force=True)
        self.assertCountEqual(result["data"]["deletedIds"], [self.a.id, self.b.id])
        self.assertEqual(result["data"]["skippedAdmins"], 1)
        self.assertTrue(User.objects.filter(id=self.admin.id).exists())


class SupervisorFromStudentImportTests(TestCase):
    """Supervisors created as a side effect of a student row must look like every
    other imported user: active, and in the student's state."""

    def setUp(self):
        # Fixture-only country/state so the assertions can't collide with real rows.
        self.country, _ = Countries.objects.get_or_create(country_name="Zedonia")
        self.state = CountryStates.objects.create(
            country=self.country, state_name="Zednsw"
        )
        for name in ["student", "supervisor"]:
            Roles.objects.get_or_create(role_name=name)

    def _import_student(self, **overrides):
        payload = {
            "email": "zed-kid@example.com",
            "firstName": "Kid",
            "lastName": "Student",
            "role": "student",
            "state": "Zednsw",
            "country": "Zedonia",
            "schoolName": "Test High",
            "yearLevel": 10,
            "interests": ["Biotechnology"],
            "supervisorEmail": "zed-sup@example.com",
            "supervisorFirstName": "Sam",
            "supervisorLastName": "Super",
        }
        payload.update(overrides)
        return bulk_create_users([payload], admin_user_id=None)

    def test_created_supervisor_is_active(self):
        self._import_student()
        sup = User.objects.get(email="zed-sup@example.com")
        self.assertTrue(sup.is_active)
        self.assertEqual(sup.account_status, User.AccountStatus.ACTIVE)

    def test_created_supervisor_inherits_student_state(self):
        self._import_student()
        sup = User.objects.get(email="zed-sup@example.com")
        self.assertEqual(sup.state_id, self.state.id)
        self.assertEqual(sup.country_id, self.country.id)

    def test_created_supervisor_inherits_country_without_a_state(self):
        self._import_student(state="")
        sup = User.objects.get(email="zed-sup@example.com")
        self.assertEqual(sup.country_id, self.country.id)
        self.assertIsNone(sup.state_id)

    def test_created_supervisor_is_mapped_to_student(self):
        self._import_student()
        sup = User.objects.get(email="zed-sup@example.com")
        student = User.objects.get(email="zed-kid@example.com")
        profile = StudentProfile.objects.get(user_id=student.id)
        self.assertEqual(profile.supervisor_id, sup.id)
        self.assertTrue(
            StudentSupervisor.objects.filter(
                student_user_id=student.id, supervisor_user_id=sup.id
            ).exists()
        )

    def test_existing_supervisor_is_not_reactivated_or_moved(self):
        other_state = CountryStates.objects.create(
            country=self.country, state_name="Zedvic"
        )
        existing = User.objects.create_user(
            email="zed-sup@example.com", first_name="Sam", last_name="Super",
            password=None, state_id=other_state.id, is_active=False,
            account_status=User.AccountStatus.DEACTIVATED,
        )
        self._import_student()
        existing.refresh_from_db()
        self.assertFalse(existing.is_active)
        self.assertEqual(existing.state_id, other_state.id)

    def test_stateless_existing_supervisor_gets_backfilled(self):
        existing = User.objects.create_user(
            email="zed-sup@example.com", first_name="Sam", last_name="Super",
            password=None,
        )
        self.assertIsNone(existing.state_id)
        self._import_student()
        existing.refresh_from_db()
        self.assertEqual(existing.state_id, self.state.id)


class UserCountryFilterTests(TestCase):
    """Country filter must disambiguate states that share a name across countries."""

    def setUp(self):
        # Two fixture countries sharing a state name — the exact ambiguity the
        # country filter exists to resolve. Names are fixture-only so real rows
        # in the dev DB can't satisfy these filters.
        zed, _ = Countries.objects.get_or_create(country_name="Zedonia")
        yar, _ = Countries.objects.get_or_create(country_name="Yartonia")
        self.zed_vic = CountryStates.objects.create(country=zed, state_name="Sharedvic")
        self.yar_vic = CountryStates.objects.create(country=yar, state_name="Sharedvic")
        self.zed_user = User.objects.create_user(
            email="zed-user@example.com", first_name="Z", last_name="User",
            password="x", country_id=zed.id, state_id=self.zed_vic.id,
        )
        self.yar_user = User.objects.create_user(
            email="yar-user@example.com", first_name="Y", last_name="User",
            password="x", country_id=yar.id, state_id=self.yar_vic.id,
        )

    def test_country_filter_narrows_same_named_state(self):
        result = query_users(country="Zedonia", state="Sharedvic")
        emails = [u["email"] for u in result["data"]["items"]]
        self.assertEqual(emails, ["zed-user@example.com"])

    def test_state_without_country_still_matches_both(self):
        result = query_users(state="Sharedvic")
        emails = sorted(u["email"] for u in result["data"]["items"])
        self.assertEqual(emails, ["yar-user@example.com", "zed-user@example.com"])

    def test_country_filter_alone(self):
        result = query_users(country="Yartonia")
        emails = [u["email"] for u in result["data"]["items"]]
        self.assertEqual(emails, ["yar-user@example.com"])


class InternationalGeographyImportTests(TestCase):
    """An international registrant gets a country and no state — the country must
    never be stored as a state (which is how mentors showed 'STATE: UAE')."""

    def setUp(self):
        for name in ["student", "mentor"]:
            Roles.objects.get_or_create(role_name=name)

    def _import_mentor(self, **overrides):
        payload = {
            "email": "zed-mentor@example.com",
            "firstName": "Intl",
            "lastName": "Mentor",
            "role": "mentor",
            "country": "Zedonia",
            "interests": ["Biotechnology"],
            "mentorInstitution": "Zed University",
            "mentorReason": "Testing",
            "mentorMaxGroupCount": 2,
        }
        payload.update(overrides)
        return bulk_create_users([payload], admin_user_id=None)

    def test_country_only_import_leaves_state_blank(self):
        self._import_mentor()
        user = User.objects.get(email="zed-mentor@example.com")
        self.assertEqual(user.country.country_name, "Zedonia")
        self.assertIsNone(user.state_id)

    def test_country_is_never_stored_as_a_state(self):
        # The old bug: state fell back to the country name, creating a
        # CountryStates row named after its own country.
        self._import_mentor(state="Zedonia")
        user = User.objects.get(email="zed-mentor@example.com")
        self.assertEqual(user.country.country_name, "Zedonia")
        self.assertIsNone(user.state_id)
        self.assertFalse(
            CountryStates.objects.filter(state_name="Zedonia").exists()
        )

    def test_region_is_kept_as_a_state_under_its_country(self):
        self._import_mentor(state="Zednorth")
        user = User.objects.get(email="zed-mentor@example.com")
        self.assertEqual(user.country.country_name, "Zedonia")
        self.assertEqual(user.state.state_name, "Zednorth")
        self.assertEqual(user.state.country_id, user.country_id)

    def test_serialized_user_exposes_country_separately_from_state(self):
        self._import_mentor()
        user = User.objects.get(email="zed-mentor@example.com")
        data = fetch_user_by_id(user.id)
        self.assertEqual(data["country"], {"id": user.country_id, "countryName": "Zedonia"})
        self.assertIsNone(data["state"])
