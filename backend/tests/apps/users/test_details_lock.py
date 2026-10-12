"""Who can change a student's own details (slide 14): the student, when they
registered themselves or through a peer; their supervisor, when the
supervisor registered them or has edited them since. Guardian details are
the student's to change either way."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.admin.services.user import upsert_student_profile
from apps.common.role_names import ROLE_STUDENT, ROLE_SUPERVISOR
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import StudentProfile, SupervisorProfile, User


def _registration(registered_by=None, email="kid@example.com"):
    body = {
        "Title": email,
        "FirstName": "Kid",
        "Surname": "Student",
        "Country": "Australia",
        "Region": "NSW",
        "SupervisorEmail": "sup@example.com",
        "SupervisorFirstName": "Sam",
        "SupervisorSurname": "Super",
        "GuardianEmail": "parent@example.com",
        "GuardianName": "Pat",
        "GuardianSurname": "Parent",
        "SchoolName": "Test High",
        "YearLevel": "10",
        "Areaofinterest": "Biotechnology",
    }
    if registered_by is not None:
        body["RegisteredBy"] = registered_by
    return {"body": body}


class RegistrationLockTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        for name in [ROLE_STUDENT, ROLE_SUPERVISOR]:
            Roles.objects.get_or_create(role_name=name)

    def _register(self, registered_by=None):
        response = self.client.post(reverse("registration"), _registration(registered_by), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return StudentProfile.objects.get(user__email="kid@example.com")

    def test_a_supervisors_registration_locks_the_students_details(self):
        for said in ("Supervisor", "teacher"):
            with self.subTest(said=said):
                StudentProfile.objects.all().delete()
                User.objects.filter(email="kid@example.com").delete()
                profile = self._register(said)
                self.assertEqual(profile.registered_by, StudentProfile.RegisteredBy.SUPERVISOR)
                self.assertTrue(profile.details_locked)

    def test_a_student_or_peer_registration_leaves_them_free_to_edit(self):
        for said, recorded in (("Self", "self"), ("Peer", "peer")):
            with self.subTest(said=said):
                StudentProfile.objects.all().delete()
                User.objects.filter(email="kid@example.com").delete()
                profile = self._register(said)
                self.assertEqual(profile.registered_by, recorded)
                # Their supervisor is linked all the same.
                self.assertIsNotNone(profile.supervisor_id)
                self.assertFalse(profile.details_locked)

    def test_a_registration_that_doesnt_say_leaves_them_free_to_edit(self):
        profile = self._register()

        self.assertEqual(profile.registered_by, "")
        self.assertFalse(profile.details_locked)


class StudentEditLockTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="amy@example.com", first_name="Amy", last_name="Chen", account_status=User.AccountStatus.ACTIVE,
        )
        RoleAssignmentHistory.objects.create(
            user=self.student, role=Roles.objects.get_or_create(role_name=ROLE_STUDENT)[0],
            valid_from=timezone.now() - timedelta(days=1),
        )
        self.supervisor = User.objects.create_user(email="grace@school.edu", first_name="Grace", last_name="Green")
        self.profile = StudentProfile.objects.create(
            user=self.student, pg_first_name="Pat", pg_last_name="Parent", pg_email="pat@example.com",
            parent_guardian_flag=True, school_name="Test High", year_lvl="10",
            supervisor=SupervisorProfile.objects.create(user=self.supervisor, school_name="Test High"),
        )
        self.client = APIClient()
        self.client.force_authenticate(self.student)

    def _edit_name(self):
        return self.client.patch(reverse("MeListHTMLView"), {"first_name": "Amelia"}, format="json")

    def test_a_student_with_a_supervisor_who_registered_themselves_can_edit(self):
        response = self._edit_name()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()["details_locked"])
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Amelia")

    def test_a_student_their_supervisor_registered_cannot_edit_but_can_change_their_guardian(self):
        self.profile.registered_by = StudentProfile.RegisteredBy.SUPERVISOR
        self.profile.save()

        self.assertEqual(self._edit_name().status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(self.client.get(reverse("MeListHTMLView")).json()["details_locked"])
        response = self.client.put(
            reverse("me-guardian"),
            {"first_name": "Robin", "last_name": "Carer", "email": "robin@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_supervisors_edit_locks_a_student_who_registered_themselves(self):
        self.profile.registered_by = StudentProfile.RegisteredBy.SELF
        self.profile.has_join_permission = True
        self.profile.save()
        supervisor = APIClient()
        supervisor.force_authenticate(self.supervisor)

        response = supervisor.patch(
            reverse("supervised-student-detail", kwargs={"pk": self.student.pk}),
            {"first_name": "Amy", "last_name": "Chen", "school_name": "Test High", "year_lvl": "11"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.supervisor_edited_at)
        self.assertEqual(self._edit_name().status_code, status.HTTP_403_FORBIDDEN)


class AdminAddedStudentTests(TestCase):
    def test_a_student_an_admin_adds_is_recorded_as_such_and_free_to_edit(self):
        user = User.objects.create_user(email="new@example.com", first_name="New", last_name="Student")

        upsert_student_profile(user.id, "New", "Student", "Test High", 10)

        profile = StudentProfile.objects.get(user=user)
        self.assertEqual(profile.registered_by, StudentProfile.RegisteredBy.ADMIN)
        self.assertFalse(profile.details_locked)

    def test_an_admin_editing_a_student_keeps_who_registered_them(self):
        user = User.objects.create_user(email="sup-reg@example.com", first_name="Sup", last_name="Reg")
        StudentProfile.objects.create(
            user=user, pg_first_name="Pat", pg_last_name="Parent", school_name="Test High", year_lvl="10",
            registered_by=StudentProfile.RegisteredBy.SUPERVISOR,
        )

        upsert_student_profile(user.id, "Sup", "Reg", "New High", 11)

        self.assertEqual(StudentProfile.objects.get(user=user).registered_by, StudentProfile.RegisteredBy.SUPERVISOR)
