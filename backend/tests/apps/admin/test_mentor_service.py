"""Tests for admin mentor service."""
from django.test import TestCase

from apps.admin.services.mentor import get_mentor_list, set_mentor_active
from apps.audit.models import AuditLog
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership
from apps.users.models import MentorProfile, User
from apps.users.models.admin_scope import AdminScope


class MentorServiceTests(TestCase):
    def setUp(self):
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.admin_user = User.objects.create_user(
            email="admin@example.com", first_name="Admin", password="testpass",
        )
        AdminScope.objects.create(user=self.admin_user)
        self.mentor = User.objects.create_user(
            email="mentor1@example.com",
            first_name="Mina",
            last_name="Mentor",
            country=self.country,
            state=self.state,
            password="testpass",
            is_active=True,
        )
        MentorProfile.objects.create(
            user=self.mentor,
            institution="UNSW",
            mentor_reason="Testing",
            max_group_count=3,
            background="Science",
        )

    def test_get_mentor_list_returns_empty_when_no_mentors(self):
        MentorProfile.objects.all().delete()
        result = get_mentor_list(requesting_user=self.admin_user)
        self.assertEqual(result, [])

    def test_get_mentor_list_returns_mentor_dict(self):
        result = get_mentor_list(requesting_user=self.admin_user)
        self.assertEqual(len(result), 1)
        mentor = result[0]
        self.assertEqual(mentor["firstName"], "Mina")
        self.assertEqual(mentor["lastName"], "Mentor")
        self.assertEqual(mentor["email"], "mentor1@example.com")
        self.assertEqual(mentor["institution"], "UNSW")
        self.assertEqual(mentor["countryName"], "Australia")
        self.assertEqual(mentor["utcOffsetHours"], 0.0)
        self.assertEqual(mentor["maxGroupCount"], 3)
        self.assertEqual(mentor["currentAssignedCount"], 0)
        self.assertEqual(mentor["remainingCapacity"], 3)
        self.assertTrue(mentor["isActive"])
        self.assertEqual(mentor["accountStatus"], "active")

    def test_get_mentor_list_reports_account_status(self):
        self.mentor.is_active = False
        self.mentor.account_status = User.AccountStatus.INVITED
        self.mentor.save(update_fields=["is_active", "account_status"])

        mentor = get_mentor_list(requesting_user=self.admin_user)[0]

        self.assertFalse(mentor["isActive"])
        self.assertEqual(mentor["accountStatus"], "invited")

    def test_get_mentor_list_counts_assigned_groups(self):
        group = Groups.objects.create(group_name="Group A")
        GroupMembership.objects.create(
            user=self.mentor,
            group=group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = get_mentor_list(requesting_user=self.admin_user)
        self.assertEqual(result[0]["currentAssignedCount"], 1)
        self.assertEqual(result[0]["remainingCapacity"], 2)

    def test_get_mentor_list_handles_mentor_without_geography(self):
        mentor_no_state = User.objects.create_user(
            email="mentor2@example.com", first_name="No", last_name="State",
            password="testpass",
        )
        MentorProfile.objects.create(
            user=mentor_no_state, institution="UAT", mentor_reason="Test",
        )
        result = get_mentor_list(requesting_user=self.admin_user)
        by_email = {m["email"]: m for m in result}
        self.assertIn("mentor2@example.com", by_email)
        self.assertIsNone(by_email["mentor2@example.com"]["countryName"])

    def test_set_mentor_active_deactivates(self):
        set_mentor_active(self.mentor.id, False)
        self.mentor.refresh_from_db()
        self.assertFalse(self.mentor.is_active)

    def test_set_mentor_active_activates(self):
        self.mentor.is_active = False
        self.mentor.save()
        set_mentor_active(self.mentor.id, True)
        self.mentor.refresh_from_db()
        self.assertTrue(self.mentor.is_active)

    def _pending_mentor(self):
        user = User.objects.create_user(email="applicant@example.com", first_name="Ari", last_name="Applicant")
        MentorProfile.objects.create(user=user, institution="UNSW", mentor_reason="Testing", max_group_count=2)
        return user

    def test_activating_a_pending_mentor_stamps_activated_at_and_audits(self):
        applicant = self._pending_mentor()
        self.assertEqual((applicant.account_status, applicant.is_active, applicant.activated_at), ("pending", False, None))

        result = set_mentor_active(applicant.id, True, initiated_by=self.admin_user)

        self.assertEqual(result, {"mentorId": applicant.id, "isActive": True})
        applicant.refresh_from_db()
        self.assertEqual((applicant.account_status, applicant.is_active), ("active", True))
        self.assertIsNotNone(applicant.activated_at)
        entry = AuditLog.objects.get(entity_type="user", entity_id=applicant.id, action="status_change")
        self.assertEqual(entry.actor_user, self.admin_user)
        self.assertEqual(entry.before_state, {"isActive": False, "accountStatus": "pending"})
        self.assertEqual(entry.after_state, {"isActive": True, "accountStatus": "active"})

    def test_reactivating_keeps_the_first_activated_at(self):
        applicant = self._pending_mentor()
        set_mentor_active(applicant.id, True)
        applicant.refresh_from_db()
        first = applicant.activated_at

        set_mentor_active(applicant.id, False)
        set_mentor_active(applicant.id, True)

        applicant.refresh_from_db()
        self.assertEqual((applicant.account_status, applicant.is_active), ("active", True))
        self.assertEqual(applicant.activated_at, first)

    def test_deactivating_leaves_activated_at_alone(self):
        applicant = self._pending_mentor()
        set_mentor_active(applicant.id, True)
        applicant.refresh_from_db()
        first = applicant.activated_at

        result = set_mentor_active(applicant.id, False)

        self.assertEqual(result, {"mentorId": applicant.id, "isActive": False})
        applicant.refresh_from_db()
        self.assertEqual((applicant.account_status, applicant.is_active), ("deactivated", False))
        self.assertEqual(applicant.activated_at, first)
