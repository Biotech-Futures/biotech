"""Registration checks its addresses with QuickEmailVerification once it's
saved (apps.users.registration_intake.check_addresses_after_commit), when
EMAIL_VERIFICATION_ENABLED is on.

No test here makes a network call: the checks' HTTP is patched to fail any
request a test hasn't set up, and most tests stop at the scheduled batch."""
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings

from apps.users import email_verification
from apps.users.models import EmailVerification, RegistrationInvitation, User
from apps.users.registration_intake import checked_addresses, save_student
from tests.apps.users.test_email_verification import qev, response
from tests.apps.users.test_registration_latelink import request_body
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch, student

# What runs once a registration commits: the batch handed to the checker.
DISPATCH = "apps.users.email_verification._dispatch"


@override_settings(EMAIL_VERIFICATION_ENABLED=True)
class RegistrationEmailCheckTestCase(MultiStudentSetup, TestCase):
    def setUp(self):
        super().setUp()
        get = patch.object(email_verification.requests, "get", side_effect=AssertionError("unexpected HTTP call"))
        self.http = get.start()
        self.addCleanup(get.stop)
        send = patch.object(requests.Session, "send", side_effect=AssertionError("real network call"))
        send.start()
        self.addCleanup(send.stop)

    def register(self, body=None, *, expect=201, **kwargs):
        """Register, run what's queued for after the commit, and return the
        batches handed to the checker."""
        with patch(DISPATCH) as dispatch, self.captureOnCommitCallbacks(execute=True):
            result = self.post_batch(body or self.body, **kwargs)
        self.assertEqual(result.status_code, expect, getattr(result, "data", result))
        return [call.args[0] for call in dispatch.call_args_list]


class WhenTests(RegistrationEmailCheckTestCase):
    def test_nothing_is_checked_until_the_registration_commits(self):
        with patch(DISPATCH) as dispatch:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                self.assertEqual(self.post_batch(self.body).status_code, 201)
            dispatch.assert_not_called()

            for callback in callbacks:
                callback()

        dispatch.assert_called_once_with(["jordan.lee@example.com", "guardian@example.com"])

    def test_an_unchanged_retry_checks_nothing_more(self):
        key = "3f6c2a54-7e0b-4f59-9d1e-0c1b2a3d4e5f"

        self.assertEqual(len(self.register(key=key)), 1)
        self.assertEqual(self.register(key=key, expect=200), [])

    def test_a_late_link_taken_meanwhile_checks_nothing(self):
        self.close_window()
        invite = self.mint()

        def revoked_meanwhile(*args, **kwargs):
            user = save_student(*args, **kwargs)
            RegistrationInvitation.objects.filter(pk=invite["id"]).update(revoked_at=email_verification.timezone.now())
            return user

        with patch("apps.users.registration_intake.save_student", side_effect=revoked_meanwhile):
            self.assertEqual(self.register(token=invite["token"], expect=409), [])

    def test_a_registration_rolled_back_after_scheduling_checks_nothing(self):
        with patch("apps.users.registration_intake.receipt", side_effect=RuntimeError("late failure")), \
                patch(DISPATCH) as dispatch, self.captureOnCommitCallbacks(execute=True):
            # The project's exception handler answers an unexpected error with a 500.
            self.assertEqual(self.post_batch(self.body).status_code, 500)

        dispatch.assert_not_called()
        self.assertFalse(User.objects.filter(email="jordan.lee@example.com").exists())

    def test_a_refused_registration_checks_nothing(self):
        self.close_window()

        self.assertEqual(self.register(expect=400), [])

    @override_settings(EMAIL_VERIFICATION_ENABLED=False)
    def test_nothing_is_checked_while_the_switch_is_off(self):
        with patch("apps.users.registration_intake.verify_after_commit") as schedule:
            self.assertEqual(self.register(), [])

        schedule.assert_not_called()


