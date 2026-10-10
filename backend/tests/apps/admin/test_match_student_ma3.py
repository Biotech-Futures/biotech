"""MA3: automatic student matching only ever forms brand new groups.

Groups that already have members are off-limits to the matcher, no matter where
they came from (CSV import, an admin, or an earlier run). Admins can still fill
seats by hand through the groups app, which is a separate code path.
"""
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.admin.services.match import confirm_student_assignments, match_student
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership
from apps.matching_runtime.models import MatchRun
from apps.users.models import (
    AreasOfInterest, StudentProfile, User, UserInterest,
)
from apps.users.models.admin_scope import AdminScope

STUDENT_ROLE = GroupMembership.MembershipRoleChoices.STUDENT


class FormOnlyStudentMatchTests(TestCase):
    def setUp(self):
        country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=country, state_name="NSW")
        self.interest = AreasOfInterest.objects.create(interest_desc="Biotech")

        self.admin_user = User.objects.create_user(
            email="admin@example.com", first_name="Admin", password="testpass",
        )
        AdminScope.objects.create(user=self.admin_user)

        # A group with one seat taken and four free: the old join path would have
        # happily funnelled standalone students into it.
        self.formed_group = Groups.objects.create(group_name="Formed Group")
        seated = self._student("seated@example.com")
        GroupMembership.objects.create(
            user=seated, group=self.formed_group, membership_role=STUDENT_ROLE,
        )

        self.standalone = [
            self._student(f"standalone{index}@example.com") for index in range(3)
        ]

    def _student(self, email):
        user = User.objects.create_user(
            email=email, first_name="S", last_name=email.split("@")[0],
            state=self.state, password="testpass",
        )
        StudentProfile.objects.create(
            user=user, pg_first_name="P", pg_last_name="G",
            parent_guardian_flag=True, school_name="School", year_lvl="10",
        )
        UserInterest.objects.create(user=user, interest=self.interest)
        return user

    def test_no_student_is_recommended_into_a_group_with_members(self):
        result = match_student(str(self.admin_user.id))

        # Guard the guard: the run really did form groups, so the assertions
        # below are not passing on an empty list.
        self.assertTrue(result.recommendations)

        recommended_ids = [group["id"] for group in result.recommendations]
        self.assertNotIn(self.formed_group.id, recommended_ids)
        self.assertNotIn(str(self.formed_group.id), [str(i) for i in recommended_ids])
        # Every recommendation is a brand new group, never a persisted one.
        for group_id in recommended_ids:
            self.assertTrue(str(group_id).startswith("new-"), group_id)

    def test_recommended_groups_start_empty(self):
        result = match_student(str(self.admin_user.id))

        self.assertTrue(result.recommendations)
        for group in result.recommendations:
            self.assertEqual(group["existingStudents"], [])

    def test_formed_group_is_still_reported_as_having_free_seats(self):
        # Admins need to see the seats to fill them by hand, so the report keeps
        # the group even though matching will not touch it.
        result = match_student(str(self.admin_user.id))

        reported = {group["id"]: group for group in result.not_full_groups}
        self.assertIn(self.formed_group.id, reported)
        self.assertEqual(reported[self.formed_group.id]["studentCount"], 1)
        self.assertGreater(reported[self.formed_group.id]["availableSeats"], 0)

    def test_run_snapshot_records_the_form_only_strategy(self):
        match_student(str(self.admin_user.id))

        run = MatchRun.objects.get(run_type="student-match")
        self.assertEqual(run.rules_snapshot["strategy"], "form-only")
        self.assertEqual(run.rules_snapshot["studentCount"], len(self.standalone))
        self.assertIn("groupsAtRunTime", run.rules_snapshot)


class ConfirmRejectsFormedGroupsTests(TestCase):
    def setUp(self):
        self.formed_group = Groups.objects.create(group_name="Formed Group")
        self.empty_group = Groups.objects.create(group_name="Empty Group")
        self.students = [
            User.objects.create_user(
                email=f"student{index}@example.com", first_name=f"S{index}",
                last_name="Example", password="testpass",
            )
            for index in range(3)
        ]
        GroupMembership.objects.create(
            user=self.students[0], group=self.formed_group,
            membership_role=STUDENT_ROLE,
        )

    def test_assignment_into_a_formed_group_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            confirm_student_assignments({
                "assignments": [
                    {"studentId": self.students[1].id, "groupId": self.formed_group.id},
                ]
            })

        self.assertIn("Formed Group", str(caught.exception))
        self.assertFalse(
            GroupMembership.objects.filter(user=self.students[1]).exists()
        )

    def test_one_formed_target_rejects_the_whole_payload(self):
        with self.assertRaises(ValidationError):
            confirm_student_assignments({
                "assignments": [
                    {
                        "studentId": self.students[1].id,
                        "groupId": f"new-{self.students[1].id}",
                    },
                    {"studentId": self.students[2].id, "groupId": self.formed_group.id},
                ]
            })

        # Nothing was written: no new group, and neither student moved.
        self.assertEqual(Groups.objects.count(), 2)
        self.assertFalse(
            GroupMembership.objects.filter(
                user__in=self.students[1:3]
            ).exists()
        )

    def test_an_empty_existing_group_can_still_be_confirmed_into(self):
        # Only membership makes a group off-limits, so a hand-made empty group is
        # still a valid target for an admin confirming a board.
        result = confirm_student_assignments({
            "assignments": [
                {"studentId": self.students[1].id, "groupId": self.empty_group.id},
            ]
        })

        self.assertEqual(result, {"assigned_count": 1})
        self.assertEqual(
            GroupMembership.objects.get(user=self.students[1]).group_id,
            self.empty_group.id,
        )
