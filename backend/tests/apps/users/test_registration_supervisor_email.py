"""A supervisor registering themselves has their email checked as a mentor's
is: a placeholder or an address that doesn't exist is refused at Submit; one
that couldn't be checked, or looks like a typo of their name, is a warning
they confirm. The page checks the same as the box is left (supervisor_self),
at most so many times a minute."""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from apps.common.rbac import user_has_role
from apps.resources.models import Roles
from apps.users.models import SupervisorProfile, User
from apps.users.serializers import PLACEHOLDER_EMAIL
from apps.users.supervisor_registration import SUPERVISOR_EMAIL_TAKEN
from tests.apps.users.test_email_verification import QevTestCase, qev
from tests.apps.users.test_registration_email_field_check import (
    NEW, URL, FieldCheckSetup, ok, problem, warned,
)
from tests.apps.users.test_registration_email_rules import STUDENT_INVALID
from tests.apps.users.test_registration_email_warnings import answer
from tests.apps.users.test_registration_latelink import RegistrationSetup
from tests.apps.users.test_registration_supervisor import supervisor_body

SEND = "apps.users.registration_emails.send_system_email"
UNKNOWN = "This email address couldn't be verified. Please check it, or confirm if this is correct."
TYPO = "This email looks like it might have a typo compared to the supervisor's name. Please confirm."


class SupervisorSubmitTests(RegistrationSetup, TestCase):
    def setUp(self):
        super().setUp()
        Roles.objects.get_or_create(role_name="mentor")

    def register(self, **changes):
        with patch(SEND), self.captureOnCommitCallbacks(execute=True):
            return self.submit(body=supervisor_body(**changes))

    def test_a_placeholder_address_is_refused(self):
        refused = self.register(email="sam@example.invalid")

        self.assertEqual(refused.status_code, 400, refused.data)
        self.assertEqual(refused.data["fields"]["supervisor.email"], [PLACEHOLDER_EMAIL])
        self.assertFalse(User.objects.filter(email__iexact="sam@example.invalid").exists())

    def test_an_address_that_doesnt_exist_is_refused(self):
        answer("teacher@example.com")

        refused = self.register()

        self.assertEqual(refused.status_code, 400, refused.data)
        self.assertEqual(refused.data["fields"]["supervisor.email"], [STUDENT_INVALID])
        self.assertFalse(User.objects.filter(email__iexact="teacher@example.com").exists())

    def test_one_that_couldnt_be_checked_is_saved_once_confirmed(self):
        answer("teacher@example.com", "unknown")

        warned_first = self.register()
        self.assertEqual(warned_first.status_code, 400, warned_first.data)
        self.assertEqual(
            [(w["code"], w["field"], w["override_field"]) for w in warned_first.data["warnings"]],
            [("email_invalid", "supervisor.email", "supervisor.overrides.ConfirmEmailInvalidOverride")],
        )
        self.assertFalse(User.objects.filter(email__iexact="teacher@example.com").exists())

        saved = self.register(overrides={"ConfirmEmailInvalidOverride": True})
        self.assertEqual(saved.status_code, 201, saved.data)

    def test_a_typo_of_their_name_is_saved_once_confirmed(self):
        warned_first = self.register(email="samteachr@example.com")
        self.assertEqual(warned_first.status_code, 400, warned_first.data)
        self.assertEqual(
            [(w["message"], w["override_field"]) for w in warned_first.data["warnings"]],
            [(TYPO, "supervisor.overrides.ConfirmNameEmailOverride")],
        )

        saved = self.register(email="samteachr@example.com", overrides={"ConfirmNameEmailOverride": True})
        self.assertEqual(saved.status_code, 201, saved.data)

    def test_an_unknown_override_is_refused(self):
        refused = self.register(overrides={"ConfirmSchoolOverride": True})

        self.assertEqual(refused.status_code, 400, refused.data)
        self.assertIn("supervisor.overrides", refused.data["fields"])