class AddressTests(RegistrationEmailCheckTestCase):
    def test_a_student_on_their_own_and_their_guardian(self):
        self.assertEqual(self.register(), [["jordan.lee@example.com", "guardian@example.com"]])

    def test_a_team_checks_every_student_and_each_guardian_given(self):
        # The creator names a guardian; their teammates' are left for later.
        (addresses,) = self.register(batch("student_team", 3))

        self.assertEqual(addresses, [
            "learner0@students.example.test", "parent0@guardians.example.test",
            "learner1@students.example.test", "learner2@students.example.test",
        ])

    def test_a_shared_guardian_is_checked_once_and_its_casing_doesnt_matter(self):
        body = batch("supervisor_group", 3)
        for index, item in enumerate(body["payload"]["students"]):
            if index < 2:
                item.update(guardianDeferred=False, guardian={
                    **request_body()["payload"]["students"][0]["guardian"], "email": " Shared.Parent@Example.TEST ",
                })

        (addresses,) = self.register(body)

        self.assertEqual(addresses, [
            "learner0@students.example.test", "shared.parent@example.test",
            "learner1@students.example.test", "learner2@students.example.test",
        ])

    def test_a_500_row_csv_is_one_batch_deduped_with_blanks_dropped(self):
        body = batch("supervisor_csv", 500)
        for index, item in enumerate(body["payload"]["students"]):
            if index % 2 == 0:
                # Two students to a family; every other student's guardian is left for later.
                item.update(guardianDeferred=False, guardian={
                    **request_body()["payload"]["students"][0]["guardian"],
                    "email": f"family{index // 4}@guardians.example.test",
                })

        (addresses,) = self.register(body)

        students = [f"learner{index}@students.example.test" for index in range(500)]
        families = [f"family{index}@guardians.example.test" for index in range(125)]
        self.assertEqual(len(addresses), 625)
        self.assertEqual(sorted(addresses), sorted(students + families))
        self.assertEqual(addresses[:3], [students[0], families[0], students[1]])
        self.assertNotIn("", addresses)

    def test_a_student_who_confirmed_their_email_past_the_warning_isnt_checked_but_their_guardian_is(self):
        self.body["payload"]["students"][0]["overrides"] = {"ConfirmNameEmailOverride": True}

        self.assertEqual(self.register(), [["guardian@example.com"]])

    def test_confirming_only_the_school_still_checks_the_students_email(self):
        self.body["payload"]["students"][0]["overrides"] = {"ConfirmSchoolOverride": True}

        self.assertEqual(self.register(), [["jordan.lee@example.com", "guardian@example.com"]])

    def test_a_legacy_registration_honours_the_override_too(self):
        body = {"body": {
            "Title": "jordan.lee@example.com", "FirstName": "Jordan", "Surname": "Lee",
            "Country": "Australia", "Region": "NSW", "SchoolName": "Example High", "YearLevel": "10",
            "Areaofinterest": "Biotechnology", "GuardianEmail": "guardian@example.com",
            "GuardianName": "Taylor", "GuardianSurname": "Lee", "ConfirmNameEmailOverride": True,
        }}
        with patch(DISPATCH) as dispatch, self.captureOnCommitCallbacks(execute=True):
            result = self.client.post("/api/v1/registration", body, format="json")

        self.assertEqual(result.status_code, 200, result.data)
        dispatch.assert_called_once_with(["guardian@example.com"])

    def test_the_address_list_on_its_own(self):
        def entry(email, guardian="", **overrides):
            return {"email": email, "guardian": {"email": guardian} if guardian else {}, "overrides": overrides}

        self.assertEqual(checked_addresses([
            entry("a@example.com", "Parent@Example.com"),
            entry("b@example.com", "parent@example.com"),
            entry("c@example.com", "   "),
            entry("a@example.com"),
            entry("d@example.com", "d.parent@example.com", ConfirmNameEmailOverride=True),
            entry("e@example.com", ConfirmNameEmailOverride=False),
        ]), [
            "a@example.com", "parent@example.com", "b@example.com", "c@example.com",
            "d.parent@example.com", "e@example.com",
        ])


class FailureTests(RegistrationEmailCheckTestCase):
    def test_registration_still_succeeds_if_scheduling_the_check_fails(self):
        with patch("apps.users.registration_intake.verify_after_commit", side_effect=RuntimeError("boom")), \
                self.assertLogs("apps.users.registration_intake", "ERROR") as logs:
            self.register()

        self.assertTrue(User.objects.filter(email="jordan.lee@example.com").exists())
        self.assertEqual(logs.output, [
            "ERROR:apps.users.registration_intake:registration.email_check_not_scheduled error=RuntimeError",
        ])

    def test_registration_still_succeeds_if_building_the_list_fails(self):
        with patch("apps.users.registration_intake.checked_addresses", side_effect=KeyError("overrides")):
            self.register()

        self.assertTrue(User.objects.filter(email="jordan.lee@example.com").exists())

    def test_end_to_end_the_answers_are_stored_with_the_http_mocked(self):
        self.http.side_effect = [response(qev("valid")), response(qev("invalid", "rejected_email"))]

        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post_batch(self.body).status_code, 201)

        self.assertEqual(self.http.call_count, 2)
        self.assertEqual(
            dict(EmailVerification.objects.values_list("email", "status")),
            {"jordan.lee@example.com": "valid", "guardian@example.com": "invalid"},
        )
