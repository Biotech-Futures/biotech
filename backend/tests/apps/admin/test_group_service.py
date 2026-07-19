from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.admin.services.group import (
    create_group, query_groups, query_group_by_id, query_group_messages,
    update_group, remove_group_member, remove_group_message,
    delete_group, bulk_delete_groups, bulk_delete_groups_by_filter,
)
from apps.audit.models import AuditLog
from apps.chat.models import Messages
from apps.groups.models import GroupAutoNameUnavailable, Groups, GroupMembership
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

    def test_query_groups_sorted_by_name_orders_auto_names_numerically(self):
        # Without the virtual zero-padding "BTF10" would sort before "BTF9".
        for name in ("BTF10", "BTF9", "BTF100", "BTF2"):
            Groups.objects.create(group_name=name)

        result = query_groups(
            limit=20, sort_by="name", sort_order="asc", requesting_user=self.admin_user,
        )

        names = [group["name"] for group in result["data"]["items"]]
        self.assertEqual(
            [name for name in names if name.startswith("BTF")],
            ["BTF2", "BTF9", "BTF10", "BTF100"],
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

    def test_update_group_strips_surrounding_whitespace(self):
        result = update_group(str(self.group.id), name="  Padded Group  ")
        self.assertEqual(result["data"]["name"], "Padded Group")

    def test_update_group_rejects_blank_name(self):
        result = update_group(str(self.group.id), name="   ")
        self.assertEqual(result["msg"], "Group name is required")
        self.assertIsNone(result["data"])
        self.group.refresh_from_db()
        self.assertEqual(self.group.group_name, "Group One")

    def test_update_group_rejects_duplicate_name(self):
        Groups.objects.create(group_name="Group Two")

        result = update_group(str(self.group.id), name="Group Two")

        self.assertEqual(result["msg"], "A group with this name already exists")
        self.assertIsNone(result["data"])
        self.group.refresh_from_db()
        self.assertEqual(self.group.group_name, "Group One")

    def test_update_group_rejects_duplicate_that_races_past_the_precheck(self):
        # Drives the IntegrityError fallback: the pre-check is what normally catches
        # a duplicate, so only a forced miss exercises the DB constraint behind it.
        Groups.objects.create(group_name="Group Two")

        with mock.patch("apps.admin.services.group._active_name_taken", return_value=False):
            result = update_group(
                str(self.group.id), name="Group Two", initiated_by=self.admin_user,
            )

        self.assertEqual(result["msg"], "A group with this name already exists")
        self.assertIsNone(result["data"])
        self.group.refresh_from_db()
        self.assertEqual(self.group.group_name, "Group One")
        self.assertFalse(AuditLog.objects.filter(entity_type="group").exists())

    def test_update_group_rejects_non_string_name(self):
        result = update_group(str(self.group.id), name=123)

        self.assertEqual(result["msg"], "Group name is required")
        self.assertIsNone(result["data"])
        self.group.refresh_from_db()
        self.assertEqual(self.group.group_name, "Group One")

    def test_update_group_rejects_over_length_name(self):
        result = update_group(str(self.group.id), name="x" * 256)

        self.assertEqual(result["msg"], "Group name must be 255 characters or fewer")
        self.assertIsNone(result["data"])
        self.group.refresh_from_db()
        self.assertEqual(self.group.group_name, "Group One")

    def test_update_group_allows_name_freed_by_soft_delete(self):
        # unique_active_group_name is partial on deleted_at IS NULL, so a
        # soft-deleted group must not reserve its name. created_at is pinned to
        # the past for the model's deleted_at >= created_at CHECK constraint.
        Groups.objects.create(
            group_name="Group Two",
            created_at=timezone.now() - timedelta(days=1),
            deleted_at=timezone.now(),
        )

        result = update_group(str(self.group.id), name="Group Two")

        self.assertEqual(result["msg"], "Group updated successfully")
        self.assertEqual(result["data"]["name"], "Group Two")

    def test_update_group_accepts_its_own_current_name(self):
        result = update_group(str(self.group.id), name="Group One")

        self.assertEqual(result["msg"], "Group updated successfully")
        self.assertEqual(result["data"]["name"], "Group One")

    def test_update_group_without_name_leaves_group_untouched(self):
        result = update_group(str(self.group.id))

        self.assertEqual(result["data"]["name"], "Group One")
        self.assertFalse(AuditLog.objects.filter(entity_type="group").exists())

    def test_update_group_logs_audit_event(self):
        update_group(str(self.group.id), name="Renamed Group", initiated_by=self.admin_user)

        entry = AuditLog.objects.get(entity_type="group", action="update")
        self.assertEqual(entry.actor_user, self.admin_user)
        self.assertEqual(entry.entity_id, self.group.id)
        self.assertEqual(entry.before_state, {"name": "Group One"})
        self.assertEqual(entry.after_state, {"name": "Renamed Group"})

    def test_update_group_skips_audit_event_when_name_unchanged(self):
        update_group(str(self.group.id), name="Group One", initiated_by=self.admin_user)
        self.assertFalse(AuditLog.objects.filter(entity_type="group").exists())

    def test_create_group_strips_surrounding_whitespace(self):
        result = create_group("  Fresh Group  ")
        self.assertEqual(result["data"]["name"], "Fresh Group")

    def test_create_group_rejects_duplicate_name(self):
        result = create_group("Group One")
        self.assertEqual(result["msg"], "A group with this name already exists")
        self.assertIsNone(result["data"])

    def test_create_group_auto_names_when_name_blank(self):
        for number, blank in enumerate((None, "", "   "), start=1):
            with self.subTest(name=blank):
                result = create_group(blank)
                self.assertEqual(result["msg"], "Group created successfully")
                self.assertEqual(result["data"]["name"], f"BTF{number}")

    def test_create_group_explicit_name_wins_over_auto(self):
        result = create_group("Human Chosen")
        self.assertEqual(result["data"]["name"], "Human Chosen")

    def test_create_group_steps_over_a_hand_named_squatter(self):
        Groups.objects.create(group_name="BTF5")

        result = create_group(None)

        self.assertEqual(result["msg"], "Group created successfully")
        self.assertEqual(result["data"]["name"], "BTF6")

    def test_create_group_never_reuses_a_soft_deleted_number(self):
        create_group(None)
        dead_id = create_group(None)["data"]["id"]
        now = timezone.now()
        Groups.objects.filter(id=dead_id).update(
            created_at=now - timedelta(days=1), deleted_at=now,
        )

        self.assertEqual(create_group(None)["data"]["name"], "BTF3")

    def test_create_group_reports_an_exhausted_auto_name(self):
        # Only reachable now by losing every retry, so drive it directly.
        with mock.patch.object(
            Groups, "create_auto_named", side_effect=GroupAutoNameUnavailable("BTF7"),
        ):
            result = create_group(None)

        self.assertIsNone(result["data"])
        self.assertIn("BTF7", result["msg"])

    def test_create_group_rejects_non_string_name(self):
        result = create_group(123)
        self.assertEqual(result["msg"], "Group name is required")
        self.assertIsNone(result["data"])

    def test_create_group_rejects_over_length_name(self):
        result = create_group("x" * 256)
        self.assertEqual(result["msg"], "Group name must be 255 characters or fewer")
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

    # --- delete_group (hard delete) ----------------------------------------

    def _make_workshop(self, group):
        from apps.workshops.models import Workshops

        return Workshops.objects.create(
            workshop_name="Intro Session",
            start_datetime=timezone.now(),
            duration=timedelta(hours=1),
            location="Zoom",
            host_user=self.mentor,
            group=group,
        )

    def test_delete_group_hard_deletes_and_cascades_membership(self):
        result = delete_group(str(self.group.id), initiated_by=self.admin_user)

        self.assertEqual(result["msg"], "Group deleted successfully")
        self.assertEqual(result["data"]["id"], str(self.group.id))
        self.assertFalse(Groups.objects.filter(id=self.group.id).exists())
        # Memberships CASCADE with the group.
        self.assertFalse(
            GroupMembership.objects.filter(id=self.membership.id).exists()
        )

    def test_delete_group_invalid_id(self):
        result = delete_group("bad")
        self.assertEqual(result["msg"], "Group not found")
        self.assertIsNone(result["data"])

    def test_delete_group_not_found(self):
        result = delete_group("9999")
        self.assertEqual(result["msg"], "Group not found")
        self.assertIsNone(result["data"])

    def test_delete_group_already_deleted_is_not_found(self):
        g2 = Groups.objects.create(group_name="Group Two")
        delete_group(str(g2.id))
        result = delete_group(str(g2.id))
        self.assertEqual(result["msg"], "Group not found")
        self.assertIsNone(result["data"])

    def test_delete_group_logs_audit_event(self):
        delete_group(str(self.group.id), initiated_by=self.admin_user)

        entry = AuditLog.objects.get(entity_type="group", action="delete")
        self.assertEqual(entry.actor_user, self.admin_user)
        self.assertEqual(entry.entity_id, self.group.id)

    def test_delete_group_blocked_by_workshop_without_force(self):
        self._make_workshop(self.group)

        result = delete_group(str(self.group.id))

        self.assertEqual(
            result["msg"],
            "Group cannot be deleted because other records reference it",
        )
        self.assertIsNone(result["data"])
        self.assertTrue(Groups.objects.filter(id=self.group.id).exists())

    def test_delete_group_force_purges_workshop(self):
        workshop = self._make_workshop(self.group)

        result = delete_group(
            str(self.group.id), initiated_by=self.admin_user, force=True
        )

        self.assertEqual(result["msg"], "Group deleted successfully")
        self.assertFalse(Groups.objects.filter(id=self.group.id).exists())
        from apps.workshops.models import Workshops
        self.assertFalse(Workshops.objects.filter(pk=workshop.pk).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                entity_type="group", action="force_delete"
            ).exists()
        )

    # --- bulk_delete_groups (hard delete) ----------------------------------

    def test_bulk_delete_groups_hard_deletes_multiple(self):
        g2 = Groups.objects.create(group_name="Group Two")
        g3 = Groups.objects.create(group_name="Group Three")

        result = bulk_delete_groups([g2.id, g3.id], initiated_by=self.admin_user)

        self.assertCountEqual(result["data"]["deletedIds"], [g2.id, g3.id])
        self.assertEqual(result["data"]["failedIds"], [])
        self.assertEqual(result["data"]["notFoundIds"], [])
        self.assertFalse(Groups.objects.filter(id__in=[g2.id, g3.id]).exists())

    def test_bulk_delete_groups_reports_failed_when_protected(self):
        g2 = Groups.objects.create(group_name="Group Two")
        self._make_workshop(g2)

        result = bulk_delete_groups([g2.id])

        self.assertEqual(result["data"]["deletedIds"], [])
        self.assertEqual(result["data"]["failedIds"], [g2.id])
        self.assertTrue(Groups.objects.filter(id=g2.id).exists())

        forced = bulk_delete_groups([g2.id], force=True)
        self.assertEqual(forced["data"]["deletedIds"], [g2.id])
        self.assertFalse(Groups.objects.filter(id=g2.id).exists())

    def test_bulk_delete_groups_dedupes_and_reports_not_found(self):
        g2 = Groups.objects.create(group_name="Group Two")

        result = bulk_delete_groups([g2.id, g2.id, 9999])

        self.assertEqual(result["data"]["deletedIds"], [g2.id])
        self.assertEqual(result["data"]["notFoundIds"], [9999])

    def test_bulk_delete_groups_rejects_empty_or_bad_ids(self):
        self.assertIsNone(bulk_delete_groups([])["data"])
        self.assertIsNone(bulk_delete_groups(["bad"])["data"])

    # --- bulk_delete_groups_by_filter --------------------------------------

    def test_bulk_delete_groups_by_filter_respects_mentor_status(self):
        # self.group has a mentor (matched); g2 has none (unmatched).
        g2 = Groups.objects.create(group_name="Unmatched Group")

        result = bulk_delete_groups_by_filter(
            {"mentorStatus": "unmatched"}, initiated_by=self.admin_user
        )

        self.assertEqual(result["data"]["deletedIds"], [g2.id])
        self.assertTrue(Groups.objects.filter(id=self.group.id).exists())
        self.assertFalse(Groups.objects.filter(id=g2.id).exists())

    def test_bulk_delete_groups_by_filter_honors_exclude_ids(self):
        g2 = Groups.objects.create(group_name="Group Two")

        result = bulk_delete_groups_by_filter({}, exclude_ids=[g2.id])

        self.assertNotIn(g2.id, result["data"]["deletedIds"])
        self.assertIn(self.group.id, result["data"]["deletedIds"])
        self.assertTrue(Groups.objects.filter(id=g2.id).exists())

    def test_bulk_delete_groups_by_filter_expected_count_guard(self):
        # Two active groups now match, but the admin reviewed only one.
        Groups.objects.create(group_name="Group Two")

        result = bulk_delete_groups_by_filter({}, expected_count=1)

        self.assertIsNone(result["data"])
        self.assertIn("changed", result["msg"])
        self.assertTrue(Groups.objects.filter(id=self.group.id).exists())

    def test_bulk_delete_groups_by_filter_force_purges_workshops(self):
        # self.group is matched and has a PROTECT-ing workshop.
        workshop = self._make_workshop(self.group)

        result = bulk_delete_groups_by_filter(
            {"mentorStatus": "matched"}, initiated_by=self.admin_user, force=True
        )

        self.assertIn(self.group.id, result["data"]["deletedIds"])
        self.assertFalse(Groups.objects.filter(id=self.group.id).exists())
        from apps.workshops.models import Workshops
        self.assertFalse(Workshops.objects.filter(pk=workshop.pk).exists())

    def test_bulk_delete_groups_by_filter_empty_set(self):
        result = bulk_delete_groups_by_filter({"searchGroup": "no-such-group"})

        self.assertEqual(result["msg"], "No matching groups to delete")
        self.assertEqual(result["data"]["deletedIds"], [])
        self.assertEqual(result["data"]["remaining"], 0)

    def test_bulk_delete_groups_by_filter_limit_deletes_one_batch(self):
        # self.group + 2 more = 3 active groups; a limit of 2 deletes 2, leaving 1.
        Groups.objects.create(group_name="Group Two")
        Groups.objects.create(group_name="Group Three")

        result = bulk_delete_groups_by_filter({}, limit=2, initiated_by=self.admin_user)

        self.assertEqual(len(result["data"]["deletedIds"]), 2)
        self.assertEqual(result["data"]["remaining"], 1)
        self.assertEqual(Groups.objects.filter(deleted_at__isnull=True).count(), 1)

        # A second call drains the rest; remaining hits 0.
        rest = bulk_delete_groups_by_filter({}, limit=2, initiated_by=self.admin_user)
        self.assertEqual(len(rest["data"]["deletedIds"]), 1)
        self.assertEqual(rest["data"]["remaining"], 0)
        self.assertEqual(Groups.objects.filter(deleted_at__isnull=True).count(), 0)
