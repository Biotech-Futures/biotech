"""
Tests for Spec §2.6: mentor capacity guardrails.

Covers two related rules:
  - ``upsert_mentor_profile`` / ``set_mentor_max_group_count`` cannot lower
    a mentor's ``maxGroupCount`` below their current assigned group count.
  - ``confirm_mentor_assignments`` cannot push a mentor beyond their
    configured ``maxGroupCount``.
"""

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.admin.services.mentor import (
    count_current_assigned_groups,
    set_mentor_max_group_count,
    validate_max_group_count_against_assigned,
)
from apps.admin.services.mentor_match import confirm_mentor_assignments
from apps.admin.services.user import upsert_mentor_profile
from apps.groups.models import (
    Countries,
    CountryStates,
    Groups,
    GroupMembership,
    Tracks,
)
from apps.users.models import MentorProfile, User


def _make_mentor(email: str, track, first_name: str = "Mina", max_groups: int = 3) -> User:
    user = User.objects.create_user(
        email=email,
        first_name=first_name,
        last_name="Mentor",
        track=track,
        password="testpass",
    )
    MentorProfile.objects.create(
        user=user,
        institution="UNSW",
        mentor_reason="Testing",
        max_group_count=max_groups,
    )
    return user


def _assign_mentor(mentor: User, group: Groups) -> GroupMembership:
    return GroupMembership.objects.create(
        group=group,
        user=mentor,
        membership_role=GroupMembership.MembershipRoleChoices.MENTOR,
    )


class MentorMaxGroupCountGuardrailTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=state)
        self.mentor = _make_mentor("m1@example.com", self.track, max_groups=3)
        self.group_a = Groups.objects.create(group_name="Group A", track=self.track)
        self.group_b = Groups.objects.create(group_name="Group B", track=self.track)
        _assign_mentor(self.mentor, self.group_a)
        _assign_mentor(self.mentor, self.group_b)

    def test_count_current_assigned_groups_only_counts_active_memberships(self):
        self.assertEqual(count_current_assigned_groups(self.mentor.id), 2)

        # Closed memberships should not be counted.
        closed_group = Groups.objects.create(group_name="Closed", track=self.track)
        membership = _assign_mentor(self.mentor, closed_group)
        membership.left_at = membership.joined_at
        membership.save(update_fields=["left_at"])

        self.assertEqual(count_current_assigned_groups(self.mentor.id), 2)

    def test_validate_rejects_value_below_current_assigned_count(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_max_group_count_against_assigned(self.mentor.id, 1)
        detail = ctx.exception.detail
        self.assertIn("mentorMaxGroupCount", detail)
        self.assertEqual(int(detail["currentAssignedCount"]), 2)

    def test_validate_accepts_value_equal_to_current_assigned_count(self):
        result = validate_max_group_count_against_assigned(self.mentor.id, 2)
        self.assertEqual(result, 2)

    def test_validate_rejects_negative_values(self):
        with self.assertRaises(ValidationError):
            validate_max_group_count_against_assigned(self.mentor.id, -1)

    def test_validate_rejects_non_integer_input(self):
        with self.assertRaises(ValidationError):
            validate_max_group_count_against_assigned(self.mentor.id, "abc")

    def test_set_mentor_max_group_count_updates_profile_on_valid_value(self):
        result = set_mentor_max_group_count(self.mentor.id, 5)
        self.assertEqual(result["maxGroupCount"], 5)
        self.assertEqual(result["currentAssignedCount"], 2)
        self.assertEqual(result["remainingCapacity"], 3)
        self.assertEqual(
            MentorProfile.objects.get(user_id=self.mentor.id).max_group_count,
            5,
        )

    def test_set_mentor_max_group_count_rejects_below_current_load(self):
        with self.assertRaises(ValidationError):
            set_mentor_max_group_count(self.mentor.id, 1)
        # Unchanged in DB.
        self.assertEqual(
            MentorProfile.objects.get(user_id=self.mentor.id).max_group_count,
            3,
        )

    def test_upsert_mentor_profile_rejects_below_current_load(self):
        with self.assertRaises(ValidationError):
            upsert_mentor_profile(
                user_id=self.mentor.id,
                institution="UNSW",
                mentor_reason="Testing",
                max_group_count=1,
            )

    def test_upsert_mentor_profile_allows_raising_cap(self):
        upsert_mentor_profile(
            user_id=self.mentor.id,
            institution="UNSW",
            mentor_reason="Testing",
            max_group_count=4,
        )
        self.assertEqual(
            MentorProfile.objects.get(user_id=self.mentor.id).max_group_count,
            4,
        )


class ConfirmMentorAssignmentsCapacityTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        state = CountryStates.objects.create(country=country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=state)
        # Mentor with capacity 2 already assigned to one group.
        self.mentor = _make_mentor("m1@example.com", self.track, max_groups=2)
        self.existing_group = Groups.objects.create(
            group_name="Existing", track=self.track,
        )
        _assign_mentor(self.mentor, self.existing_group)
        self.empty_group_one = Groups.objects.create(
            group_name="Empty One", track=self.track,
        )
        self.empty_group_two = Groups.objects.create(
            group_name="Empty Two", track=self.track,
        )

    def test_rejects_confirm_that_would_exceed_capacity(self):
        # Mentor has 1 existing assignment + capacity 2. Asking to take 2 new
        # groups (without replacing existing) would push them to 3 active groups.
        with self.assertRaises(ValidationError) as ctx:
            confirm_mentor_assignments({
                "assignments": [
                    {"groupId": self.empty_group_one.id, "mentorUserId": self.mentor.id},
                    {"groupId": self.empty_group_two.id, "mentorUserId": self.mentor.id},
                ],
            })
        detail = ctx.exception.detail
        self.assertIn("assignments", detail)
        over = detail["assignments"]["overCapacity"]
        self.assertEqual(len(over), 1)
        self.assertEqual(int(over[0]["maxGroupCount"]), 2)
        self.assertEqual(int(over[0]["wouldAssign"]), 3)
        # No memberships were created.
        self.assertFalse(
            GroupMembership.objects.filter(
                user_id=self.mentor.id,
                group_id__in=[self.empty_group_one.id, self.empty_group_two.id],
                left_at__isnull=True,
            ).exists()
        )

    def test_allows_confirm_that_replaces_existing_assignment(self):
        # Reassigning the existing_group to a NEW empty group keeps mentor at 2.
        # Mentor already on existing_group; confirming them on empty_group_one
        # replaces nothing for them (they aren't on empty_group_one), so it
        # would be 1 existing + 1 new = 2 → exactly at the cap.
        result = confirm_mentor_assignments({
            "assignments": [
                {"groupId": self.empty_group_one.id, "mentorUserId": self.mentor.id},
            ],
        })
        self.assertEqual(result["confirmedCount"], 1)
        self.assertTrue(
            GroupMembership.objects.filter(
                user_id=self.mentor.id,
                group_id=self.empty_group_one.id,
                left_at__isnull=True,
            ).exists()
        )

    def test_reassigning_same_groups_does_not_double_count(self):
        # When the confirm targets the group the mentor is already on, the
        # existing membership is replaced by a new one, so the count stays 1.
        result = confirm_mentor_assignments({
            "assignments": [
                {"groupId": self.existing_group.id, "mentorUserId": self.mentor.id},
            ],
        })
        self.assertEqual(result["confirmedCount"], 1)
        active_memberships = GroupMembership.objects.filter(
            user_id=self.mentor.id,
            left_at__isnull=True,
        )
        self.assertEqual(active_memberships.count(), 1)

    def test_rejects_when_mentor_profile_missing(self):
        non_mentor = User.objects.create_user(
            email="not-a-mentor@example.com",
            first_name="Nora",
            last_name="Student",
            track=self.track,
            password="testpass",
        )
        with self.assertRaises(ValidationError) as ctx:
            confirm_mentor_assignments({
                "assignments": [
                    {"groupId": self.empty_group_one.id, "mentorUserId": non_mentor.id},
                ],
            })
        self.assertIn("missingMentorProfiles", ctx.exception.detail["assignments"])
