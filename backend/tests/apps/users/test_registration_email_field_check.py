"""Checking a registration's email boxes as the person leaves each one
(apps.users.email_field_check): Submit's hard problems only, in Submit's order,
always on. All HTTP is mocked (QevTestCase), so no test can spend real credits."""

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.resources.models import Roles
from apps.users.email_field_check import MAX_FIELDS
from apps.users.mentor_registration import MENTOR_EMAIL_TAKEN
from apps.users.models import EmailVerification, MentorProfile, SupervisorProfile, User
from apps.users.serializers import GUARDIAN_IS_SELF, GUARDIAN_IS_STUDENT, PLACEHOLDER_EMAIL, SUPERVISOR_IS_SELF
from tests.apps.users.test_email_verification import QevTestCase, qev
from tests.apps.users.test_registration_email_warnings import answer
from tests.apps.users.test_registration_email_rules import GUARDIAN_INVALID, STUDENT_INVALID
from tests.apps.users.test_registration_latelink import RegistrationSetup
from tests.apps.users.test_registration_mentor import mentor_body
from tests.apps.users.test_returning import _last_years_student

URL = "/api/v1/registration/email-check/field/"
NEW = "new.person@example.test"


def ok():
    return {"ok": True}


def problem(code, message):
    return {"ok": False, "code": code, "message": message}


class FieldCheckSetup(RegistrationSetup):
    def setUp(self):
        super().setUp()
        # Any lookup a test doesn't set up says the address exists.
        self.answer_always(qev())

    def check(self, *fields, client=None, **extra):
        return (client or self.client).post(URL, {"fields": list(fields), **extra}, format="json")

    def one(self, kind, email, student_email=None):
        field = {"field": "box", "kind": kind, "email": email}
        if student_email is not None:
            field["studentEmail"] = student_email
        result = self.check(field)
        self.assertEqual(result.status_code, 200, result.data)
        return result.data["results"]["box"]

    def lookups(self):
        return self.http.call_count

    def supervisor(self, email="sam.teacher@example.test"):
        user = User.objects.create_user(email=email)
        SupervisorProfile.objects.create(user=user, school_name="Example High")
        return email

    def current_student(self, email="current@students.example.test"):
        from apps.submissions.services import current_cohort

        _, profile = _last_years_student(email, account_status=User.AccountStatus.ACTIVE)
        profile.challenge_year = current_cohort()
        profile.save(update_fields=["challenge_year"])
        return email


class StudentTests(FieldCheckSetup, QevTestCase):
    def test_format(self):
        self.assertEqual(self.one("student", "not-an-email"), problem("invalid", "Enter a valid email address."))
        self.assertEqual(self.one("student", ""), problem("blank", "This field may not be blank."))
        self.assertEqual(self.lookups(), 0)

    def test_placeholder(self):
        self.assertEqual(self.one("student", "kid@example.invalid"), problem("placeholder_email", PLACEHOLDER_EMAIL))
        self.assertEqual(self.lookups(), 0)

    def test_existing_accounts(self):
        supervisor = self.supervisor()
        User.objects.create_user(email="taken@example.test")
        _last_years_student("last.year@students.example.test")

        self.assertEqual(self.one("student", supervisor.upper())["code"], "student_email_is_supervisor")
        self.assertEqual(
            self.one("student", "taken@example.test"),
            problem("email_taken", "An account with this email address already exists."),
        )
        self.assertEqual(self.one("student", "last.year@students.example.test"), ok())

    def test_an_account_problem_comes_before_the_mailbox(self):
        User.objects.create_user(email="taken@example.test")
        answer("taken@example.test")

        self.assertEqual(self.one("student", "taken@example.test")["code"], "email_taken")

    def test_mailbox(self):
        self.answer_always(qev("invalid", "rejected_email", did_you_mean="new.person@example.org"))

        self.assertEqual(self.one("student", NEW), problem(
            "email_invalid_address",
            "This email address doesn't appear to exist. Did you mean new.person@example.org? Please correct it.",
        ))


