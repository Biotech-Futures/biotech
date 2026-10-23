"""Addresses on the reserved .invalid domain (the CSV template's example row)
are refused for students, guardians and supervisors, and never looked up."""
from django.core.cache import cache
from django.test import TestCase

from apps.users.email_precheck import registration_addresses
from apps.users.serializers import PLACEHOLDER_EMAIL, UserRegisterBodySerializer, is_placeholder_email
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch


def body(**fields):
    return {
        "Title": "kid@students.example.test", "FirstName": "Kid", "Surname": "Student",
        "Country": "Australia", "Region": "NSW", "SchoolName": "Example High", "YearLevel": "10",
        "Areaofinterest": "Biotechnology", "RegisteredBy": "supervisor", **fields,
    }


class PlaceholderTests(TestCase):
    def test_which_addresses_are_placeholders(self):
        for address in ("a@example.invalid", "A@School.Example.INVALID", " a@example.invalid. ", "a@invalid"):
            with self.subTest(address=address):
                self.assertTrue(is_placeholder_email(address))
        for address in ("a@invalid.com", "a@example.invalidx", "invalid@example.com", "", None):
            with self.subTest(address=address):
                self.assertFalse(is_placeholder_email(address))

    def test_each_address_field_refuses_a_placeholder(self):
        guardian = {"GuardianName": "Pat", "GuardianSurname": "Parent", "GuardianEmail": "pat@guardians.example.test"}
        for field, extra in (
            ("Title", {}),
            ("GuardianEmail", guardian),
            ("SupervisorEmail", {"SupervisorFirstName": "Sam", "SupervisorSurname": "Teacher"}),
        ):
            with self.subTest(field=field):
                serializer = UserRegisterBodySerializer(data=body(**{**extra, field: "someone@example.invalid"}))
                self.assertFalse(serializer.is_valid())
                self.assertEqual(serializer.errors[field][0], PLACEHOLDER_EMAIL)
                self.assertEqual(serializer.errors[field][0].code, "placeholder_email")

    def test_the_pre_check_never_looks_one_up(self):
        students = [{"email": "kid@example.invalid", "guardian": {"email": "pat@guardians.example.test"}}]
        self.assertEqual(
            registration_addresses(students, "sam@school.example.invalid"), ["pat@guardians.example.test"],
        )


class JourneyTests(MultiStudentSetup, TestCase):
    def submit(self, *args, **kwargs):
        # More registrations than the per-IP limit allows in one test.
        cache.clear()
        return super().submit(*args, **kwargs)

    def test_a_csv_row_with_template_addresses_is_refused_on_each(self):
        body = batch("supervisor_csv", 2)
        first = body["payload"]["students"][0]
        first.update(email="student@example.invalid", guardianDeferred=False, guardian={
            "firstName": "Pat", "lastName": "Parent", "email": "guardian@example.invalid",
        })

        response = self.submit(body=body, client=self.supervisor_client)

        self.assertEqual(response.status_code, 400, response.data)
        fields = response.data["fields"]
        self.assertEqual(fields["students.0.email"], [PLACEHOLDER_EMAIL])
        self.assertEqual(fields["students.0.guardian.email"], [PLACEHOLDER_EMAIL])
        self.assertNotIn("students.1.email", fields)

    def test_a_student_naming_a_placeholder_supervisor_is_refused(self):
        body = batch("student_individual")
        body["payload"]["supervisor"]["email"] = "teacher@example.invalid"

        response = self.submit(body=body)

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn(PLACEHOLDER_EMAIL, str(response.data["fields"]))

    def test_real_addresses_still_register(self):
        self.assertEqual(self.submit(body=batch("supervisor_csv", 2), client=self.supervisor_client).status_code, 201)
