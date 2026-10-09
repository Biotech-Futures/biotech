"""Admin email edits keep account identity and revoke old emailed credentials."""
from unittest.mock import patch

from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.groups.models import Groups, GroupMembership
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.services.models import LoginToken, PasswordResetToken
from apps.users.models import (
    AreasOfInterest, MentorProfile, StudentProfile, StudentSupervisor,
    SupervisorProfile, User, UserInterest,
)
from apps.users.models.admin_scope import AdminScope


class AdminUserEmailTests(TestCase):
    def setUp(self):
        self.admin = self.make_user("admin", "admin@example.com")
        AdminScope.objects.create(user=self.admin)
        self.student = self.make_user("student", "student@example.com")
        self.supervisor = self.make_user("supervisor", "supervisor@example.com")
        self.supervisor_profile = SupervisorProfile.objects.create(
            user=self.supervisor, school_name="Test High",
        )
        self.profile = StudentProfile.objects.create(
            user=self.student, school_name="Test High", year_lvl="10",
            pg_first_name="Pat", pg_last_name="Parent", pg_email="parent@example.com",
            parent_guardian_flag=True, has_join_permission=True,
            joinperm_responseID="BTF-123", joinperm_granted_at=timezone.now(), supervisor=self.supervisor_profile,
        )
        StudentSupervisor.objects.create(student_user_id=self.student.pk, supervisor_user_id=self.supervisor.pk)
        self.interest = AreasOfInterest.objects.create(interest_desc="Biomedical Innovations")
        UserInterest.objects.create(user=self.student, interest=self.interest)
        self.group = Groups.objects.create(group_name="Email edit test")
        GroupMembership.objects.create(group=self.group, user=self.student, membership_role="student")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def make_user(self, role, email):
        user = User.objects.create_user(email=email, password="testpass", first_name="Test", last_name=role)
        RoleAssignmentHistory.objects.create(
            user=user, role=Roles.objects.get_or_create(role_name=role)[0], valid_from=timezone.now(),
        )
        return user

    def update(self, payload, user=None):
        return self.client.put(f"/api/v1/admin/user/{(user or self.student).pk}/", payload, format="json")

    def test_admin_changes_email_without_replacing_the_account_or_its_links(self):
        response = self.update({"email": "  New.Student@Example.COM  "})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["email"], "new.student@example.com")
        self.assertEqual(response.data["data"]["id"], self.student.pk)
        self.student.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertTrue(self.student.check_password("testpass"))
        self.assertTrue(self.profile.has_join_permission)
        self.assertEqual(self.profile.joinperm_responseID, "BTF-123")
        self.assertEqual(self.profile.supervisor_id, self.supervisor.pk)
        self.assertTrue(StudentSupervisor.objects.filter(student_user_id=self.student.pk, supervisor_user_id=self.supervisor.pk).exists())
        self.assertTrue(GroupMembership.objects.filter(user=self.student, group=self.group).exists())
        self.assertTrue(UserInterest.objects.filter(user=self.student, interest=self.interest).exists())
        audit = AuditLog.objects.get(entity_id=self.student.pk, action="update")
        self.assertEqual(audit.actor_user_id, self.admin.pk)
        self.assertEqual(audit.before_state["email"], "student@example.com")
        self.assertEqual(audit.after_state["email"], "new.student@example.com")

    def test_new_address_logs_in_and_old_address_does_not(self):
        self.assertEqual(self.update({"email": "new@example.com"}).status_code, 200)
        self.assertIsNone(authenticate(email="student@example.com", password="testpass"))
        self.assertEqual(authenticate(email="new@example.com", password="testpass").pk, self.student.pk)

    def test_old_login_and_reset_tokens_are_invalidated_only_for_changed_account(self):
        login = LoginToken.create_for_user(self.student)
        reset = PasswordResetToken.create_for_user(self.student)
        other = LoginToken.create_for_user(self.supervisor)
        self.assertEqual(self.update({"email": "new@example.com"}).status_code, 200)
        login.refresh_from_db()
        reset.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(login.used)
        self.assertTrue(reset.used)
        self.assertIsNotNone(reset.used_at)
        self.assertFalse(other.used)
        self.assertIsNone(PasswordResetToken.peek(reset.token))
        fresh = LoginToken.create_for_user(self.student)
        self.assertTrue(fresh.is_valid)

    def test_unchanged_email_keeps_live_tokens_and_creates_no_audit_edit(self):
        login = LoginToken.create_for_user(self.student)
        for payload in ({"email": " STUDENT@EXAMPLE.COM "}, {}):
            self.assertEqual(self.update(payload).status_code, 200)
        login.refresh_from_db()
        self.assertFalse(login.used)
        self.assertFalse(AuditLog.objects.filter(entity_id=self.student.pk, action="update").exists())

    def test_rejects_invalid_or_missing_email_values_without_other_edits(self):
        for value in (None, "", "  ", "invalid", "a@", 123, [], {}, "a" * 250 + "@example.com"):
            with self.subTest(value=value):
                response = self.update({"email": value, "firstName": "Changed"})
                self.assertEqual(response.status_code, 400)
                self.student.refresh_from_db()
                self.assertEqual(self.student.email, "student@example.com")
                self.assertEqual(self.student.first_name, "Test")

    def test_duplicate_address_is_rejected_case_insensitively_even_if_inactive(self):
        User.objects.create(email="Taken@Example.com", first_name="Other", last_name="User", is_active=False)
        response = self.update({"email": "taken@example.com"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["msg"], "Account email already exists")

    def test_rejects_current_pending_and_simultaneously_changed_guardian_email(self):
        self.profile.pending_pg_email = "pending@example.com"
        self.profile.save(update_fields=["pending_pg_email"])
        for payload in (
            {"email": "PARENT@example.com"},
            {"email": "pending@example.com"},
            {"email": "new@example.com", "guardianEmail": "NEW@example.com"},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.update(payload).status_code, 400)

    def test_students_supervisors_and_mentors_cannot_edit_account_emails(self):
        mentor = self.make_user("mentor", "mentor@example.com")
        for actor in (self.student, self.supervisor, mentor, None):
            with self.subTest(actor=actor):
                self.client.force_authenticate(actor)
                self.assertEqual(self.update({"email": "new@example.com"}).status_code, 403)
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "student@example.com")

    def test_failed_update_rolls_back_email_and_token_revocation(self):
        login = LoginToken.create_for_user(self.student)
        with patch("apps.admin.services.user.upsert_student_profile", side_effect=IntegrityError("conflict")):
            self.assertEqual(self.update({"email": "new@example.com"}).status_code, 400)
        self.student.refresh_from_db()
        login.refresh_from_db()
        self.assertEqual(self.student.email, "student@example.com")
        self.assertFalse(login.used)
        self.assertFalse(AuditLog.objects.filter(entity_id=self.student.pk, action="update").exists())

    def test_email_only_edits_preserve_supervisor_and_mentor_profile_details(self):
        self.assertEqual(self.update({"email": "teacher@example.com"}, self.supervisor).status_code, 200)
        self.supervisor_profile.refresh_from_db()
        self.assertEqual(self.supervisor_profile.school_name, "Test High")
        mentor = self.make_user("mentor", "mentor@example.com")
        profile = MentorProfile.objects.create(
            user=mentor, institution="University", mentor_reason="Support students", background="Research", max_group_count=0,
        )
        UserInterest.objects.create(user=mentor, interest=self.interest)
        self.assertEqual(self.update({"email": "researcher@example.com"}, mentor).status_code, 200)
        profile.refresh_from_db()
        self.assertEqual((profile.institution, profile.mentor_reason, profile.background, profile.max_group_count),
                         ("University", "Support students", "Research", 0))

    def test_admin_can_change_their_own_email_without_losing_admin_scope(self):
        self.assertEqual(self.update({"email": "new.admin@example.com"}, self.admin).status_code, 200)
        self.assertTrue(AdminScope.objects.filter(user=self.admin).exists())
