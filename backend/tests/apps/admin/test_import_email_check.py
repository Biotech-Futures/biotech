"""Admin > Users > Import Students and Import Mentors: every address in the
file checked before Import (apps.admin.import_email_check), and the supervisor
rows importing refuses. All HTTP is mocked (QevTestCase), so no test can
spend real credits."""
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.admin.services.user import add_users_by_role
from apps.admin.user_email_check import (
    NOT_AN_EMAIL, SUPERVISOR_IS_STUDENT, SUPERVISOR_NOT_A_SUPERVISOR, SUPERVISOR_NOT_AN_EMAIL, TAKEN,
)
from apps.resources.models import Roles
from apps.users.models import AdminScope, EmailVerification, StudentProfile, SupervisorProfile, User
from apps.users.serializers import GUARDIAN_IS_SELF, GUARDIAN_IS_STUDENT, PLACEHOLDER_ADDRESS, SUPERVISOR_IS_SELF
from tests.apps.users.test_email_verification import QevTestCase, qev
from tests.apps.users.test_registration_email_warnings import answer

URL = "/api/v1/admin/user/import-check/"


def row(number, email, **fields):
    return {"row": number, "email": email, "firstName": "Pip", "lastName": "Pupil", **fields}


class ImportCheckSetup(QevTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        # Any lookup a test doesn't set up says the address exists.
        self.answer_always(qev())
        for name in ("student", "supervisor", "mentor"):
            Roles.objects.get_or_create(role_name=name)
        self.admin = User.objects.create_user(email="admin@example.test", first_name="Ada", last_name="Admin")
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.student = User.objects.create_user(email="kid@example.test", first_name="Kid", last_name="Pupil")
        StudentProfile.objects.create(
            user=self.student, school_name="Test High", year_lvl="10", pg_first_name="Pat", pg_last_name="Parent",
        )
        self.mentor = User.objects.create_user(email="mentor@example.test")
        self.supervisor = User.objects.create_user(
            email="m.somerville@example.edu", first_name="Mary", last_name="Somerville",
        )
        SupervisorProfile.objects.create(user=self.supervisor, school_name="Test High")

    def check(self, rows, kind="students", lookup=False):
        response = self.client.post(URL, {"kind": kind, "rows": rows, "lookup": lookup}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def by_row(self, rows, **extra):
        return {result["row"]: result for result in self.check(rows, **extra)["results"]}


class ProblemTests(ImportCheckSetup):
    def test_admins_only(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(URL, {"kind": "students", "rows": [row(2, "a@b.test")]}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_each_rows_problems(self):
        results = self.by_row([
            row(2, "nope"),
            row(3, "pip@example.invalid"),
            row(4, "KID@example.test"),
            row(5, "pip@example.test"),
            row(6, "pip@example.test"),
            row(7, "a@example.test", guardianEmail="A@example.test"),
            row(8, "b@example.test", guardianEmail="kid@example.test"),
            row(9, "c@example.test", guardianEmail="pip@example.test"),
            row(10, "d@example.test", supervisorEmail="kid@example.test"),
            row(11, "e@example.test", supervisorEmail="mentor@example.test"),
            row(12, "f@example.test", supervisorEmail="bad"),
            row(13, "g@example.test", supervisorEmail="g@example.test"),
            row(14, "h@example.test", supervisorEmail="pip@example.test"),
            row(15, "i@example.test", supervisorEmail="M.Somerville@example.edu", guardianEmail="pat@example.test"),
        ])

        self.assertEqual({number: result["problems"] for number, result in results.items()}, {
            2: [NOT_AN_EMAIL],
            3: [PLACEHOLDER_ADDRESS],
            4: [TAKEN],
            5: [],
            6: ["This student is also in row 5."],
            7: [GUARDIAN_IS_SELF],
            8: [GUARDIAN_IS_STUDENT],
            9: ["The guardian's email is the student's in row 5."],
            10: [SUPERVISOR_IS_STUDENT],
            11: [SUPERVISOR_NOT_A_SUPERVISOR],
            12: [SUPERVISOR_NOT_AN_EMAIL],
            13: [SUPERVISOR_IS_SELF],
            14: ["The supervisor's email is the student's in row 5."],
            15: [],
        })

    def test_a_mentor_listed_twice(self):
        results = self.by_row([row(2, "mo@example.test"), row(3, "Mo@example.test")], kind="mentors")
        self.assertEqual(results[3]["problems"], ["This mentor is also in row 2."])


class WarningTests(ImportCheckSetup):
    def warnings(self, result):
        return [(warning["field"], warning["message"]) for warning in result["warnings"]]

    def test_mailboxes_names_and_a_guardian_with_an_account(self):
        answer("gone@example.test", did_you_mean="gone@example.org")
        answer("pat@example.test", "unknown")
        results = self.by_row([
            row(2, "gone@example.test"),
            row(3, "pipupil@example.test", firstName="Pip", lastName="Pupill"),
            row(4, "ok@example.test", guardianEmail="pat@example.test"),
            row(5, "ok2@example.test", guardianEmail="mentor@example.test"),
        ])

        self.assertEqual(self.warnings(results[2]), [
            ("email", "The student's email doesn't appear to exist. Did you mean gone@example.org?"),
        ])
        self.assertEqual(self.warnings(results[3]), [("email", "The student's email looks like a typo of their name.")])
        self.assertEqual(self.warnings(results[4]), [("guardianEmail", "The guardian's email couldn't be verified.")])
        self.assertEqual(self.warnings(results[5]), [("guardianEmail", "The guardian's email already has an account.")])

    def test_a_new_supervisor_near_an_existing_one_or_their_name(self):
        results = self.by_row([
            row(2, "a@example.test", supervisorEmail="m.somervile@example.edu"),
            row(3, "b@example.test", supervisorEmail="m.somerville@exmaple.edu"),
            row(4, "c@example.test", supervisorEmail="samteachr@school.test",
                supervisorFirstName="Sam", supervisorLastName="Teacher"),
            # An existing supervisor's own address: nothing to warn about.
            row(5, "d@example.test", supervisorEmail="m.somerville@example.edu"),
        ])

        near = (
            "The supervisor's email is a letter or two off Mary Somerville's, m.somerville@example.edu. "
            "Did you mean that? Importing makes a new supervisor account for this one."
        )
        self.assertEqual(self.warnings(results[2]), [("supervisorEmail", near)])
        self.assertEqual(self.warnings(results[3]), [("supervisorEmail", near)])
        self.assertEqual(self.warnings(results[4]), [
            ("supervisorEmail", "The supervisor's email looks like a typo of their name."),
        ])
        self.assertEqual(results[5]["warnings"], [])

    def test_a_row_with_a_problem_has_no_warnings(self):
        answer("gone@example.test")
        results = self.by_row([row(2, "kid@example.test", guardianEmail="gone@example.test")])
        self.assertEqual((results[2]["problems"], results[2]["warnings"]), ([TAKEN], []))

    def test_a_mentors_mailbox(self):
        answer("gone@example.test", "unknown")
        results = self.by_row([row(2, "gone@example.test")], kind="mentors")
        self.assertEqual(self.warnings(results[2]), [("email", "The mentor's email couldn't be verified.")])


class LookupTests(ImportCheckSetup):
    def test_new_addresses_are_looked_up_once_then_warned_about(self):
        self.answer_always(qev("invalid", "rejected_email"))
        rows = [
            row(2, "new@example.test", guardianEmail="parent@example.test", supervisorEmail="m.somerville@example.edu"),
            row(3, "new2@example.test", guardianEmail="parent@example.test"),
            # Refused: nothing on it is looked up.
            row(4, "kid@example.test", guardianEmail="other.parent@example.test"),
        ]

        with self.captureOnCommitCallbacks(execute=True):
            started = self.check(rows, lookup=True)

        # The two students and their guardian: not the supervisor (an
        # account), nor anything on the refused row.
        self.assertEqual(self.http.call_count, 3)
        lookups = started["lookups"]
        self.assertEqual((lookups["status"], lookups["total"]), ("started", 3))
        progress = self.client.get(f"{URL}{lookups['jobId']}/")
        self.assertEqual((progress.status_code, progress.data["status"], progress.data["done"]), (200, "done", 3))
        self.assertEqual(
            set(EmailVerification.objects.values_list("email", flat=True)),
            {"new@example.test", "new2@example.test", "parent@example.test"},
        )

        results = {result["row"]: result for result in self.check(rows)["results"]}
        self.assertEqual(
            [warning["message"] for warning in results[2]["warnings"]],
            ["The student's email doesn't appear to exist.", "The guardian's email doesn't appear to exist."],
        )
        self.assertEqual(self.http.call_count, 3)

    def test_with_every_answer_on_file_there_is_nothing_to_follow(self):
        answer("new@example.test", "valid")
        with self.captureOnCommitCallbacks(execute=True):
            self.assertIsNone(self.check([row(2, "new@example.test")], lookup=True)["lookups"])
        self.http.assert_not_called()


class ImportRefusesTests(ImportCheckSetup):
    def add(self, supervisor_email):
        return add_users_by_role([{
            "email": "new@example.test", "firstName": "Pip", "lastName": "Pupil", "role": "student",
            "supervisorEmail": supervisor_email, "supervisorFirstName": "Sam", "supervisorLastName": "Teacher",
        }])[0]

    def test_a_supervisor_email_the_check_refuses_importing_refuses(self):
        for email, message in (
            ("kid@example.test", SUPERVISOR_IS_STUDENT),
            ("Mentor@example.test", SUPERVISOR_NOT_A_SUPERVISOR),
            ("bad", SUPERVISOR_NOT_AN_EMAIL),
            ("sam@example.invalid", PLACEHOLDER_ADDRESS),
            ("new@example.test", SUPERVISOR_IS_SELF),
        ):
            with self.subTest(email=email):
                self.assertEqual(self.add(email)["msg"], message)
        self.assertFalse(User.objects.filter(email="new@example.test").exists())
        # Nobody was quietly made a supervisor.
        self.assertFalse(SupervisorProfile.objects.filter(user__in=[self.student, self.mentor]).exists())

    def test_an_existing_or_new_supervisor_is_fine(self):
        self.assertIsNotNone(self.add("M.Somerville@example.edu")["data"])
        profile = StudentProfile.objects.get(user__email="new@example.test")
        self.assertEqual(profile.supervisor_id, self.supervisor.pk)
