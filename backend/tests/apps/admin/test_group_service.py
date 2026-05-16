from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.db import IntegrityError, transaction
from unittest.mock import patch

from apps.admin.services.group import (
    delete_group,
    query_group_messages,
    query_groups,
    remove_group_message,
    restore_group,
    restore_group_message,
)
from apps.chat.models import Messages
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership, Tracks
from apps.users.models import AdminScope
from apps.users.models import MentorProfile, User


class AdminGroupServiceTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="TRACK-1", state=state)
        self.group = Groups.objects.create(group_name="Group One", track=self.track)
        self.mentor = User.objects.create_user(
            email="mentor@example.com",
            first_name="Mina",
            last_name="Mentor",
            track=self.track,
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
        self.admin = User.objects.create_user(
            email="admin@example.com",
            first_name="Ada",
            last_name="Admin",
            password="testpass",
        )
        AdminScope.objects.create(user=self.admin, is_global=True)

    def test_query_groups_uses_adminweb_camel_case_contract(self):
        result = query_groups()
        group = result["data"]["items"][0]

        self.assertIn("createdAt", group)
        self.assertIn("updatedAt", group)
        self.assertNotIn("created_at", group)
        self.assertEqual(group["mentor"]["membershipId"], self.membership.id)
        self.assertNotIn("membership_id", group["mentor"])

    def test_query_groups_orders_by_created_at_desc(self):
        older = self.group
        newer = Groups.objects.create(group_name="Group Two", track=self.track)

        now = timezone.now()
        Groups.objects.filter(id=older.id).update(created_at=now - timedelta(days=1))
        Groups.objects.filter(id=newer.id).update(created_at=now)

        result = query_groups(limit=10)

        self.assertEqual(
            [group["id"] for group in result["data"]["items"]],
            [str(newer.id), str(older.id)],
        )

    def test_query_groups_deleted_filter_and_restore_group(self):
        now = timezone.now()
        deleted_group = Groups.objects.create(
            group_name="Deleted Group",
            track=self.track,
            created_at=now - timedelta(seconds=1),
            deleted_at=now,
        )

        result = query_groups(deleted=True)

        self.assertEqual(result["data"]["total"], 1)
        self.assertEqual(result["data"]["items"][0]["id"], str(deleted_group.id))
        self.assertEqual(result["data"]["items"][0]["deletedAt"], now.isoformat())

        restore_result = restore_group(str(deleted_group.id))

        self.assertEqual(restore_result["msg"], "Group restored successfully")
        deleted_group.refresh_from_db()
        self.assertIsNone(deleted_group.deleted_at)

    def test_delete_group_allows_name_reuse_but_not_duplicate_active_name(self):
        result = delete_group(str(self.group.id), requesting_user=self.admin)

        self.assertEqual(result["msg"], "Group deleted successfully")
        self.group.refresh_from_db()
        self.assertIsNotNone(self.group.deleted_at)

        replacement = Groups.objects.create(
            group_name=self.group.group_name,
            track=self.track,
        )
        self.assertEqual(replacement.group_name, self.group.group_name)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Groups.objects.create(group_name=self.group.group_name, track=self.track)

    @patch("apps.admin.services.group._broadcast")
    def test_remove_group_message_records_admin_and_broadcasts_tombstone(self, broadcast):
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.mentor,
            message_text="remove me",
        )

        result = remove_group_message(str(self.group.id), message.id, actor=self.admin)

        self.assertEqual(result["msg"], "Group message removed successfully")
        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)
        self.assertEqual(message.deleted_by_id, self.admin.id)
        broadcast.assert_called_once()
        self.assertEqual(broadcast.call_args.args[1], "message.deleted")
        self.assertEqual(broadcast.call_args.args[2]["message_text"], "")
        self.assertTrue(broadcast.call_args.args[2]["deleted_by_is_admin"])

    @patch("apps.admin.services.group._broadcast")
    def test_restore_group_message_restores_deleted_message(self, broadcast):
        now = timezone.now()
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.mentor,
            message_text="restore me",
            sent_at=now,
            deleted_at=now,
            deleted_by=self.admin,
        )

        result = restore_group_message(str(self.group.id), message.id, actor=self.admin)

        self.assertEqual(result["msg"], "Group message restored successfully")
        message.refresh_from_db()
        self.assertIsNone(message.deleted_at)
        self.assertIsNone(message.deleted_by_id)
        broadcast.assert_called_once()
        self.assertEqual(broadcast.call_args.args[1], "message.restored")

    def test_query_group_deleted_messages_returns_admin_tombstone_label(self):
        now = timezone.now()
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.mentor,
            message_text="deleted content",
            sent_at=now,
            deleted_at=now,
            deleted_by=self.admin,
        )

        result = query_group_messages(str(self.group.id), deleted=True)
        item = result["data"]["items"][0]

        self.assertEqual(item["id"], str(message.id))
        self.assertEqual(item["text"], "")
        self.assertEqual(item["deleted_by_name"], "Admin")
        self.assertTrue(item["deleted_by_is_admin"])
