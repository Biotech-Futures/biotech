"""The rules a registration has to pass (UserRegisterBodySerializer): which
emails are already taken, who may be named as the guardian and supervisor, and
the warnings the person registering can confirm their way past."""
from django.test import TestCase
from django.utils import timezone

from apps.common.role_names import ROLE_MENTOR, ROLE_STUDENT, ROLE_SUPERVISOR
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import StudentProfile, SupervisorProfile, User
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
                self.assertEqual(errors["Title"][0].code, "email_taken")


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


class CrossRoleEmailTests(RegistrationValidationTestCase):
    def _user_with_role(self, email, role_name):
        user = User.objects.create_user(email=email, first_name="Robin", last_name="Existing")
        RoleAssignmentHistory.objects.create(
            user=user, role=Roles.objects.get_or_create(role_name=role_name)[0], valid_from=timezone.now(),
        )
        return user

    def _student(self, email="pupil@example.com"):
        user = User.objects.create_user(email=email, first_name="Robin", last_name="Existing")
        return StudentProfile.objects.create(
            user=user, pg_first_name="Pat", pg_last_name="Parent", school_name="Test High School", year_lvl="10",
        )

    def _supervisor(self, email="grace@example.com"):
        user = User.objects.create_user(email=email, first_name="Grace", last_name="Green")
        return SupervisorProfile.objects.create(user=user, school_name="Test High School")

    def assertRefusedOn(self, field, code, **overrides):
        errors = self.assertRefused(**overrides)
        self.assertEqual(list(errors), [field], errors)
        self.assertEqual(errors[field][0].code, code)

    def test_a_student_cannot_be_nominated_as_a_supervisor(self):
        self._student()

        for typed in ("pupil@example.com", "Pupil@Example.com"):
            with self.subTest(typed=typed):
                self.assertRefusedOn("SupervisorEmail", "supervisor_email_is_student", SupervisorEmail=typed)

    def test_an_account_with_only_the_student_role_cannot_be_nominated(self):
        self._user_with_role("pupil@example.com", ROLE_STUDENT)

        self.assertRefusedOn(
            "SupervisorEmail", "supervisor_email_is_student", SupervisorEmail="pupil@example.com",
        )

    def test_another_kind_of_account_cannot_be_nominated(self):
        self._user_with_role("mentor@example.com", ROLE_MENTOR)

        self.assertRefusedOn("SupervisorEmail", "supervisor_email_in_use", SupervisorEmail="mentor@example.com")

    def test_an_existing_supervisor_can_be_nominated(self):
        self._supervisor()
        self._user_with_role("role-only@example.com", ROLE_SUPERVISOR)

        for typed in ("grace@example.com", "GRACE@example.com", "role-only@example.com"):
            with self.subTest(typed=typed):
                self.assertAccepted(SupervisorEmail=typed)

    def test_a_supervisors_email_cannot_register_as_a_student(self):
        self._supervisor()

        for typed in ("grace@example.com", "Grace@Example.com"):
            with self.subTest(typed=typed):
                self.assertRefusedOn("Title", "student_email_is_supervisor", Title=typed)

    def test_any_other_email_in_use_is_reported_as_taken(self):
        self._user_with_role("mentor@example.com", ROLE_MENTOR)

        self.assertRefusedOn("Title", "email_taken", Title="mentor@example.com")


class OptionalGuardianTests(RegistrationValidationTestCase):
    no_guardian = {"GuardianEmail": "", "GuardianName": "", "GuardianSurname": ""}
    guardian_fields = ["GuardianEmail", "GuardianName", "GuardianSurname"]

    def assertGuardianRequired(self, fields=None, **overrides):
        errors = self.assertRefused(**overrides)
        self.assertEqual(sorted(errors), fields or self.guardian_fields, errors)
        for field in errors:
            self.assertEqual(errors[field][0].code, "guardian_required")

    def test_a_student_registering_individually_must_name_a_guardian(self):
        for said in ("Self", "self", "individual", "student"):
            with self.subTest(said=said):
                self.assertGuardianRequired(RegisteredBy=said, **self.no_guardian)

    def test_a_form_that_doesnt_say_who_registered_must_name_a_guardian(self):
        for said in (None, "", "someone else"):
            with self.subTest(said=said):
                self.assertGuardianRequired(RegisteredBy=said, **self.no_guardian)

    def test_guardian_fields_left_out_altogether_are_reported_too(self):
        self.assertGuardianRequired(
            RegisteredBy="Self", GuardianEmail=None, GuardianName=None, GuardianSurname=None,
        )

    def test_only_the_missing_guardian_fields_are_reported(self):
        self.assertGuardianRequired(["GuardianEmail"], RegisteredBy="Self", GuardianEmail="")
        self.assertGuardianRequired(["GuardianName"], RegisteredBy="Self", GuardianName="   ")

    def test_a_peer_or_supervisor_can_register_a_student_without_a_guardian(self):
        for said in ("Peer", "team", "Supervisor", " supervisor ", "teacher"):
            with self.subTest(said=said):
                self.assertAccepted(RegisteredBy=said, **self.no_guardian)

    def test_a_peer_or_supervisor_can_leave_the_guardian_fields_out(self):
        self.assertAccepted(
            RegisteredBy="Peer", GuardianEmail=None, GuardianName=None, GuardianSurname=None,
        )

    def test_a_guardian_is_accepted_whoever_registers(self):
        for said in ("Self", "Peer", "Supervisor", None):
            with self.subTest(said=said):
                self.assertAccepted(RegisteredBy=said)

    def test_a_guardian_given_by_a_peer_or_supervisor_still_cannot_be_the_student(self):
        for said in ("Peer", "Supervisor"):
            with self.subTest(said=said):
                self.assertRefusedWith(
                    "guardian cannot be the same person", RegisteredBy=said, GuardianEmail="kid@example.com",
                )
                self.assertRefusedWith(
                    "guardian cannot be the same person",
                    RegisteredBy=said, GuardianName="Kid", GuardianSurname="Student",
                )

    def test_a_malformed_guardian_email_is_refused_whoever_registers(self):
        errors = self.assertRefused(RegisteredBy="Supervisor", GuardianEmail="not-an-email")

        self.assertEqual(list(errors), ["GuardianEmail"])
