"""Tests for private admin notes on user profiles.

Admin notes are visible and editable exclusively by admins. They must never be
leaked in public/student/mentor serializers or endpoints.
"""
from django.test import TestCase

from apps.admin.services.user import (
    add_users_by_role,
    bulk_delete_users_by_filter,
    bulk_update_status_by_filter,
    fetch_user_by_id,
    query_users,
    update_user,
)
from apps.audit.models import AuditLog
from apps.users.models import User
from apps.users.models.admin_scope import AdminScope
from apps.users.serializers import UserSerializer


class AdminUserNotesTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            first_name="Alice",
            last_name="Admin",
            is_staff=True,
            is_superuser=True,
        )
        AdminScope.objects.create(user=self.admin)

    def test_create_user_with_admin_notes(self):
        payload = [{
            "email": "student_with_notes@example.com",
            "firstName": "Sam",
            "lastName": "Student",
            "role": "student",
            "country": "Australia",
            "schoolName": "Sydney Grammar",
            "yearLevel": 11,
            "interests": ["Biotechnology"],
            "adminNotes": "  Requires special accommodations for exams.  ",
        }]
        result = add_users_by_role(payload)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["msg"], "User created successfully")
        self.assertIsNotNone(result[0]["data"])

        user_id = result[0]["data"]["id"]
        user = User.objects.get(id=user_id)
        self.assertEqual(user.admin_notes, "Requires special accommodations for exams.")

        fetched = fetch_user_by_id(user_id)
        self.assertEqual(fetched["adminNotes"], "Requires special accommodations for exams.")

    def test_update_user_admin_notes(self):
        user = User.objects.create_user(
            email="mentor@example.com",
            first_name="Bob",
            last_name="Mentor",
            admin_notes="Initial note.",
        )
        AdminScope.objects.create(user=user)

        update_result = update_user(
            user.id,
            {
                "role": "admin",
                "adminNotes": "Updated confidential context.",
            },
            initiated_by=self.admin,
        )
        self.assertEqual(update_result["msg"], "User updated successfully")
        self.assertEqual(update_result["data"]["adminNotes"], "Updated confidential context.")

        user.refresh_from_db()
        self.assertEqual(user.admin_notes, "Updated confidential context.")

        # Verify audit log was recorded
        audit = AuditLog.objects.filter(entity_id=user.id, action="update").last()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.before_state["adminNotes"], "Initial note.")
        self.assertEqual(audit.after_state["adminNotes"], "Updated confidential context.")

    def test_update_user_without_changing_notes_does_not_log_notes_change(self):
        user = User.objects.create_user(
            email="supervisor@example.com",
            first_name="Sara",
            last_name="Supervisor",
            admin_notes="Same note.",
        )
        AdminScope.objects.create(user=user)

        payload = {
            "role": "admin",
            "adminNotes": "Same note.",
        }
        update_user(user.id, payload, initiated_by=self.admin)
        count_before = AuditLog.objects.filter(entity_id=user.id, action="update").count()

        # Update again with identical values
        update_user(user.id, payload, initiated_by=self.admin)
        count_after = AuditLog.objects.filter(entity_id=user.id, action="update").count()

        # No change to user details -> update audit log count unchanged
        self.assertEqual(count_before, count_after)

    def test_query_users_includes_admin_notes_and_filters(self):
        user = User.objects.create_user(
            email="notable@example.com",
            first_name="Notable",
            last_name="User",
            admin_notes="DistinctiveKeyword123 in private note",
            is_active=True,
        )

        # Query all
        res = query_users(limit=50)
        items = {item["email"]: item for item in res["data"]["items"]}
        self.assertIn("notable@example.com", items)
        self.assertEqual(items["notable@example.com"]["adminNotes"], "DistinctiveKeyword123 in private note")

        # Query with search keyword matching admin notes
        search_res = query_users(search="DistinctiveKeyword123")
        search_emails = [item["email"] for item in search_res["data"]["items"]]
        self.assertIn("notable@example.com", search_emails)

        # Private notes are searchable in the list, but must not expand
        # filter-based bulk actions.
        update_result = bulk_update_status_by_filter(
            {"search": "DistinctiveKeyword123"}, False,
            initiated_by=self.admin,
        )
        self.assertEqual(update_result["data"]["updatedIds"], [])
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        delete_result = bulk_delete_users_by_filter(
            {"search": "DistinctiveKeyword123"},
            initiated_by=self.admin,
        )
        self.assertEqual(delete_result["data"]["deletedIds"], [])
        self.assertTrue(User.objects.filter(id=user.id).exists())

    def test_user_serializer_does_not_expose_admin_notes(self):
        user = User.objects.create_user(
            email="confidential@example.com",
            first_name="Secret",
            last_name="Agent",
            admin_notes="Extremely confidential admin notes",
        )
        serializer = UserSerializer(user)
        self.assertNotIn("admin_notes", serializer.data)
        self.assertNotIn("adminNotes", serializer.data)
        self.assertNotIn("Extremely confidential admin notes", str(serializer.data))
