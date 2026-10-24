from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.admin.services.match import confirm_student_assignments
from apps.groups.models import GroupAutoNameUnavailable, Groups, GroupMembership
from apps.users.models import User


class ConfirmStudentAssignmentsTests(TestCase):
    def setUp(self):
        self.group_one = Groups.objects.create(group_name="Group One")
        self.group_two = Groups.objects.create(group_name="Group Two")
        self.students = [
            User.objects.create_user(
                email=f"student{index}@example.com",
                first_name=f"Student{index}",
                last_name="Example",
                password="testpass",
            )
            for index in range(4)
        ]

    def test_confirms_camel_case_assignments_with_synthetic_group(self):
        synthetic_group_id = (
            f"new-{self.students[2].id}-{self.students[3].id}"
        )
        result = confirm_student_assignments(
            {
                "assignments": [
                    {"studentId": self.students[0].id, "groupId": self.group_two.id},
                    {"studentId": self.students[1].id, "groupId": self.group_one.id},
                    {
                        "studentId": self.students[2].id,
                        "groupId": synthetic_group_id,
                    },
                    {
                        "studentId": self.students[3].id,
                        "groupId": synthetic_group_id,
                    },
                ]
            }
        )

        self.assertEqual(result, {"assigned_count": 4})
        self.assertEqual(
            GroupMembership.objects.get(user=self.students[0]).group_id,
            self.group_two.id,
        )
        self.assertEqual(
            GroupMembership.objects.get(user=self.students[1]).group_id,
            self.group_one.id,
        )
        synthetic_group_ids = set(
            GroupMembership.objects.filter(user__in=self.students[2:4]).values_list(
                "group_id",
                flat=True,
            )
        )
        self.assertEqual(len(synthetic_group_ids), 1)
        self.assertNotIn(self.group_one.id, synthetic_group_ids)
        self.assertNotIn(self.group_two.id, synthetic_group_ids)

    def test_still_accepts_snake_case_assignments(self):
        result = confirm_student_assignments(
            {
                "assignments": [
                    {
                        "student_id": self.students[0].id,
                        "group_id": self.group_one.id,
                    }
                ]
            }
        )

        self.assertEqual(result, {"assigned_count": 1})
        self.assertTrue(
            GroupMembership.objects.filter(
                user=self.students[0],
                group=self.group_one,
            ).exists()
        )

    def test_synthetic_groups_draw_from_the_shared_auto_name_series(self):
        confirm_student_assignments(
            {
                "assignments": [
                    {
                        "studentId": self.students[0].id,
                        "groupId": f"new-{self.students[0].id}",
                    },
                    {
                        "studentId": self.students[1].id,
                        "groupId": f"new-{self.students[1].id}",
                    },
                ]
            }
        )

        created = Groups.objects.exclude(
            id__in=[self.group_one.id, self.group_two.id]
        ).order_by("id")
        self.assertEqual([group.group_name for group in created], ["BTF01", "BTF02"])

    def test_synthetic_group_steps_over_a_hand_named_squatter(self):
        Groups.objects.create(group_name="BTF5")

        confirm_student_assignments(
            {
                "assignments": [
                    {
                        "studentId": self.students[0].id,
                        "groupId": f"new-{self.students[0].id}",
                    }
                ]
            }
        )

        group = Groups.objects.get(groupmembership__user=self.students[0])
        self.assertEqual(group.group_name, "BTF06")

    def test_auto_name_failure_aborts_without_dropping_memberships(self):
        GroupMembership.objects.create(
            group=self.group_one,
            user=self.students[0],
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )

        with patch.object(
            Groups, "create_auto_named", side_effect=GroupAutoNameUnavailable("BTF1"),
        ):
            with self.assertRaises(ValidationError):
                confirm_student_assignments(
                    {
                        "assignments": [
                            {
                                "studentId": self.students[0].id,
                                "groupId": f"new-{self.students[0].id}",
                            }
                        ]
                    }
                )

        # Rolled back whole: the student keeps the group they were already in.
        self.assertEqual(
            GroupMembership.objects.get(user=self.students[0]).group_id,
            self.group_one.id,
        )
        self.assertEqual(Groups.objects.count(), 2)

    def test_invalid_assignment_payload_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            confirm_student_assignments(
                {
                    "assignments": [
                        {"studentId": self.students[0].id, "groupId": "oops"}
                    ]
                }
            )

    def _in_group(self, group, *users, joined_at=None):
        for user in users:
            GroupMembership.objects.create(
                group=group, user=user, membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
                **({"joined_at": joined_at} if joined_at else {}),
            )

    def _more_students(self, count):
        return [
            User.objects.create_user(
                email=f"extra{index}@example.com", first_name=f"Extra{index}", last_name="Example",
                password="testpass",
            )
            for index in range(count)
        ]

    def _refusal(self, input_data):
        with self.assertRaises(ValidationError) as caught:
            confirm_student_assignments(input_data)
        return str(caught.exception.detail["assignments"][0])

    def test_a_group_never_goes_past_five_and_nothing_is_saved(self):
        self._in_group(self.group_one, *self._more_students(4))

        message = self._refusal({"assignments": [
            {"studentId": self.students[0].id, "groupId": self.group_one.id},
            {"studentId": self.students[1].id, "groupId": self.group_one.id},
        ]})

        self.assertEqual(message, "Group One has room for 1 more student.")
        self.assertFalse(GroupMembership.objects.filter(user__in=self.students[:2]).exists())

    def test_a_student_moving_out_frees_their_place(self):
        self._in_group(self.group_one, self.students[0], *self._more_students(4))

        confirm_student_assignments({"assignments": [
            {"studentId": self.students[0].id, "groupId": self.group_two.id},
            {"studentId": self.students[1].id, "groupId": self.group_one.id},
        ]})

        active = GroupMembership.objects.filter(group=self.group_one, left_at__isnull=True)
        self.assertEqual(active.count(), 5)
        self.assertTrue(active.filter(user=self.students[1]).exists())

    def test_a_new_group_takes_five_at_most(self):
        students = self.students + self._more_students(2)

        message = self._refusal({"assignments": [
            {"studentId": student.id, "groupId": "new-1"} for student in students
        ]})

        self.assertEqual(message, "A new group can have at most 5 students.")
        self.assertEqual(Groups.objects.count(), 2)

    def test_a_move_keeps_the_old_membership_as_history(self):
        self._in_group(self.group_one, self.students[0])

        confirm_student_assignments(
            {"assignments": [{"studentId": self.students[0].id, "groupId": self.group_two.id}]}
        )

        old = GroupMembership.objects.get(user=self.students[0], group=self.group_one)
        self.assertIsNotNone(old.left_at)
        self.assertTrue(
            GroupMembership.objects.filter(
                user=self.students[0], group=self.group_two, left_at__isnull=True,
            ).exists()
        )

    def test_a_student_already_in_the_group_is_left_as_they_were(self):
        joined = timezone.now() - timedelta(days=30)
        self._in_group(self.group_one, self.students[0], joined_at=joined)

        result = confirm_student_assignments(
            {"assignments": [{"studentId": self.students[0].id, "groupId": self.group_one.id}]}
        )

        self.assertEqual(result, {"assigned_count": 1})
        membership = GroupMembership.objects.get(user=self.students[0])
        self.assertEqual(membership.joined_at, joined)
        self.assertIsNone(membership.left_at)

    def test_only_ungrouped_refuses_a_student_who_has_since_joined_a_group(self):
        self._in_group(self.group_one, self.students[0])

        message = self._refusal({
            "onlyUngrouped": True,
            "assignments": [
                {"studentId": self.students[0].id, "groupId": self.group_two.id},
                {"studentId": self.students[1].id, "groupId": self.group_two.id},
            ],
        })

        self.assertEqual(
            message, "Since this page loaded, Student0 Example has joined Group One. Reload and try again.",
        )
        self.assertEqual(GroupMembership.objects.get(user=self.students[0]).group_id, self.group_one.id)
        self.assertFalse(GroupMembership.objects.filter(user=self.students[1]).exists())
