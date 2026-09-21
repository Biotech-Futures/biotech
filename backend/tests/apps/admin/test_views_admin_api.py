from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin.models import AdminView
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import MentorProfile, StudentProfile, User
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
        self.assertTrue({"All Users", "All Mentors", "All Supervisors", "All Admins"}.issubset(names))

    def test_list_views_endpoint(self):
        res = self.client.get("/api/v1/admin/view/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("items", res.data["data"])
        self.assertGreaterEqual(res.data["data"]["total"], 4)

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
        view = AdminView.objects.create(
            name="Export Test View",
            target_roles=["student"],
            visible_columns=["name", "email", "school", "status"],
            is_default=False,
        )
        res = self.client.get(f"/api/v1/admin/view/{view.id}/export-csv/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertIn('attachment; filename="export_test_view_export.csv"', res["Content-Disposition"])

        content = res.content.decode("utf-8")
        lines = content.strip().split("\r\n")
        header = lines[0]
        self.assertEqual(header, "Full Name,Email,School / Institution,Status")
        self.assertTrue(any("student1@example.com" in line for line in lines[1:]))