class GuardianTests(FieldCheckSetup, QevTestCase):
    def test_blank_says_nothing(self):
        self.assertEqual(self.one("guardian", ""), ok())
        self.assertEqual(self.one("guardian", "  "), ok())
        self.assertEqual(self.lookups(), 0)

    def test_format_then_placeholder_then_the_student_themselves(self):
        self.assertEqual(self.one("guardian", "nope", "nope")["code"], "invalid")
        self.assertEqual(self.one("guardian", "kid@example.invalid", "kid@example.invalid")["code"], "placeholder_email")
        self.assertEqual(
            self.one("guardian", "Kid@Example.test", " kid@example.test "),
            problem("guardian_same_as_student", GUARDIAN_IS_SELF),
        )
        self.assertEqual(self.lookups(), 0)

    def test_the_student_themselves_comes_before_a_current_student(self):
        email = self.current_student()

        self.assertEqual(self.one("guardian", email, email)["code"], "guardian_same_as_student")

    def test_a_current_student_is_a_problem_and_other_accounts_are_not(self):
        email = self.current_student()
        _last_years_student("last.year@students.example.test")
        supervisor = self.supervisor()
        User.objects.create_user(email="no.role@example.test")

        self.assertEqual(
            self.one("guardian", email, "kid@example.test"), problem("guardian_email_is_student", GUARDIAN_IS_STUDENT),
        )
        # These only warn at Submit, so say nothing here.
        for other in ("last.year@students.example.test", supervisor, "no.role@example.test"):
            with self.subTest(account=other):
                self.assertEqual(self.one("guardian", other, "kid@example.test"), ok())

    def test_mailbox(self):
        answer(NEW)

        self.assertEqual(self.one("guardian", NEW, "kid@example.test"), problem("email_invalid_address", GUARDIAN_INVALID))
        self.assertEqual(self.lookups(), 0)


class SupervisorTests(FieldCheckSetup, QevTestCase):
    def test_blank_says_nothing(self):
        self.assertEqual(self.one("supervisor", ""), ok())

    def test_format_then_placeholder_then_the_student_themselves(self):
        self.assertEqual(self.one("supervisor", "nope")["code"], "invalid")
        self.assertEqual(self.one("supervisor", "sam@example.invalid", "sam@example.invalid")["code"], "placeholder_email")
        self.assertEqual(
            self.one("supervisor", "kid@example.test", "KID@example.test"),
            problem("supervisor_same_as_student", SUPERVISOR_IS_SELF),
        )

    def test_role_clashes(self):
        student = self.current_student()
        User.objects.create_user(email="no.role@example.test")
        supervisor = self.supervisor()

        self.assertEqual(self.one("supervisor", student, "kid@example.test")["code"], "supervisor_email_is_student")
        self.assertEqual(self.one("supervisor", "no.role@example.test", "kid@example.test")["code"], "supervisor_email_in_use")
        self.assertEqual(self.one("supervisor", supervisor, "kid@example.test"), ok())

    def test_a_role_clash_comes_before_the_mailbox(self):
        User.objects.create_user(email="no.role@example.test")
        answer("no.role@example.test")

        self.assertEqual(self.one("supervisor", "no.role@example.test")["code"], "supervisor_email_in_use")

    def test_mailbox(self):
        answer(NEW, did_you_mean="new.person@example.org")

        self.assertEqual(self.one("supervisor", NEW, "kid@example.test"), problem(
            "email_invalid_address",
            "The supervisor's email address doesn't appear to exist. Did you mean new.person@example.org? "
            "Please correct it.",
        ))


