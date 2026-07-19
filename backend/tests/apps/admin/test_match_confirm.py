from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.admin.services.match import confirm_student_assignments
from apps.groups.models import Groups, GroupMembership
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

    def test_synthetic_group_name_collision_aborts_without_dropping_memberships(self):
        # Hand-name a group into the BTF_ slot the synthetic group would claim; the
        # probe row consumes a pk itself, so the next insert lands at probe + 2.
        GroupMembership.objects.create(
            group=self.group_one,
            user=self.students[0],
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        probe_id = Groups.objects.create(group_name="collision-probe").id
        Groups.objects.create(group_name=f"BTF_{probe_id + 2:04d}")

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

        # Rolled back whole: the student keeps the group they were already in and
        # no orphan placeholder row survives.
        self.assertEqual(
            GroupMembership.objects.get(user=self.students[0]).group_id,
            self.group_one.id,
        )
        self.assertFalse(Groups.objects.filter(group_name__startswith="BTF_new-").exists())

    def test_invalid_assignment_payload_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            confirm_student_assignments(
                {
                    "assignments": [
                        {"studentId": self.students[0].id, "groupId": "oops"}
                    ]
                }
            )
