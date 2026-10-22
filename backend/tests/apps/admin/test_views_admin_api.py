from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin.models import AdminView
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import MentorProfile, StudentProfile, SupervisorProfile, User
from apps.users.models.admin_scope import AdminScope


class AdminViewApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Admin user for auth
        self.admin = User.objects.create_user(
            email="admin@example.com",
            first_name="Ada",
            last_name="Admin",
            password="testpass",
        )
        AdminScope.objects.create(user=self.admin)
        self.client.force_authenticate(user=self.admin)

        for item in [
            {
                'name': 'All Users',
                'description': 'Complete directory of all registered accounts',
                'is_default': True,
                'target_roles': ['all'],
                'account_status': 'all',
                'engagement_status': 'all',
                'advanced_conditions': [],
                'visible_columns': ['name', 'email', 'role', 'school', 'state', 'group_number', 'status'],
            },
            {
                'name': 'All Students',
                'description': 'Active students across all schools and cohorts',
                'is_default': True,
                'target_roles': ['student'],
                'account_status': 'active',
                'engagement_status': 'all',
                'advanced_conditions': [],
                'visible_columns': ['name', 'email', 'role', 'school', 'state', 'group_number', 'status'],
            },
            {
                'name': 'All Mentors',
                'description': 'Active certified mentors across all domains',
                'is_default': True,
                'target_roles': ['mentor'],
                'account_status': 'active',
                'engagement_status': 'all',
                'advanced_conditions': [],
                'visible_columns': [
                    'name', 'email', 'role', 'institution', 'state',
                    'group_number', 'group_count', 'status',
                ],
            },
            {
                'name': 'All Supervisors',
                'description': 'Institution and academic supervisors',
                'is_default': True,
                'target_roles': ['supervisor'],
                'account_status': 'active',
                'engagement_status': 'all',
                'advanced_conditions': [],
                'visible_columns': [
                    'name', 'email', 'role', 'school', 'state',
                    'group_number', 'group_count', 'status',
                ],
            },
            {
                'name': 'All Admins',
                'description': 'Platform administrators with elevated management permissions',
                'is_default': True,
                'target_roles': ['admin'],
                'account_status': 'active',
                'engagement_status': 'all',
                'advanced_conditions': [],
                'visible_columns': ['name', 'email', 'role', 'last_login', 'status'],
            },
        ]:
            AdminView.objects.get_or_create(name=item['name'], defaults=item)

        # Geographies
        self.country = Countries.objects.create(country_name="Australia")
        self.state_nsw = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.state_vic = CountryStates.objects.create(country=self.country, state_name="VIC")

        # Roles
        self.role_student, _ = Roles.objects.get_or_create(role_name="student")
        self.role_mentor, _ = Roles.objects.get_or_create(role_name="mentor")

        # Group
        self.group = Groups.objects.create(group_name="BTF1")

        # Student user 1: Active, NSW, in group
        self.student_user = User.objects.create_user(
            email="student1@example.com",
            first_name="Sofia",
            last_name="Bianchi",
            password="password",
            country=self.country,
            state=self.state_nsw,
        )
        self.student_user.is_active = True
        self.student_user.save()
        StudentProfile.objects.create(
            user=self.student_user,
            school_name="Sydney Grammar School",
            year_lvl="11",
            pg_first_name="Marco",
            pg_last_name="Bianchi",
        )
        RoleAssignmentHistory.objects.create(
            user=self.student_user,
            role=self.role_student,
            valid_from=timezone.now(),
            valid_to=None,
        )
        GroupMembership.objects.create(
            group=self.group,
            user=self.student_user,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

        # Mentor user 1: Active, VIC, in group
        self.mentor_user = User.objects.create_user(
            email="mentor1@example.com",
            first_name="Mary",
            last_name="Somerville",
            password="password",
            country=self.country,
            state=self.state_vic,
        )
        self.mentor_user.is_active = True
        self.mentor_user.save()
        MentorProfile.objects.create(
            user=self.mentor_user,
            institution="Sydney BioTech Institute",
            mentor_reason="Passionate about biology",
        )
        RoleAssignmentHistory.objects.create(
            user=self.mentor_user,
            role=self.role_mentor,
            valid_from=timezone.now(),
            valid_to=None,
        )
        GroupMembership.objects.create(
            group=self.group,
            user=self.mentor_user,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )

        # Student user 2: Inactive, unmatched
        self.inactive_student = User.objects.create_user(
            email="inactive_student@example.com",
            first_name="John",
            last_name="Inactive",
            password="password",
            country=self.country,
            state=self.state_nsw,
        )
        self.inactive_student.deactivate()
        StudentProfile.objects.create(
            user=self.inactive_student,
            school_name="Melbourne Grammar",
            year_lvl="10",
            pg_first_name="Jane",
            pg_last_name="Inactive",
        )
        RoleAssignmentHistory.objects.create(
            user=self.inactive_student,
            role=self.role_student,
            valid_from=timezone.now(),
            valid_to=None,
        )

    # ========================================================================
    # 1. DEFAULT VIEWS & LISTING
    # ========================================================================

    def test_default_views_exist_from_migration(self):
        defaults = AdminView.objects.filter(is_default=True)
        names = set(defaults.values_list("name", flat=True))
        self.assertTrue({"All Users", "All Students", "All Mentors", "All Supervisors", "All Admins"}.issubset(names))

    def test_list_views_endpoint(self):
        res = self.client.get("/api/v1/admin/view/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("items", res.data["data"])
        self.assertGreaterEqual(res.data["data"]["total"], 5)

    def test_list_views_tab_filtering(self):
        # Create a custom view
        AdminView.objects.create(name="Custom 1", is_default=False, created_by=self.admin)

        # Default tab
        res_default = self.client.get("/api/v1/admin/view/?tab=default")
        self.assertEqual(res_default.status_code, status.HTTP_200_OK)
        for item in res_default.data["data"]["items"]:
            self.assertTrue(item["isDefault"])

        # Custom tab
        res_custom = self.client.get("/api/v1/admin/view/?tab=custom")
        self.assertEqual(res_custom.status_code, status.HTTP_200_OK)
        for item in res_custom.data["data"]["items"]:
            self.assertFalse(item["isDefault"])

    # ========================================================================
    # 2. CREATE, UPDATE & DELETE CUSTOM VIEWS
    # ========================================================================

    def test_create_custom_view(self):
        payload = {
            "name": "Australian High School Students",
            "description": "Active grade 11 students in Australia",
            "targetRoles": ["student"],
            "accountStatus": "active",
            "engagementStatus": "matched",
            "advancedConditions": [
                {"field": "country", "operator": "equals", "value": "Australia", "logic": "AND"},
                {"field": "yearLevel", "operator": "equals", "value": "11", "logic": "AND"},
            ],
            "visibleColumns": ["name", "email", "role", "school", "status"],
        }
        res = self.client.post("/api/v1/admin/view/", data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["data"]["name"], "Australian High School Students")
        self.assertFalse(res.data["data"]["isDefault"])

        created = AdminView.objects.get(id=res.data["data"]["id"])
        self.assertEqual(created.target_roles, ["student"])
        self.assertEqual(created.account_status, "active")

    def test_create_view_rejects_empty_or_duplicate_name(self):
        # Empty name
        res1 = self.client.post("/api/v1/admin/view/", data={"name": ""}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # Duplicate name
        res2 = self.client.post("/api/v1/admin/view/", data={"name": "All Users"}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_and_delete_custom_view(self):
        view = AdminView.objects.create(name="Temp View", is_default=False, created_by=self.admin)

        # Update
        res_update = self.client.put(
            f"/api/v1/admin/view/{view.id}/",
            data={"name": "Updated Temp View", "description": "New description"},
            format="json",
        )
        self.assertEqual(res_update.status_code, status.HTTP_200_OK)
        view.refresh_from_db()
        self.assertEqual(view.name, "Updated Temp View")

        # Delete
        res_delete = self.client.delete(f"/api/v1/admin/view/{view.id}/")
        self.assertEqual(res_delete.status_code, status.HTTP_200_OK)
        self.assertFalse(AdminView.objects.filter(id=view.id).exists())

    def test_cannot_update_or_delete_system_default_view(self):
        default_view = AdminView.objects.filter(is_default=True).first()
        self.assertIsNotNone(default_view)

        # Attempt update
        res_update = self.client.put(
            f"/api/v1/admin/view/{default_view.id}/",
            data={"name": "Tampered Default View"},
            format="json",
        )
        self.assertEqual(res_update.status_code, status.HTTP_400_BAD_REQUEST)

        # Attempt delete
        res_delete = self.client.delete(f"/api/v1/admin/view/{default_view.id}/")
        self.assertEqual(res_delete.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_delete_custom_views(self):
        v1 = AdminView.objects.create(name="Bulk 1", is_default=False, created_by=self.admin)
        v2 = AdminView.objects.create(name="Bulk 2", is_default=False, created_by=self.admin)
        def_view = AdminView.objects.filter(is_default=True).first()

        res = self.client.post(
            "/api/v1/admin/view/bulk-delete/",
            data={"viewIds": [v1.id, v2.id, def_view.id]},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["data"]["deletedCount"], 2)
        self.assertFalse(AdminView.objects.filter(id__in=[v1.id, v2.id]).exists())
        self.assertTrue(AdminView.objects.filter(id=def_view.id).exists())

    # ========================================================================
    # 3. QUERY ENGINE & VIEW EXECUTION (/run/)
    # ========================================================================

    def test_run_view_all_users(self):
        view = AdminView.objects.get(name="All Users")
        res = self.client.get(f"/api/v1/admin/view/{view.id}/run/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items = res.data["data"]["items"]
        total = res.data["data"]["total"]
        self.assertGreaterEqual(total, 3)

    def test_run_view_role_and_status_filtering(self):
        view = AdminView.objects.create(
            name="Active Students View",
            target_roles=["student"],
            account_status="active",
            is_default=False,
        )
        res = self.client.get(f"/api/v1/admin/view/{view.id}/run/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items = res.data["data"]["items"]
        emails = [u["email"] for u in items]
        self.assertIn("student1@example.com", emails)
        self.assertNotIn("mentor1@example.com", emails)
        self.assertNotIn("inactive_student@example.com", emails)

    def test_run_view_engagement_status_matched(self):
        view = AdminView.objects.create(
            name="Matched Users",
            engagement_status="matched",
            is_default=False,
        )
        res = self.client.get(f"/api/v1/admin/view/{view.id}/run/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        emails = [u["email"] for u in res.data["data"]["items"]]
        self.assertIn("student1@example.com", emails)
        self.assertIn("mentor1@example.com", emails)
        self.assertNotIn("inactive_student@example.com", emails)

    def test_run_view_advanced_conditions_case_insensitive(self):
        # Case-insensitive equals and contains
        view = AdminView.objects.create(
            name="Sydney Students",
            target_roles=["student"],
            advanced_conditions=[
                {"field": "country", "operator": "equals", "value": "australia", "logic": "AND"},
                {"field": "school", "operator": "contains", "value": "sydney", "logic": "AND"},
            ],
            is_default=False,
        )
        res = self.client.get(f"/api/v1/admin/view/{view.id}/run/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items = res.data["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["email"], "student1@example.com")

    def test_run_view_advanced_conditions_or_logic(self):
        # State NSW OR State VIC
        view = AdminView.objects.create(
            name="NSW or VIC Users",
            advanced_conditions=[
                {"field": "state", "operator": "equals", "value": "NSW", "logic": "AND"},
                {"field": "state", "operator": "equals", "value": "VIC", "logic": "OR"},
            ],
            is_default=False,
        )
        res = self.client.get(f"/api/v1/admin/view/{view.id}/run/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        emails = [u["email"] for u in res.data["data"]["items"]]
        self.assertIn("student1@example.com", emails)
        self.assertIn("mentor1@example.com", emails)

    # ========================================================================
    # 4. CSV EXPORT
    # ========================================================================

    def test_export_view_csv(self):
        # Create an international student with no state and no country/group
        intl_student = User.objects.create_user(
            email="intl_student@example.com",
            first_name="Aria",
            last_name="Suzuki",
            password="password",
        )
        StudentProfile.objects.create(
            user=intl_student,
            school_name="Summit Academy",
            year_lvl="12",
            pg_first_name="Ken",
            pg_last_name="Suzuki",
        )
        RoleAssignmentHistory.objects.create(
            user=intl_student,
            role=self.role_student,
            valid_from=timezone.now(),
            valid_to=None,
        )

        view = AdminView.objects.create(
            name="Export Test View",
            target_roles=["student"],
            visible_columns=["name", "email", "school", "state", "country", "matched_mentor", "status"],
            is_default=False,
        )
        res = self.client.get(f"/api/v1/admin/view/{view.id}/export-csv/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", res["Content-Type"])
        self.assertIn("charset=utf-8", res["Content-Type"])
        self.assertIn('attachment; filename="export_test_view_export.csv"', res["Content-Disposition"])

        content = res.content.decode("utf-8")
        lines = content.strip().split("\r\n")
        header = lines[0]
        self.assertEqual(
            header,
            "Full Name,Email,School / Institution,State,Country,Matched Mentor / Mentee,Status"
        )
        # Sofia Bianchi has state=NSW, country=Australia, in group with mentor Mary Somerville
        sofia_line = next((line for line in lines[1:] if "student1@example.com" in line), None)
        self.assertIsNotNone(sofia_line)
        self.assertIn(",NSW,Australia,Mentor: Mary Somerville,Active", sofia_line)

        # Aria Suzuki has state=None, country=None, unmatched -> '-', 'Unassigned', '-'
        intl_line = next((line for line in lines[1:] if "intl_student@example.com" in line), None)
        self.assertIsNotNone(intl_line)
        self.assertIn(",-,Unassigned,-,", intl_line)
        self.assertNotIn("—", content)

    def test_group_count_column_and_sorting(self):
        # Add mentor_user to a second group so they have 2 active groups
        second_group = Groups.objects.create(group_name="BTF2")
        GroupMembership.objects.create(
            group=second_group,
            user=self.mentor_user,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )

        # Create a second mentor with 0 groups
        unmatched_mentor = User.objects.create_user(
            email="mentor2@example.com",
            first_name="Alan",
            last_name="Turing",
            password="password",
        )
        MentorProfile.objects.create(user=unmatched_mentor, institution="Cambridge")
        RoleAssignmentHistory.objects.create(
            user=unmatched_mentor,
            role=self.role_mentor,
            valid_from=timezone.now(),
            valid_to=None,
        )

        mentors_view = AdminView.objects.get(name="All Mentors")
        self.assertIn("group_count", mentors_view.visible_columns)

        # Run view sorted by groupCount desc
        res = self.client.get(
            f"/api/v1/admin/view/{mentors_view.id}/run/?sortBy=groupCount&sortOrder=desc"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items = res.data["data"]["items"]
        self.assertEqual(items[0]["email"], "mentor1@example.com")
        self.assertEqual(items[0]["groupCount"], 2)
        self.assertEqual(items[1]["email"], "mentor2@example.com")
        self.assertEqual(items[1]["groupCount"], 0)

        # Verify CSV export includes Number of Groups column and values
        csv_res = self.client.get(f"/api/v1/admin/view/{mentors_view.id}/export-csv/")
        csv_content = csv_res.content.decode("utf-8")
        lines = csv_content.strip().split("\r\n")
        self.assertIn("Number of Groups", lines[0])
        mary_line = next((line for line in lines[1:] if "mentor1@example.com" in line), None)
        self.assertIsNotNone(mary_line)
        self.assertIn(",2,Active", mary_line)

    def test_group_number_column_and_sorting(self):
        # "Group Number" is the name of the group(s) a user is in; "Number of
        # Groups" is how many. They are separate columns.
        self.assertIn("group_number", AdminView.objects.get(name="All Mentors").visible_columns)
        self.assertIn("group_count", AdminView.objects.get(name="All Mentors").visible_columns)

        # The mentor joins a second group, so their groups are "BTF1" and "BTF10".
        second_group = Groups.objects.create(group_name="BTF10")
        GroupMembership.objects.create(
            group=second_group,
            user=self.mentor_user,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )

        # A mentor in a later group, and one in no group at all.
        role_supervisor, _ = Roles.objects.get_or_create(role_name="supervisor")
        later_mentor = User.objects.create_user(
            email="mentor2@example.com",
            first_name="Alan",
            last_name="Turing",
            password="password",
        )
        MentorProfile.objects.create(user=later_mentor, institution="Cambridge")
        RoleAssignmentHistory.objects.create(
            user=later_mentor,
            role=self.role_mentor,
            valid_from=timezone.now(),
            valid_to=None,
        )
        GroupMembership.objects.create(
            group=Groups.objects.create(group_name="BTF2"),
            user=later_mentor,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        ungrouped_mentor = User.objects.create_user(
            email="mentor3@example.com",
            first_name="Grace",
            last_name="Hopper",
            password="password",
        )
        MentorProfile.objects.create(user=ungrouped_mentor, institution="Cambridge")
        RoleAssignmentHistory.objects.create(
            user=ungrouped_mentor,
            role=self.role_mentor,
            valid_from=timezone.now(),
            valid_to=None,
        )

        # A supervisor in a group gets the group name too.
        supervisor = User.objects.create_user(
            email="supervisor1@example.com",
            first_name="Karen",
            last_name="Sparck",
            password="password",
        )
        SupervisorProfile.objects.create(user=supervisor, school_name="USyd")
        RoleAssignmentHistory.objects.create(
            user=supervisor,
            role=role_supervisor,
            valid_from=timezone.now(),
            valid_to=None,
        )
        GroupMembership.objects.create(
            group=Groups.objects.create(group_name="BTF6"),
            user=supervisor,
            membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR,
        )

        # Mentors: the two groups of one mentor are listed, comma separated.
        mentors_view = AdminView.objects.get(name="All Mentors")
        res = self.client.get(
            f"/api/v1/admin/view/{mentors_view.id}/run/?sortBy=groupNumber&sortOrder=asc"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items = res.data["data"]["items"]
        by_email = {u["email"]: u for u in items}

        self.assertEqual(by_email["mentor1@example.com"]["groupNumbers"], "BTF1, BTF10")
        self.assertEqual(by_email["mentor1@example.com"]["groupCount"], 2)
        self.assertEqual(by_email["mentor2@example.com"]["groupNumbers"], "BTF2")
        self.assertEqual(by_email["mentor3@example.com"]["groupNumbers"], "")

        # Sorted by group number, and listed once each even though the first
        # mentor is in two groups.
        self.assertEqual(len(items), len(by_email))
        grouped = [u["email"] for u in items if u["groupNumbers"]]
        self.assertEqual(grouped, ["mentor1@example.com", "mentor2@example.com"])

        # A student is in one group, so it reads as a single group number.
        students_view = AdminView.objects.get(name="All Students")
        students_res = self.client.get(f"/api/v1/admin/view/{students_view.id}/run/")
        student_items = {
            u["email"]: u for u in students_res.data["data"]["items"]
        }
        self.assertEqual(student_items["student1@example.com"]["groupNumbers"], "BTF1")

        # A supervisor in a group is listed with it too.
        supervisors_view = AdminView.objects.get(name="All Supervisors")
        supervisors_res = self.client.get(f"/api/v1/admin/view/{supervisors_view.id}/run/")
        supervisor_items = {
            u["email"]: u for u in supervisors_res.data["data"]["items"]
        }
        self.assertEqual(supervisor_items["supervisor1@example.com"]["groupNumbers"], "BTF6")

        # CSV export carries the column and its comma separated value.
        csv_res = self.client.get(f"/api/v1/admin/view/{mentors_view.id}/export-csv/")
        csv_content = csv_res.content.decode("utf-8")
        lines = csv_content.strip().split("\r\n")
        self.assertIn("Group Number", lines[0])
        mary_line = next((line for line in lines[1:] if "mentor1@example.com" in line), None)
        self.assertIsNotNone(mary_line)
        self.assertIn('"BTF1, BTF10"', mary_line)