class MentorTests(FieldCheckSetup, QevTestCase):
    def test_format_then_placeholder(self):
        self.assertEqual(self.one("mentor", "nope")["code"], "invalid")
        self.assertEqual(self.one("mentor", "m@example.invalid"), problem("placeholder_email", PLACEHOLDER_EMAIL))

    def test_an_existing_account_unless_a_mentor_back_for_a_later_year(self):
        User.objects.create_user(email="taken@example.test")
        returning = User.objects.create_user(
            email="back@example.test", account_status=User.AccountStatus.DEACTIVATED,
        )
        MentorProfile.objects.create(user=returning, institution="Uni", mentor_reason="Help", max_group_count=1)

        self.assertEqual(self.one("mentor", "Taken@example.test"), problem("email_taken", MENTOR_EMAIL_TAKEN))
        self.assertEqual(self.one("mentor", "back@example.test"), ok())

    def test_an_existing_account_comes_before_the_mailbox(self):
        User.objects.create_user(email="taken@example.test")
        answer("taken@example.test")

        self.assertEqual(self.one("mentor", "taken@example.test")["code"], "email_taken")

    def test_mailbox(self):
        answer(NEW)

        self.assertEqual(self.one("mentor", NEW), problem("email_invalid_address", STUDENT_INVALID))


class MailboxTests(FieldCheckSetup, QevTestCase):
    def test_answers_on_file_are_used_without_a_lookup(self):
        answer("invalid@example.test")
        answer("valid@example.test", "valid")
        answer("unknown@example.test", "unknown")

        self.assertEqual(self.one("student", "invalid@example.test")["code"], "email_invalid_address")
        self.assertEqual(self.one("student", "valid@example.test"), ok())
        self.assertEqual(self.one("student", "unknown@example.test"), ok())
        self.assertEqual(self.lookups(), 0)

    def test_an_answer_too_old_is_looked_up_again_and_stored(self):
        answer(NEW, "valid", days_old=200)
        self.answer_always(qev("invalid", "rejected_email"))

        self.assertEqual(self.one("student", NEW)["code"], "email_invalid_address")
        self.assertEqual(self.lookups(), 1)
        self.assertEqual(EmailVerification.objects.get(email=NEW).status, "invalid")

    def test_a_live_answer(self):
        for status, said in (("invalid", "email_invalid_address"), ("unknown", None), ("valid", None)):
            with self.subTest(status=status):
                address = f"{status}@example.test"
                self.answer_always(qev(status, "rejected_email" if status == "invalid" else "accepted_email"))
                result = self.one("student", address)
                self.assertEqual(result.get("code"), said)
                self.assertEqual(EmailVerification.objects.get(email=address).status, status)

    def test_an_error_says_nothing_and_stores_nothing(self):
        self.answer_always(status=500)

        self.assertEqual(self.one("student", NEW), ok())
        self.assertFalse(EmailVerification.objects.exists())

    @override_settings(QEV_API_KEY="", QEV_PAID_API_KEY="")
    def test_no_key_says_nothing(self):
        self.assertEqual(self.one("student", NEW), ok())
        self.assertEqual(self.lookups(), 0)

    @override_settings(QEV_DAILY_LOOKUP_CAP=1)
    def test_a_lookup_past_the_cap_says_nothing(self):
        self.answer_always(qev("invalid", "rejected_email"))

        result = self.check(
            {"field": "a", "kind": "student", "email": "first@example.test"},
            {"field": "b", "kind": "student", "email": "second@example.test"},
        )

        self.assertEqual(result.data["results"]["a"]["code"], "email_invalid_address")
        self.assertEqual(result.data["results"]["b"], ok())
        self.assertEqual(self.lookups(), 1)

    def test_an_address_in_several_boxes_is_looked_up_once(self):
        self.answer_always(qev("invalid", "rejected_email"))

        result = self.check(
            {"field": "students.0.guardian.email", "kind": "guardian", "email": NEW, "studentEmail": "a@example.test"},
            {"field": "students.1.guardian.email", "kind": "guardian", "email": NEW.upper(), "studentEmail": "b@example.test"},
            {"field": "supervisor.email", "kind": "supervisor", "email": f" {NEW} ", "studentEmail": "a@example.test"},
        )

        self.assertEqual(
            [value["code"] for value in result.data["results"].values()], ["email_invalid_address"] * 3,
        )
        self.assertEqual(self.lookups(), 1)

    @override_settings(EMAIL_PRECHECK_ENABLED=True)
    def test_whichever_way_the_pre_check_switch_is_set(self):
        answer(NEW)
        self.assertEqual(self.one("student", NEW)["code"], "email_invalid_address")
        with override_settings(EMAIL_PRECHECK_ENABLED=False):
            self.assertEqual(self.one("student", NEW)["code"], "email_invalid_address")

    def test_submit_reads_the_answer_the_check_stored(self):
        self.answer_always(qev("invalid", "rejected_email"))
        self.assertEqual(self.one("student", "jordan.lee@example.com")["code"], "email_invalid_address")
        self.answer_always(status=500)

        submitted = self.submit()

        self.assertEqual(submitted.status_code, 400, submitted.data)
        self.assertEqual(submitted.data["fields"]["students.0.email"], [STUDENT_INVALID])
        self.assertEqual(self.lookups(), 1)


