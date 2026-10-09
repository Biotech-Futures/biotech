"""The rules a registration has to pass (UserRegisterBodySerializer): which
emails are already taken, who may be named as the guardian and supervisor, and
the warnings the person registering can confirm their way past."""
from django.test import TestCase

from apps.users.models import User
from apps.users.serializers import UserRegisterBodySerializer


def _body(**overrides):
    body = {
        "Title": "kid@example.com",
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
        "SchoolName": "Test High School",
        "YearLevel": "10",
        "Areaofinterest": "Biotechnology",
    }
    body.update(overrides)
    return {key: value for key, value in body.items() if value is not None}


class RegistrationValidationTestCase(TestCase):
    def assertAccepted(self, **overrides):
        serializer = UserRegisterBodySerializer(data=_body(**overrides))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.validated_data

    def assertRefused(self, **overrides):
        serializer = UserRegisterBodySerializer(data=_body(**overrides))
        self.assertFalse(serializer.is_valid())
        return serializer.errors

    def assertRefusedWith(self, message, **overrides):
        errors = self.assertRefused(**overrides)
        self.assertEqual(list(errors), ["non_field_errors"], errors)
        self.assertIn(message, errors["non_field_errors"][0])


class DuplicateEmailTests(RegistrationValidationTestCase):
    def test_a_new_email_is_accepted(self):
        self.assertAccepted()

    def test_an_email_already_in_use_is_refused_whatever_its_casing(self):
        User.objects.create_user(email="kid@example.com")

        for typed in ("kid@example.com", "Kid@Example.com", "KID@EXAMPLE.COM"):
            with self.subTest(typed=typed):
                errors = self.assertRefused(Title=typed)

                self.assertEqual(list(errors), ["Title"])
                self.assertIn("already exists", errors["Title"][0])


class SamePersonTests(RegistrationValidationTestCase):
    def test_the_guardian_cannot_share_the_students_email(self):
        self.assertRefusedWith("guardian cannot be the same person", GuardianEmail="KID@example.com")

    def test_the_guardian_cannot_share_the_students_name(self):
        self.assertRefusedWith(
            "guardian cannot be the same person", GuardianName=" kid ", GuardianSurname="STUDENT",
        )

    def test_a_guardian_sharing_only_the_surname_is_accepted(self):
        self.assertAccepted(GuardianSurname="Student")

    def test_the_supervisor_cannot_share_the_students_email(self):
        self.assertRefusedWith("supervisor cannot be the same person", SupervisorEmail="Kid@Example.com")

    def test_the_supervisor_cannot_share_the_students_name(self):
        self.assertRefusedWith(
            "supervisor cannot be the same person", SupervisorFirstName="KID", SupervisorSurname="student",
        )

    def test_a_supervisor_sharing_only_the_first_name_is_accepted(self):
        self.assertAccepted(SupervisorFirstName="Kid")


class SchoolWarningTests(RegistrationValidationTestCase):
    def test_a_school_named_like_a_university_is_held_for_confirmation(self):
        for school in ("University of Sydney", "the UNIVERSITY of sydney", "Sydney University"):
            with self.subTest(school=school):
                self.assertRefusedWith("looks like a university", SchoolName=school)

    def test_declining_to_confirm_still_holds_it(self):
        self.assertRefusedWith(
            "looks like a university", SchoolName="University of Sydney", ConfirmSchoolOverride=False,
        )

    def test_confirming_the_school_lets_it_through(self):
        data = self.assertAccepted(SchoolName="University of Sydney", ConfirmSchoolOverride=True)

        self.assertEqual(data["SchoolName"], "University of Sydney")

    def test_an_ordinary_school_needs_no_confirmation(self):
        self.assertAccepted(SchoolName="Test High School")


class NameEmailWarningTests(RegistrationValidationTestCase):
    """William Nixon's email, by how many edits its local part is from his name."""

    def _william(self, local_part, **overrides):
        return {
            "Title": f"{local_part}@example.com", "FirstName": "William", "Surname": "Nixon", **overrides,
        }

    def test_an_email_matching_the_name_is_accepted(self):
        for local_part in ("william.nixon", "william_nixon", "williamnixon", "William.Nixon"):
            with self.subTest(local_part=local_part):
                self.assertAccepted(**self._william(local_part))

    def test_an_email_one_or_two_edits_from_the_name_is_held_for_confirmation(self):
        for local_part in ("wiliam.nixon", "wilam.nixon"):
            with self.subTest(local_part=local_part):
                self.assertRefusedWith("might have a typo", **self._william(local_part))

    def test_an_email_three_edits_from_the_name_is_accepted(self):
        self.assertAccepted(**self._william("wilm.nixon"))

    def test_an_email_unrelated_to_the_name_is_accepted(self):
        self.assertAccepted(**self._william("coolkid123"))

    def test_confirming_the_email_lets_it_through(self):
        self.assertAccepted(**self._william("wiliam.nixon", ConfirmNameEmailOverride=True))

    def test_confirming_the_school_does_not_confirm_the_email(self):
        self.assertRefusedWith(
            "might have a typo", **self._william("wiliam.nixon", ConfirmSchoolOverride=True),
        )
