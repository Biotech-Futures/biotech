from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.admin.services.match import confirm_student_assignments
from apps.groups.models import Countries, CountryStates, Groups, GroupMembership, Tracks
from apps.users.models import User


class ConfirmStudentAssignmentsTests(TestCase):
    def setUp(self):
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=self.state)
        self.group_one = Groups.objects.create(group_name="Group One", track=self.track)
        self.group_two = Groups.objects.create(group_name="Group Two", track=self.track)
        self.students = [
            User.objects.create_user(
                email=f"student{index}@example.com",
                first_name=f"Student{index}",
                last_name="Example",
                track=self.track,
                password="testpass",
            )
            for index in range(4)
        ]

    def test_confirms_camel_case_assignments_with_synthetic_group(self):
        result = confirm_student_assignments(
            {
                "assignments": [
                    {"studentId": self.students[0].id, "groupId": self.group_two.id},
                    {"studentId": self.students[1].id, "groupId": self.group_one.id},
                    {
                        "studentId": self.students[2].id,
                        "groupId": f"new-AUS-NSW-{self.students[2].id}-{self.students[3].id}",
                    },
                    {
                        "studentId": self.students[3].id,
                        "groupId": f"new-AUS-NSW-{self.students[2].id}-{self.students[3].id}",
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

    def test_invalid_assignment_payload_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            confirm_student_assignments(
                {
                    "assignments": [
                        {"studentId": self.students[0].id, "groupId": "oops"}
                    ]
                }
            )