class ReturningSupervisorTests(RegistrationSetup, TestCase):
    """A supervisor Start new year deactivated registers again: their account
    comes back, active, with this form's details."""

    def setUp(self):
        super().setUp()
        Roles.objects.get_or_create(role_name="mentor")
        self.old = User.objects.create_user(
            email="teacher@example.com", first_name="Old", last_name="Name",
            account_status=User.AccountStatus.DEACTIVATED, is_active=False,
        )
        SupervisorProfile.objects.create(user=self.old, school_name="Old School")

    def register(self, **changes):
        with patch(SEND), self.captureOnCommitCallbacks(execute=True):
            return self.submit(body=supervisor_body(**changes))

    def test_their_account_comes_back_with_the_new_details(self):
        response = self.register(school="New School")

        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email__iexact="teacher@example.com")
        self.assertEqual(user.pk, self.old.pk)
        self.assertEqual((user.first_name, user.last_name), ("Sam", "Teacher"))
        self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
        self.assertTrue(user.is_active)
        self.assertEqual(SupervisorProfile.objects.get(user=user).school_name, "New School")
        self.assertTrue(user_has_role(user, "supervisor"))
        self.assertEqual(User.objects.filter(email__iexact="teacher@example.com").count(), 1)

    def test_their_pronouns_stay_when_the_form_sends_none(self):
        # The registration page no longer asks for pronouns.
        self.old.pronouns = "she/her"
        self.old.save(update_fields=["pronouns"])

        response = self.register()

        self.assertEqual(response.status_code, 201, response.data)
        self.old.refresh_from_db()
        self.assertEqual(self.old.pronouns, "she/her")

    def test_someone_elses_deactivated_account_still_takes_the_address(self):
        other = User.objects.create_user(
            email="former.student@example.com", account_status=User.AccountStatus.DEACTIVATED, is_active=False,
        )

        refused = self.register(email=other.email)

        self.assertEqual(refused.status_code, 400, refused.data)
        self.assertEqual(refused.data["fields"]["supervisor.email"], [SUPERVISOR_EMAIL_TAKEN])


class SupervisorFieldTests(FieldCheckSetup, QevTestCase):
    def test_a_supervisor_back_for_a_later_year_is_not_taken(self):
        old = User.objects.create_user(
            email="back@example.test", account_status=User.AccountStatus.DEACTIVATED, is_active=False,
        )
        SupervisorProfile.objects.create(user=old, school_name="Old School")

        self.assertEqual(self.result(self.item("back@example.test")), ok())

    def item(self, email, **extra):
        return {"field": "box", "kind": "supervisor_self", "email": email, **extra}

    def result(self, item, **extra):
        response = self.check(item, **extra)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["results"]["box"]

    def test_format_placeholder_and_an_existing_account(self):
        User.objects.create_user(email="taken@example.test")

        self.assertEqual(self.result(self.item("nope"))["code"], "invalid")
        self.assertEqual(self.result(self.item("s@example.invalid")), problem("placeholder_email", PLACEHOLDER_EMAIL))
        self.assertEqual(
            self.result(self.item("Taken@example.test")), problem("email_taken", SUPERVISOR_EMAIL_TAKEN),
        )

    def test_a_mailbox_that_doesnt_exist_is_refused_as_at_submit(self):
        answer(NEW)

        self.assertEqual(self.result(self.item(NEW)), problem("email_invalid_address", STUDENT_INVALID))

    def test_warnings_at_their_own_place_then_ok_once_confirmed(self):
        answer("samteachr@example.test", "unknown")
        item = self.item("samteachr@example.test", firstName="Sam", lastName="Teacher")

        self.assertEqual(self.result(item, journey="supervisor"), warned(
            "email_invalid", UNKNOWN, "supervisor.email", "supervisor.overrides.ConfirmEmailInvalidOverride",
        ))
        item["overrides"] = {"ConfirmEmailInvalidOverride": True}
        self.assertEqual(self.result(item), warned(
            "name_email_mismatch", TYPO, "supervisor.email", "supervisor.overrides.ConfirmNameEmailOverride",
        ))
        item["overrides"]["ConfirmNameEmailOverride"] = True
        self.assertEqual(self.result(item), ok())

    def test_a_valid_new_address_is_ok(self):
        self.answer_always(qev("valid"))

        self.assertEqual(self.result(self.item("sam.teacher@example.test")), ok())


class FieldCheckLimitTests(FieldCheckSetup, QevTestCase):
    def test_at_most_thirty_checks_a_minute_from_one_person(self):
        cache.clear()
        item = {"field": "box", "kind": "student", "email": "jo@example.test"}
        for _ in range(30):
            self.assertEqual(self.check(item).status_code, 200)

        refused = self.client.post(URL, {"fields": [item]}, format="json")
        self.assertEqual(refused.status_code, 429)
