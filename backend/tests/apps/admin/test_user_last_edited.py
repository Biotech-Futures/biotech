"""Who last edited a user, as the admin user pages show it: the newest change
anyone made to their details, an admin, the user themselves or their
supervisor. Emails and other things the platform does aren't edits."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.admin.services.user import fetch_user_by_id, query_users, update_user
from apps.audit.models import AuditLog
from apps.audit.services import log_audit_event
from apps.common.role_names import ROLE_STUDENT
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import StudentProfile, User
from apps.users.models.admin_scope import AdminScope

CHANGE = {"firstName": "Chen", "lastName": "Lee", "role": "admin", "interests": [], "joinPermissionReceived": False}


class LastEditedTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="ada@example.com", first_name="Ada", last_name="Admin")
        AdminScope.objects.create(user=self.admin)
        self.user = User.objects.create_user(email="chen@example.com", first_name="Chen", last_name="Supervisor")

    def test_an_admin_edit_says_who_made_it(self):
        self.assertIsNone(fetch_user_by_id(self.user.id)["lastEditedBy"])

        result = update_user(self.user.id, CHANGE, initiated_by=self.admin)

        self.assertEqual(result["data"]["lastEditedBy"], "Ada Admin")
        self.assertIsNotNone(result["data"]["lastEditedAt"])
        self.assertTrue(AuditLog.objects.filter(entity_id=self.user.id, action="update").exists())

    def test_saving_without_changes_is_not_an_edit(self):
        update_user(self.user.id, CHANGE, initiated_by=self.admin)
        update_user(self.user.id, CHANGE, initiated_by=self.admin)

        self.assertEqual(AuditLog.objects.filter(entity_id=self.user.id, action="update").count(), 1)

    def test_the_users_list_shows_the_last_editor(self):
        update_user(self.user.id, CHANGE, initiated_by=self.admin)

        items = {item["id"]: item for item in query_users(limit=50)["data"]["items"]}

        self.assertEqual(items[self.user.id]["lastEditedBy"], "Ada Admin")
        self.assertIsNone(items[self.admin.id]["lastEditedBy"])

    def test_the_newest_edit_wins_and_emails_are_not_edits(self):
        update_user(self.user.id, CHANGE, initiated_by=self.admin)
        other = User.objects.create_user(email="bo@example.com", first_name="Bo", last_name="Brown")
        log_audit_event(actor=other, entity_type="user", entity_id=self.user.id, action="status_change")
        # Sending the consent email changes nothing about the user.
        log_audit_event(actor=self.admin, entity_type="user", entity_id=self.user.id, action="guardian_consent_request")

        self.assertEqual(fetch_user_by_id(self.user.id)["lastEditedBy"], "Bo Brown")

    def test_a_students_own_change_counts(self):
        student = User.objects.create_user(
            email="amy@example.com", first_name="Amy", last_name="Chen", account_status=User.AccountStatus.ACTIVE,
        )
        RoleAssignmentHistory.objects.create(
            user=student, role=Roles.objects.get_or_create(role_name=ROLE_STUDENT)[0],
            valid_from=timezone.now() - timedelta(days=1),
        )
        StudentProfile.objects.create(
            user=student, pg_first_name="Pat", pg_last_name="Parent", pg_email="pat@example.com",
            parent_guardian_flag=True, school_name="Test High", year_lvl="10",
        )
        client = APIClient()
        client.force_authenticate(student)

        client.put(
            reverse("me-guardian"),
            {"first_name": "Robin", "last_name": "Carer", "email": "robin@example.com"},
            format="json",
        )

        self.assertEqual(fetch_user_by_id(student.id)["lastEditedBy"], "Amy Chen")
