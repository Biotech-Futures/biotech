from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.admin.services.group import (
    query_groups, query_group_by_id, query_group_messages,
    update_group, remove_group_member, remove_group_message,
)
from apps.chat.models import Messages
from apps.groups.models import Groups, GroupMembership
from apps.users.models import MentorProfile, StudentProfile, User


class AdminGroupServiceTests(TestCase):
    def setUp(self):
        self.group = Groups.objects.create(group_name="Group One")
        self.mentor = User.objects.create_user(
            email="mentor@example.com",
            first_name="Mina",
            last_name="Mentor",
            password="testpass",
        )
        MentorProfile.objects.create(
            user=self.mentor,
            institution="UNSW",
            mentor_reason="Testing",
        )
        self.membership = GroupMembership.objects.create(
            group=self.group,
            user=self.mentor,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        self.admin_user = User.objects.create_user(
            email="admin@example.com", first_name="Admin", password="testpass",
        )
        from apps.users.models.admin_scope import AdminScope
        AdminScope.objects.create(user=self.admin_user)

    def test_query_groups_uses_adminweb_camel_case_contract(self):
        result = query_groups(requesting_user=self.admin_user)
        group = result["data"]["items"][0]

        self.assertIn("createdAt", group)
        self.assertIn("updatedAt", group)
        self.assertNotIn("created_at", group)
        self.assertEqual(group["mentor"]["membershipId"], self.membership.id)
        self.assertNotIn("membership_id", group["mentor"])

    def test_query_groups_orders_by_created_at_desc(self):
        older = self.group
        newer = Groups.objects.create(group_name="Group Two")

        now = timezone.now()
        Groups.objects.filter(id=older.id).update(created_at=now - timedelta(days=1))
        Groups.objects.filter(id=newer.id).update(created_at=now)

        result = query_groups(limit=10, requesting_user=self.admin_user)

        self.assertEqual(
            [group["id"] for group in result["data"]["items"]],
            [str(newer.id), str(older.id)],
        )

    def test_query_group_messages_handles_removed_gif_relation(self):
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.mentor,
            message_text="Hello from the admin history endpoint",
        )

        result = query_group_messages(str(self.group.id))

        self.assertEqual(result["msg"], "Group messages retrieved successfully")
        self.assertEqual(result["data"]["total"], 1)
        self.assertEqual(result["data"]["items"][0]["id"], str(message.id))
        self.assertIsNone(result["data"]["items"][0]["gif"])

    def test_query_group_by_id_found(self):
        result = query_group_by_id(str(self.group.id))
        self.assertEqual(result["msg"], "Group retrieved successfully")
        self.assertEqual(result["data"]["name"], "Group One")

    def test_query_group_by_id_invalid(self):
        result = query_group_by_id("not-a-number")
        self.assertEqual(result["msg"], "Group not found")
        self.assertIsNone(result["data"])

    def test_query_group_by_id_not_found(self):
        result = query_group_by_id("9999")
        self.assertEqual(result["msg"], "Group not found")
        self.assertIsNone(result["data"])

    def test_query_group_messages_empty(self):
        result = query_group_messages(str(self.group.id))
        self.assertEqual(result["data"]["items"], [])

    def test_query_group_messages_invalid_group_id(self):
        result = query_group_messages("bad")
        self.assertEqual(result["msg"], "Group not found")
        self.assertIsNone(result["data"])

    def test_query_group_messages_group_not_found(self):
        result = query_group_messages("9999")
        self.assertEqual(result["msg"], "Group not found")
        self.assertIsNone(result["data"])

    def test_update_group_name(self):
        result = update_group(str(self.group.id), name="Updated Group")
        self.assertEqual(result["msg"], "Group updated successfully")
        self.assertEqual(result["data"]["name"], "Updated Group")

    def test_update_group_invalid_id(self):
        result = update_group("bad", name="Test")
        self.assertEqual(result["msg"], "Group not found")
        self.assertIsNone(result["data"])

    def test_update_group_not_found(self):
        result = update_group("9999", name="Test")
        self.assertEqual(result["msg"], "Group not found")
        self.assertIsNone(result["data"])

    def test_remove_group_member(self):
        student = User.objects.create_user(
            email="student@example.com", first_name="Stud", last_name="Ent",
            password="testpass",
        )
        StudentProfile.objects.create(
            user=student, pg_first_name="P", pg_last_name="E",
            parent_guardian_flag=True, school_name="Test School", year_lvl="10",
        )
        GroupMembership.objects.create(
            user=student, group=self.group, membership_role="student",
        )
        result = remove_group_member(str(self.group.id), student.id)
        self.assertEqual(result["msg"], "Group member removed successfully")
        self.assertFalse(
            GroupMembership.objects.filter(
                user=student, group=self.group, left_at__isnull=True,
            ).exists()
        )

    def test_remove_group_member_not_found(self):
        result = remove_group_member(str(self.group.id), 9999)
        self.assertEqual(result["msg"], "Group member not found")
        self.assertIsNone(result["data"])

    def test_remove_group_member_invalid_group(self):
        result = remove_group_member("bad", 1)
        self.assertEqual(result["msg"], "Group not found")
        self.assertIsNone(result["data"])

    def test_remove_group_message(self):
        student = User.objects.create_user(
            email="sender@example.com", first_name="Sender", password="testpass",
        )
        message = Messages.objects.create(
            group=self.group, sender_user=student, message_text="Delete me",
        )
        result = remove_group_message(str(self.group.id), message.id)
        self.assertEqual(result["msg"], "Group message removed successfully")
        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)

    def test_remove_group_message_not_found(self):
        result = remove_group_message(str(self.group.id), 9999)
        self.assertEqual(result["msg"], "Group message not found")
        self.assertIsNone(result["data"])

    def test_remove_group_message_invalid_group(self):
        result = remove_group_message("bad", 1)
        self.assertEqual(result["msg"], "Group not found")
        self.assertIsNone(result["data"])
