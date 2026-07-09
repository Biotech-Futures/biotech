"""Tests for admin mentor match service."""
from django.test import TestCase
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.admin.services.mentor_match import (
    match_mentor, get_mentors, get_unmatched_groups, get_matched_groups,
    confirm_mentor_assignments, replace_mentor, bulk_replace_inactive_mentors,
    unassign_mentors, recommend_mentors_for_group,
)
from apps.admin.services.match import recommend_students_for_group
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership
from apps.users.models import (
    MentorProfile, StudentProfile, User, AreasOfInterest, UserInterest,
)
from apps.users.models.admin_scope import AdminScope
from apps.matching_runtime.models import MatchRun

STUDENT_ROLE = GroupMembership.MembershipRoleChoices.STUDENT
MENTOR_ROLE = GroupMembership.MembershipRoleChoices.MENTOR


class MentorMatchServiceTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=country, state_name="NSW")

        self.admin_user = User.objects.create_user(
            email="admin@example.com", first_name="Admin", password="testpass",
        )
        AdminScope.objects.create(user=self.admin_user)

        self.mentor = User.objects.create_user(
            email="mentor@example.com", first_name="Mina", last_name="Mentor",
            state=self.state, password="testpass", is_active=True,
        )
        MentorProfile.objects.create(
            user=self.mentor, institution="UNSW", mentor_reason="Testing", max_group_count=3,
        )

        self.group = Groups.objects.create(group_name="Group A")
        self.student = User.objects.create_user(
            email="student@example.com", first_name="Stud", last_name="Ent",
            state=self.state, password="testpass",
        )
        StudentProfile.objects.create(
            user=self.student, pg_first_name="P", pg_last_name="E",
            parent_guardian_flag=True, school_name="School", year_lvl="10",
        )
        GroupMembership.objects.create(
            user=self.student, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

    def test_match_mentor_returns_empty_when_no_groups_without_mentor(self):
        GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = match_mentor(str(self.admin_user.id))
        self.assertEqual(result, [])

    def test_get_unmatched_groups(self):
        result = get_unmatched_groups(requesting_user=self.admin_user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["groupName"], "Group A")

    def test_get_unmatched_groups_empty_when_all_matched(self):
        GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = get_unmatched_groups(requesting_user=self.admin_user)
        self.assertEqual(result, [])

    def test_get_matched_groups(self):
        GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = get_matched_groups(requesting_user=self.admin_user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["groupName"], "Group A")
        self.assertEqual(result[0]["mentor"]["name"], "Mina Mentor")

    def test_get_matched_groups_empty_when_unmatched(self):
        result = get_matched_groups(requesting_user=self.admin_user)
        self.assertEqual(result, [])

    def test_get_mentors(self):
        result = get_mentors(requesting_user=self.admin_user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["email"], "mentor@example.com")

    def test_confirm_mentor_assignments_simple(self):
        result = confirm_mentor_assignments({
            "assignments": [{"groupId": self.group.id, "mentorUserId": self.mentor.id}],
        })
        self.assertEqual(result, {"confirmedCount": 1})
        self.assertTrue(
            GroupMembership.objects.filter(
                group=self.group, user=self.mentor,
                left_at__isnull=True,
            ).exists()
        )

    def test_confirm_mentor_assignments_empty(self):
        result = confirm_mentor_assignments({"assignments": []})
        self.assertEqual(result, {"confirmedCount": 0})

    def test_confirm_mentor_assignments_raises_for_non_mentor(self):
        non_mentor = User.objects.create_user(
            email="non-mentor@example.com", first_name="Non", password="testpass",
        )
        with self.assertRaises(ValidationError):
            confirm_mentor_assignments({
                "assignments": [{"groupId": self.group.id, "mentorUserId": non_mentor.id}],
            })

    def test_replace_mentor(self):
        new_mentor = User.objects.create_user(
            email="new@example.com", first_name="New", last_name="Mentor",
            state=self.state, password="testpass", is_active=True,
        )
        MentorProfile.objects.create(
            user=new_mentor, institution="UAT", mentor_reason="Volunteer", max_group_count=3,
        )
        membership = GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = replace_mentor({
            "membershipId": membership.id,
            "groupId": self.group.id,
            "newMentorUserId": new_mentor.id,
        })
        self.assertEqual(result, {"replaced": 1})
        self.assertTrue(
            GroupMembership.objects.filter(group=self.group, user=new_mentor, left_at__isnull=True).exists()
        )

    def test_replace_mentor_raises_for_non_mentor(self):
        membership = GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        non_mentor = User.objects.create_user(
            email="non@example.com", first_name="Non", password="testpass",
        )
        with self.assertRaises(ValidationError):
            replace_mentor({
                "membershipId": membership.id,
                "groupId": self.group.id,
                "newMentorUserId": non_mentor.id,
            })

    def test_bulk_replace_inactive_mentors(self):
        GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        self.mentor.deactivate()
        result = bulk_replace_inactive_mentors()
        self.assertEqual(result, {"removedCount": 1})

    def test_bulk_replace_inactive_mentors_none(self):
        result = bulk_replace_inactive_mentors()
        self.assertEqual(result, {"removedCount": 0})

    def test_unassign_mentors(self):
        GroupMembership.objects.create(
            user=self.mentor, group=self.group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = unassign_mentors([self.group.id])
        self.assertEqual(result, {"unassignedCount": 1})
        # The membership should still exist (soft unassign via left_at)
        gm = GroupMembership.objects.get(group=self.group, user=self.mentor)
        self.assertIsNotNone(gm.left_at)

    def test_unassign_mentors_none(self):
        result = unassign_mentors([9999])
        self.assertEqual(result, {"unassignedCount": 0})

    def test_match_mentor_saves_run(self):
        existing_mentor_group = Groups.objects.create(group_name="With Mentor")
        GroupMembership.objects.create(
            user=self.mentor, group=existing_mentor_group,
            membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
        )
        result = match_mentor(str(self.admin_user.id))
        self.assertTrue(MatchRun.objects.filter(run_type="mentor-match").exists())


class RecommendReplacementTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=country, state_name="NSW")
        self.interest = AreasOfInterest.objects.create(interest_desc="Biotech")

        self.group = Groups.objects.create(group_name="Group A")
        member = self._student("member@example.com")
        UserInterest.objects.create(user=member, interest=self.interest)
        GroupMembership.objects.create(
            user=member, group=self.group, membership_role=STUDENT_ROLE
        )
        self.current_mentor = self._mentor("mentor@example.com")
        GroupMembership.objects.create(
            user=self.current_mentor, group=self.group, membership_role=MENTOR_ROLE
        )

    def _student(self, email):
        user = User.objects.create_user(
            email=email, first_name="S", last_name=email[:4],
            state=self.state, password="x",
        )
        StudentProfile.objects.create(
            user=user, pg_first_name="P", pg_last_name="G",
            parent_guardian_flag=True, school_name="School", year_lvl="10",
        )
        return user

    def _mentor(self, email):
        user = User.objects.create_user(
            email=email, first_name="M", last_name=email[:4],
            state=self.state, is_active=True, password="x",
        )
        MentorProfile.objects.create(
            user=user, institution="UNSW", mentor_reason="Help", max_group_count=3,
        )
        return user

    def test_recommend_mentors_excludes_current_mentor(self):
        other = self._mentor("other@example.com")
        result = recommend_mentors_for_group(self.group.id)
        ids = [s["mentorUserId"] for s in result["data"]["suggestions"]]
        self.assertIn(other.id, ids)
        self.assertNotIn(self.current_mentor.id, ids)

    def test_recommend_mentors_group_not_found(self):
        self.assertIsNone(recommend_mentors_for_group(999999)["data"])

    def test_recommend_students_requires_shared_interest(self):
        sharer = self._student("cand1@example.com")
        UserInterest.objects.create(user=sharer, interest=self.interest)
        self._student("cand2@example.com")  # no shared interest → not eligible
        result = recommend_students_for_group(self.group.id)
        ids = [s["studentUserId"] for s in result["data"]["suggestions"]]
        self.assertIn(sharer.id, ids)
        self.assertEqual(len(ids), 1)

    def test_recommend_students_group_not_found(self):
        self.assertIsNone(recommend_students_for_group(999999)["data"])
