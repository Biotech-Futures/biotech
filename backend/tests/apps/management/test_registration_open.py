"""Management's Registration switch: open by default, readable by anyone,
changed by admins only; while closed, students can't register themselves."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.management.models import PublicRegistrationSetting
from apps.users.models import AdminScope, StudentProfile, User
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch

URL = "/api/v1/management/registration-open/"


class RegistrationOpenTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(email="admin-open@test.com", password="pw12345!")
        AdminScope.objects.create(user=self.admin)
        self.member = User.objects.create_user(email="member-open@test.com", password="pw12345!")

    def test_open_until_an_admin_closes_it(self):
        self.assertEqual(self.client.get(URL).json(), {"open": True})
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.put(URL, {"open": False}, format="json").json(), {"open": False})
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL).json(), {"open": False})

    def test_only_admins_change_it(self):
        self.assertIn(self.client.put(URL, {"open": False}, format="json").status_code, (401, 403))
        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.put(URL, {"open": False}, format="json").status_code, 403)

    def test_needs_true_or_false(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.put(URL, {"open": "no"}, format="json").status_code, 400)


class ClosedRegistrationTests(MultiStudentSetup, TestCase):
    def close(self):
        setting = PublicRegistrationSetting.load()
        setting.open = False
        setting.save()

    def test_a_student_cant_register_themselves_while_closed(self):
        self.close()
        response = self.post_batch(batch("student_individual"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StudentProfile.objects.exists())

    def test_a_supervisor_still_can(self):
        self.close()
        response = self.post_batch(batch("supervisor_individual"))
        self.assertEqual(response.status_code, 201, response.data)
