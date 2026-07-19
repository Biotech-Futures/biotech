from unittest.mock import patch

from django.test import TestCase
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
        self.assertEqual([group.group_name for group in created], ["BTF1", "BTF2"])

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
        self.assertEqual(group.group_name, "BTF6")

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
