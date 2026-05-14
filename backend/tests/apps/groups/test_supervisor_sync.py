"""Tests for the supervisor membership sync service.

When a student joins a group, their supervisor should automatically get an
active SUPERVISOR `GroupMembership` row. When the last supervisee leaves
the group, the supervisor's row is soft-removed via `left_at`. Multiple
supervisees in the same group ref-count: removing one keeps the supervisor
present as long as another supervisee remains.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.groups.services import (
    sync_supervisor_memberships,
    sync_supervisor_memberships_for_student,
)
from apps.users.models import AdminScope, StudentProfile, SupervisorProfile

User = get_user_model()


class _SupervisorWorld:
    """Two groups, one supervisor with two supervisees (initially both in
    group A) and one unrelated student. Built once per test method."""

    def _build(self):
        country = Countries.objects.create(country_name="AU-S")
        state = CountryStates.objects.create(country=country, state_name="VIC-S")
        self.track = Tracks.objects.create(track_name="VIC-S-01", state=state)
        self.group_a = Groups.objects.create(group_name="S-Group-A", track=self.track)
        self.group_b = Groups.objects.create(group_name="S-Group-B", track=self.track)

        self.supervisor = User.objects.create_user(email="sup@s.com", password="pw")
        self.student_x = User.objects.create_user(email="sx@s.com", password="pw")
        self.student_y = User.objects.create_user(email="sy@s.com", password="pw")
        self.unrelated_student = User.objects.create_user(email="un@s.com", password="pw")

        sup_profile = SupervisorProfile.objects.create(user=self.supervisor, school_name="S")
        StudentProfile.objects.create(
            user=self.student_x, pg_first_name="P", pg_last_name="G",
            school_name="School", year_lvl="9", supervisor=sup_profile,
        )
        StudentProfile.objects.create(
            user=self.student_y, pg_first_name="P", pg_last_name="G",
            school_name="School", year_lvl="9", supervisor=sup_profile,
        )
        StudentProfile.objects.create(
            user=self.unrelated_student, pg_first_name="P", pg_last_name="G",
            school_name="School", year_lvl="9",  # no supervisor
        )

    def _student_join(self, user, group):
        return GroupMembership.objects.create(
            group=group, user=user,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

    def _student_leave(self, membership):
        membership.left_at = timezone.now()
        membership.save(update_fields=["left_at"])

    def _supervisor_active_group_ids(self):
        return sorted(
            GroupMembership.objects.filter(
                user=self.supervisor,
                membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR,
                left_at__isnull=True,
            ).values_list("group_id", flat=True)
        )


class SupervisorMembershipSyncTests(_SupervisorWorld, TestCase):

    def setUp(self):
        self._build()

    def test_sync_creates_supervisor_row_when_supervisee_joins(self):
        self._student_join(self.student_x, self.group_a)
        sync_supervisor_memberships_for_student(self.student_x.id)
        self.assertEqual(self._supervisor_active_group_ids(), [self.group_a.id])

    def test_sync_is_idempotent(self):
        self._student_join(self.student_x, self.group_a)
        sync_supervisor_memberships_for_student(self.student_x.id)
        sync_supervisor_memberships_for_student(self.student_x.id)
        sync_supervisor_memberships_for_student(self.student_x.id)
        # Only one active row
        self.assertEqual(
            GroupMembership.objects.filter(
                user=self.supervisor,
                membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR,
                left_at__isnull=True,
            ).count(),
            1,
        )

    def test_supervisor_present_in_each_supervisee_group(self):
        self._student_join(self.student_x, self.group_a)
        self._student_join(self.student_y, self.group_b)
        sync_supervisor_memberships(self.supervisor.id)
        self.assertEqual(
            self._supervisor_active_group_ids(), [self.group_a.id, self.group_b.id],
        )

    def test_ref_count_keeps_supervisor_while_any_supervisee_remains(self):
        m_x = self._student_join(self.student_x, self.group_a)
        self._student_join(self.student_y, self.group_a)
        sync_supervisor_memberships(self.supervisor.id)
        self.assertEqual(self._supervisor_active_group_ids(), [self.group_a.id])

        # Remove one supervisee; the other still in group_a -> supervisor stays.
        self._student_leave(m_x)
        sync_supervisor_memberships_for_student(self.student_x.id)
        self.assertEqual(self._supervisor_active_group_ids(), [self.group_a.id])

    def test_supervisor_removed_when_last_supervisee_leaves(self):
        m_x = self._student_join(self.student_x, self.group_a)
        sync_supervisor_memberships_for_student(self.student_x.id)
        self.assertEqual(self._supervisor_active_group_ids(), [self.group_a.id])

        self._student_leave(m_x)
        sync_supervisor_memberships_for_student(self.student_x.id)
        self.assertEqual(self._supervisor_active_group_ids(), [])

    def test_unrelated_student_does_not_create_supervisor_row(self):
        self._student_join(self.unrelated_student, self.group_a)
        sync_supervisor_memberships_for_student(self.unrelated_student.id)
        self.assertEqual(self._supervisor_active_group_ids(), [])

    def test_student_without_profile_is_noop(self):
        # Some users might not have a StudentProfile yet (edge case).
        loose_user = User.objects.create_user(email="loose@s.com", password="pw")
        self._student_join(loose_user, self.group_a)
        # Should not raise even though no StudentProfile exists.
        sync_supervisor_memberships_for_student(loose_user.id)
        self.assertEqual(self._supervisor_active_group_ids(), [])

    def test_sync_reuses_existing_active_row(self):
        # Pre-existing active row -- sync should not create a duplicate or
        # roll a new one. The original row stays intact.
        existing = GroupMembership.objects.create(
            group=self.group_a, user=self.supervisor,
            membership_role=GroupMembership.MembershipRoleChoices.SUPERVISOR,
        )
        self._student_join(self.student_x, self.group_a)
        sync_supervisor_memberships(self.supervisor.id)
        rows = list(
            GroupMembership.objects.filter(
                user=self.supervisor, group=self.group_a, left_at__isnull=True,
            )
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, existing.id)


class SupervisorMembershipViewIntegrationTests(_SupervisorWorld, TestCase):
    """Verify the sync runs from the GroupViewSet add/remove paths."""

    def setUp(self):
        self._build()
        self.admin = User.objects.create_user(email="admin@s.com", password="pw")
        AdminScope.objects.create(user=self.admin, track=self.track)
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_add_members_action_triggers_sync(self):
        url = f"/groups/groups/{self.group_a.id}/add-members/"
        r = self.client.post(url, {"user_ids": [self.student_x.id]}, format="json")
        self.assertIn(r.status_code, (200, 201))
        self.assertEqual(self._supervisor_active_group_ids(), [self.group_a.id])

    def test_remove_members_action_triggers_sync(self):
        self._student_join(self.student_x, self.group_a)
        sync_supervisor_memberships_for_student(self.student_x.id)
        url = f"/groups/groups/{self.group_a.id}/remove-members/"
        r = self.client.post(url, {"user_ids": [self.student_x.id]}, format="json")
        self.assertIn(r.status_code, (200, 204))
        self.assertEqual(self._supervisor_active_group_ids(), [])
