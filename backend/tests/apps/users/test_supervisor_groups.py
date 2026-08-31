from rest_framework.test import APIClient

from django.test import TestCase

from apps.groups.models import GroupMembership, Groups
from apps.users.models import MentorProfile, StudentProfile, SupervisorProfile, User


class SupervisedGroupsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.supervisor = User.objects.create_user(
            email="supervisor@test.com",
            first_name="Sam",
            last_name="Supervisor",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        self.sup_profile = SupervisorProfile.objects.create(
            user=self.supervisor, school_name="Test High"
        )
        self.student = User.objects.create_user(
            email="alice.smith@test.com",
            first_name="Alice",
            last_name="Smith",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        StudentProfile.objects.create(
            user=self.student,
            pg_first_name="Bob",
            pg_last_name="Smith",
            parent_guardian_flag=True,
            supervisor=self.sup_profile,
            school_name="Waterpark High School",
            year_lvl="11",
            has_join_permission=True,
        )
        self.mentor = User.objects.create_user(
            email="mentor@test.com",
            first_name="Mina",
            last_name="Mentor",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )
        MentorProfile.objects.create(
            user=self.mentor,
            institution="Test University",
            mentor_reason="Mentoring students",
            max_group_count=5,
        )
        self.outsider = User.objects.create_user(
            email="outsider@test.com",
            first_name="Out",
            last_name="Sider",
            password="Testpass123!",
            is_active=True,
            account_status=User.AccountStatus.ACTIVE,
        )

    def test_supervisor_can_create_and_manage_group(self):
        self.client.force_login(self.supervisor)
        created = self.client.post(
            "/api/v1/users/supervised-groups/",
            {"group_name": "Aerospace Crew"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        group_id = created.json()["id"]
        self.assertEqual(created.json()["group_name"], "Aerospace Crew")
        self.assertEqual(created.json()["members"][0]["role"], "supervisor")

        renamed = self.client.patch(
            f"/api/v1/users/supervised-groups/{group_id}/",
            {"group_name": "Waterpark Aerospace"},
            format="json",
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["group_name"], "Waterpark Aerospace")

        added = self.client.post(
            f"/api/v1/users/supervised-groups/{group_id}/members/",
            {"user_ids": [self.student.id], "role": "student"},
            format="json",
        )
        self.assertEqual(added.status_code, 200)
        roles = {row["email"]: row["role"] for row in added.json()["members"]}
        self.assertEqual(roles["alice.smith@test.com"], "student")

        mentor = self.client.post(
            f"/api/v1/users/supervised-groups/{group_id}/members/",
            {"user_ids": [self.mentor.id], "role": "mentor"},
            format="json",
        )
        self.assertEqual(mentor.status_code, 200)
        roles = {row["email"]: row["role"] for row in mentor.json()["members"]}
        self.assertEqual(roles["mentor@test.com"], "mentor")

        removed = self.client.delete(
            f"/api/v1/users/supervised-groups/{group_id}/members/",
            {"user_ids": [self.student.id]},
            format="json",
        )
        self.assertEqual(removed.status_code, 200)
        emails = [row["email"] for row in removed.json()["members"]]
        self.assertNotIn("alice.smith@test.com", emails)

        deleted = self.client.delete(f"/api/v1/users/supervised-groups/{group_id}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertTrue(Groups.objects.get(pk=group_id).deleted_at)

    def test_adding_student_moves_them_from_previous_group(self):
        self.client.force_login(self.supervisor)
        first = self.client.post(
            "/api/v1/users/supervised-groups/",
            {"group_name": "First Crew"},
            format="json",
        )
        second = self.client.post(
            "/api/v1/users/supervised-groups/",
            {"group_name": "Second Crew"},
            format="json",
        )
        first_id = first.json()["id"]
        second_id = second.json()["id"]
        self.client.post(
            f"/api/v1/users/supervised-groups/{first_id}/members/",
            {"user_ids": [self.student.id], "role": "student"},
            format="json",
        )

        moved = self.client.post(
            f"/api/v1/users/supervised-groups/{second_id}/members/",
            {"user_ids": [self.student.id], "role": "student"},
            format="json",
        )
        self.assertEqual(moved.status_code, 200)
        dest_emails = [row["email"] for row in moved.json()["members"]]
        self.assertIn("alice.smith@test.com", dest_emails)

        previous = self.client.get(f"/api/v1/users/supervised-groups/{first_id}/")
        self.assertEqual(previous.status_code, 200)
        previous_emails = [row["email"] for row in previous.json()["members"]]
        self.assertNotIn("alice.smith@test.com", previous_emails)
        self.assertTrue(
            GroupMembership.objects.filter(
                group_id=first_id,
                user=self.supervisor,
                left_at__isnull=True,
                membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR,
            ).exists()
        )

    def test_supervisor_cannot_add_unlinked_student(self):
        self.client.force_login(self.supervisor)
        group = Groups.objects.create(group_name="Private")
        GroupMembership.objects.create(
            group=group,
            user=self.supervisor,
            membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR,
        )
        response = self.client.post(
            f"/api/v1/users/supervised-groups/{group.id}/members/",
            {"user_ids": [self.outsider.id], "role": "student"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_create_rejects_duplicate_name(self):
        self.client.force_login(self.supervisor)
        Groups.objects.create(group_name="New Group")
        response = self.client.post(
            "/api/v1/users/supervised-groups/",
            {"group_name": "New Group"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Choose a different name", str(response.json()))

    def test_non_supervisor_is_forbidden(self):
        self.client.force_login(self.outsider)
        response = self.client.get("/api/v1/users/supervised-groups/")
        self.assertEqual(response.status_code, 403)

    def test_supervisor_can_tag_multiple_group_interests(self):
        self.client.force_login(self.supervisor)
        created = self.client.post(
            "/api/v1/users/supervised-groups/",
            {
                "group_name": "Multi Area Crew",
                "interests": ["Biomedical Innovations", "Space & Astrobiology"],
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            set(created.json()["interests"]),
            {"Biomedical Innovations", "Space & Astrobiology"},
        )

        group_id = created.json()["id"]
        updated = self.client.patch(
            f"/api/v1/users/supervised-groups/{group_id}/",
            {
                "interests": [
                    "Water & Energy Tech",
                    "Biomedical Innovations",
                    "AI & Robotics and Smart Systems",
                ]
            },
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            set(updated.json()["interests"]),
            {
                "Water & Energy Tech",
                "Biomedical Innovations",
                "AI & Robotics and Smart Systems",
            },
        )
        self.assertEqual(updated.json()["group_name"], "Multi Area Crew")

        catalog = self.client.get("/api/v1/users/supervised-groups/interests/")
        self.assertEqual(catalog.status_code, 200)
        self.assertIn("Biomedical Innovations", catalog.json()["interests"])
        self.assertIn("Water & Energy Tech", catalog.json()["interests"])
