"""A guardian's first name, surname and email go together: any one given
needs the other two, in every registration journey that takes a guardian. A
guardian with none of them stays allowed wherever it was."""
from itertools import product

from django.core.cache import cache
from django.test import TestCase

from apps.users.models import StudentProfile
from apps.users.serializers import GUARDIAN_TOGETHER, UserRegisterBodySerializer
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch

GUARDIAN = {"GuardianName": "Pat", "GuardianSurname": "Parent", "GuardianEmail": "pat@guardians.example.test"}


def body(**guardian):
    return {
        "Title": "kid@students.example.test", "FirstName": "Kid", "Surname": "Student",
        "Country": "Australia", "Region": "NSW", "SchoolName": "Example High", "YearLevel": "10",
        "Areaofinterest": "Biotechnology", "RegisteredBy": "supervisor", **guardian,
    }


class SerializerTests(TestCase):
    def test_every_combination_of_the_three(self):
        for given in product((True, False), repeat=3):
            guardian = {field: value for field, value, keep in zip(GUARDIAN, GUARDIAN.values(), given) if keep}
            with self.subTest(given=sorted(guardian)):
                serializer = UserRegisterBodySerializer(data=body(**guardian))
                if len(guardian) in (0, 3):
                    self.assertTrue(serializer.is_valid(), serializer.errors)
                    continue
                self.assertFalse(serializer.is_valid())
                missing = set(GUARDIAN) - set(guardian)
                self.assertEqual(set(serializer.errors), missing)
                for field in missing:
                    self.assertEqual(serializer.errors[field][0], GUARDIAN_TOGETHER)
                    self.assertEqual(serializer.errors[field][0].code, "guardian_incomplete")

    def test_blank_or_space_only_values_count_as_not_given(self):
        serializer = UserRegisterBodySerializer(data=body(GuardianName="Pat", GuardianSurname="  ", GuardianEmail=""))
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"GuardianSurname", "GuardianEmail"})

    def test_a_student_registering_alone_still_needs_all_three(self):
        serializer = UserRegisterBodySerializer(data=body(RegisteredBy="Self"))
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), set(GUARDIAN))
        self.assertEqual(serializer.errors["GuardianEmail"][0].code, "guardian_required")


class JourneyTests(MultiStudentSetup, TestCase):
    """Partial guardians, sent deferred or not, in each journey."""

    def journeys(self):
        return (
            ("student_individual", self.client, 0),
            ("student_team", self.client, 1),
            ("supervisor_individual", self.supervisor_client, 0),
            ("supervisor_group", self.supervisor_client, 0),
            ("supervisor_csv", self.supervisor_client, 0),
            ("admin", self.staff_client, 0),
        )

    def request(self, journey, offset):
        return batch("supervisor_individual" if journey == "admin" else journey, offset=offset)

    def submit(self, *args, **kwargs):
        # More registrations than the per-IP limit allows in one test.
        cache.clear()
        return super().submit(*args, **kwargs)

    def test_a_partial_guardian_is_refused_on_each_missing_field(self):
        for offset, (journey, client, index) in enumerate(self.journeys()):
            for deferred in (False, True):
                with self.subTest(journey=journey, deferred=deferred):
                    body = self.request(journey, offset * 10 + int(deferred) * 100)
                    student = body["payload"]["students"][index]
                    student.update(guardianDeferred=deferred, guardian={"firstName": "Pat", "lastName": "Parent"})
                    response = self.submit(body=body, client=client)
                    self.assertEqual(response.status_code, 400, response.data)
                    fields = response.data["fields"]
                    self.assertIn(f"students.{index}.guardian.email", fields)
                    self.assertNotIn(f"students.{index}.guardian.firstName", fields)
                    self.assertNotIn(f"students.{index}.guardian.lastName", fields)
        self.assertFalse(StudentProfile.objects.exists())

    def test_only_an_email_is_refused_on_both_names(self):
        body = batch("supervisor_individual")
        body["payload"]["students"][0]["guardian"] = {"email": "pat@guardians.example.test"}
        response = self.submit(body=body, client=self.supervisor_client)
        self.assertEqual(response.status_code, 400, response.data)
        fields = response.data["fields"]
        self.assertEqual(
            {key for key in fields if key.startswith("students.0.guardian.")},
            {"students.0.guardian.firstName", "students.0.guardian.lastName"},
        )
        self.assertEqual(fields["students.0.guardian.firstName"], [GUARDIAN_TOGETHER])

    def test_a_whole_guardian_or_none_where_allowed_still_registers(self):
        for offset, (journey, client, index) in enumerate(self.journeys()):
            if journey == "student_individual":
                continue
            with self.subTest(journey=journey, guardian="none"):
                response = self.submit(body=self.request(journey, 200 + offset * 10), client=client)
                self.assertEqual(response.status_code, 201, response.data)
            with self.subTest(journey=journey, guardian="all three"):
                body = self.request(journey, 400 + offset * 10)
                student = body["payload"]["students"][index]
                student.update(guardianDeferred=False, guardian={
                    "firstName": "Pat", "lastName": "Parent", "email": f"parent{offset}@guardians.example.test",
                })
                response = self.submit(body=body, client=client)
                self.assertEqual(response.status_code, 201, response.data)
        response = self.submit(body=batch("student_individual", offset=900))
        self.assertEqual(response.status_code, 201, response.data)
