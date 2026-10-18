"""Whether registration is open, by the year's dates: open with none,
readable by anyone. While closed, students can't register themselves, nor
supervisors register students, but for those let register after it closes
(Supervisors After Close)."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.models import AdminScope, RegistrationWindow, StudentProfile, User
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch

URL = "/api/v1/management/registration-open/"


class RegistrationOpenTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(email="admin-open@test.com", password="pw12345!")
        AdminScope.objects.create(user=self.admin)

    def test_open_with_no_dates_and_closed_after_them(self):
        state = self.client.get(URL).json()
        self.assertTrue(state["open_now"])
        # Only a supervisor or an admin is told whether they can register students.
        self.assertNotIn("can_register_students", state)

        closes = timezone.now() - timedelta(days=1)
        RegistrationWindow.objects.update_or_create(year=timezone.now().year, defaults={"closes_at": closes})
        state = self.client.get(URL).json()
        self.assertFalse(state["open_now"])
        self.assertIsNotNone(state["closes_at"])

    def test_nobody_switches_it_any_more(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.put(URL, {"open": False}, format="json").status_code, 405)


class ClosedByDatesTests(MultiStudentSetup, TestCase):
    """Closed by its dates: supervisors too, but for those let register after."""

    def can_register(self):
        return self.supervisor_client.get(URL).json()["can_register_students"]

    def test_a_supervisor_cant_register_after_it_closes_unless_let(self):
        self.assertTrue(self.can_register())
        self.close_window()
        self.assertFalse(self.can_register())
        response = self.post_batch(batch("supervisor_individual"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StudentProfile.objects.exists())

        self.profile.register_after_close = True
        self.profile.save()
        self.assertTrue(self.can_register())
        response = self.post_batch(batch("supervisor_individual"))
        self.assertEqual(response.status_code, 201, response.data)
        # Students still can't register themselves.
        self.assertEqual(self.post_batch(batch("student_individual", offset=10)).status_code, 400)
        self.assertEqual(StudentProfile.objects.count(), 1)


class RegistrationSupervisorsTests(MultiStudentSetup, TestCase):
    """Supervisors After Close: every supervisor, switched on or off by staff."""

    LIST = "/api/v1/management/registration-supervisors/"

    def test_staff_list_and_switch_each_supervisor(self):
        self.post_batch(batch("supervisor_individual"))
        rows = self.staff_client.get(self.LIST).json()
        row = next(item for item in rows if item["user_id"] == self.supervisor.id)
        self.assertEqual(
            (row["name"], row["email"], row["school"], row["students"], row["register_after_close"]),
            ("Current Supervisor", "manager@example.test", "Current School", 1, False),
        )

        url = f"{self.LIST}{self.supervisor.id}/"
        response = self.staff_client.put(url, {"register_after_close": True}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["register_after_close"])
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.register_after_close)
        self.assertEqual(self.staff_client.put(url, {"register_after_close": "yes"}, format="json").status_code, 400)
        self.assertEqual(
            self.staff_client.put(f"{self.LIST}999999/", {"register_after_close": True}, format="json").status_code,
            404,
        )

    def test_only_staff(self):
        self.assertEqual(self.supervisor_client.get(self.LIST).status_code, 403)
        self.assertEqual(
            self.supervisor_client.put(
                f"{self.LIST}{self.supervisor.id}/", {"register_after_close": True}, format="json",
            ).status_code,
            403,
        )
