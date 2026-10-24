"""A supervisor's CSV of students: its 1,000-student limit, and a large upload
saved in full.

The limit is checked against the registration form's rules, without saving
a thousand students, which took far longer than any other registration test;
saving is checked on a CSV of 100.
"""

from django.test import TestCase

from apps.users.models import RegistrationStudent, StudentProfile
from apps.users.registration_intake import MAX_CSV_ROWS, IntakeInput
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch


class CsvLimitTests(MultiStudentSetup, TestCase):
    def test_a_csv_of_1000_students_is_accepted_and_1001_refused(self):
        self.assertEqual(MAX_CSV_ROWS, 1000)
        at_limit = IntakeInput(data=batch("supervisor_csv", 1000))
        self.assertTrue(at_limit.is_valid(), at_limit.errors)

        response = self.post_batch(batch("supervisor_csv", 1001))
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("students", response.data["fields"])
        self.assertFalse(StudentProfile.objects.exists())

    def test_every_student_in_a_large_csv_is_saved(self):
        response = self.post_batch(batch("supervisor_csv", 100))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["student_count"], 100)
        self.assertEqual(RegistrationStudent.objects.count(), 100)
        self.assertEqual(StudentProfile.objects.count(), 100)