class RequestTests(FieldCheckSetup, QevTestCase):
    def test_one_result_per_field_echoing_its_path(self):
        result = self.check(
            {"field": "students.0.email", "kind": "student", "email": NEW},
            {"field": "students.0.guardian.email", "kind": "guardian", "email": "", "studentEmail": NEW},
            journey="student_individual",
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data, {"results": {"students.0.email": ok(), "students.0.guardian.email": ok()}})

    def test_signed_out_needs_no_csrf_token(self):
        result = self.check({"field": "f", "kind": "student", "email": NEW}, client=APIClient(enforce_csrf_checks=True))
        self.assertEqual(result.status_code, 200, result.data)

    def test_signed_in_works_as_the_registration_endpoint_does(self):
        signed_in = APIClient(enforce_csrf_checks=True)
        signed_in.force_login(self.staff)
        field = {"field": "f", "kind": "student", "email": NEW}

        self.assertEqual(self.check(field, client=signed_in).status_code, 403)
        self.assertEqual(self.submit(client=signed_in).status_code, 403)
        self.assertEqual(self.check(field, client=self.staff_client).status_code, 200)

    def test_answers_while_registration_is_closed(self):
        self.close_window()

        self.assertEqual(self.one("student", NEW), ok())

    def test_a_malformed_request_is_refused(self):
        field = {"field": "f", "kind": "student", "email": NEW}
        for name, body in (
            ("not an object", ["x"]),
            ("no fields", {}),
            ("empty", {"fields": []}),
            ("unknown kind", {"fields": [{**field, "kind": "teacher"}]}),
            ("unknown key", {"fields": [{**field, "extra": 1}]}),
            ("unknown journey", {"journey": "nope", "fields": [field]}),
            ("same field twice", {"fields": [field, field]}),
            ("too many", {"fields": [{**field, "field": str(n)} for n in range(MAX_FIELDS + 1)]}),
        ):
            with self.subTest(name):
                result = self.client.post(URL, body, format="json")
                self.assertEqual(result.status_code, 400, result.data)
                self.assertIn("fields", result.data)
        self.assertEqual(self.check(*[{**field, "field": str(n)} for n in range(MAX_FIELDS)]).status_code, 200)


class MentorSubmitTests(RegistrationSetup, TestCase):
    def test_a_placeholder_address_is_refused(self):
        Roles.objects.get_or_create(role_name="mentor")

        refused = self.submit(body=mentor_body(email="mentor@example.invalid"))

        self.assertEqual(refused.status_code, 400, refused.data)
        self.assertEqual(refused.data["fields"]["mentor.email"], [PLACEHOLDER_EMAIL])
        self.assertFalse(User.objects.filter(email__iexact="mentor@example.invalid").exists())
        self.assertEqual(self.submit(body=mentor_body()).status_code, 201)
