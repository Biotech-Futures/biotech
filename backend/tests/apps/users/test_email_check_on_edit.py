"""Checking an address saved outside registration (EMAIL_CHECK_ON_EDIT):
email_verification.check_one_address, an admin editing a user, and a student
changing their guardian. All HTTP is mocked with the dummy test keys.

TransactionTestCase, because TestCase wraps every test in a transaction and
the check makes no live lookup inside one."""
from datetime import timedelta
from unittest import mock

import requests
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.admin.services.user import update_user
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users import email_verification as ev
from apps.users.email_precheck import _busy_key
from apps.users.models import AreasOfInterest, EmailVerification, StudentProfile, User, UserInterest
from tests.apps.users.test_email_verification import qev, response
from tests.apps.users.test_registration_latelink import RegistrationSetup

ON = dict(
    EMAIL_CHECK_ON_EDIT=True, QEV_API_KEY="test-dummy-key", QEV_PAID_API_KEY="", QEV_USE_SANDBOX=False,
    QEV_TIMEOUT_SECONDS=5, QEV_RESULT_MAX_AGE_DAYS=180, QEV_DAILY_LOOKUP_CAP=0,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)


class MockedQev:
    def setUp(self):
        super().setUp()
        cache.clear()
        get = mock.patch.object(ev.requests, "get", side_effect=AssertionError("unexpected HTTP call"))
        self.http = get.start()
        self.addCleanup(get.stop)
        send = mock.patch.object(requests.Session, "send", side_effect=AssertionError("real network call"))
        send.start()
        self.addCleanup(send.stop)

    def answer(self, body):
        self.http.side_effect = None
        self.http.return_value = response(body)

    def on_file(self, email, status, did_you_mean=""):
        EmailVerification.objects.create(
            email=email, status=status, reason="test", did_you_mean=did_you_mean, checked_at=timezone.now(),
        )


@override_settings(**ON)
class CheckOneAddressTests(MockedQev, TransactionTestCase):
    @override_settings(EMAIL_CHECK_ON_EDIT=False)
    def test_switched_off_it_does_nothing(self):
        self.on_file("gone@example.com", "invalid")
        self.assertIsNone(ev.check_one_address("gone@example.com"))
        self.http.assert_not_called()

    def test_a_blank_or_unchanged_address_is_not_checked(self):
        self.assertIsNone(ev.check_one_address(""))
        self.assertIsNone(ev.check_one_address(" Pat@Example.com ", current="pat@example.com"))
        self.http.assert_not_called()

    def test_an_invalid_answer_on_file_fails_without_a_lookup(self):
        self.on_file("gone@example.com", "invalid", did_you_mean="gone@example.org")
        result = ev.check_one_address("Gone@Example.com", current="old@example.com")
        self.assertEqual((result.status, result.cached), ("invalid", True))
        self.assertEqual(
            ev.invalid_address_message(result),
            "This email address doesn't appear to exist. Did you mean gone@example.org?",
        )
        self.http.assert_not_called()

    def test_a_valid_answer_on_file_passes_without_a_lookup(self):
        self.on_file("kid@example.com", "valid")
        self.assertIsNone(ev.check_one_address("kid@example.com"))
        self.http.assert_not_called()

    def test_unknown_and_error_answers_pass(self):
        self.on_file("maybe@example.com", "unknown")
        self.answer(qev("unknown", "timeout"))
        self.assertIsNone(ev.check_one_address("maybe@example.com"))
        self.http.side_effect = requests.Timeout("slow")
        self.assertIsNone(ev.check_one_address("slow@example.com"))
        self.assertFalse(EmailVerification.objects.filter(email="slow@example.com").exists())

    def test_a_live_invalid_answer_fails_with_one_lookup(self):
        self.answer(qev("invalid", "rejected_email", did_you_mean="kid@gmail.com"))
        result = ev.check_one_address("kid@gmial.com")
        self.assertEqual((result.status, result.did_you_mean, result.cached), ("invalid", "kid@gmail.com", False))
        self.assertEqual(self.http.call_count, 1)
        self.assertEqual(EmailVerification.objects.get(email="kid@gmial.com").status, "invalid")

    def test_a_live_unknown_answer_passes(self):
        self.answer(qev("unknown", "no_connect"))
        self.assertIsNone(ev.check_one_address("maybe@example.com"))
        self.assertEqual(self.http.call_count, 1)

    def test_inside_a_transaction_only_the_answer_on_file_counts(self):
        self.on_file("gone@example.com", "invalid")
        with transaction.atomic(), self.assertLogs("apps.users.email_verification", "WARNING"):
            self.assertIsNone(ev.check_one_address("new@example.com"))
            self.assertEqual(ev.check_one_address("gone@example.com").status, "invalid")
        self.http.assert_not_called()

    def test_an_address_another_check_is_paying_for_is_not_looked_up_again(self):
        cache.add(_busy_key("busy@example.com"), 1, 60)
        self.assertIsNone(ev.check_one_address("busy@example.com"))
        self.http.assert_not_called()

    def test_a_crash_lets_the_save_go_ahead(self):
        with mock.patch.object(ev, "verify_email", side_effect=RuntimeError("boom")):
            self.assertIsNone(ev.check_one_address("kid@example.com"))


def _student():
    user = User.objects.create_user(email="ward@example.com", first_name="Wren", last_name="Ward")
    RoleAssignmentHistory.objects.create(
        user=user, role=Roles.objects.get_or_create(role_name="student")[0],
        valid_from=timezone.now() - timedelta(days=1),
    )
    StudentProfile.objects.create(
        user=user, pg_first_name="Pat", pg_last_name="Parent", pg_email="pat@example.com",
        parent_guardian_flag=True, school_name="Test High", year_lvl="10",
    )
    UserInterest.objects.create(user=user, interest=AreasOfInterest.objects.create(interest_desc="Biotech"))
    return user


@override_settings(**ON)
class AdminEditTests(MockedQev, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(email="admin@example.com")
        self.student = _student()

    def update(self, **fields):
        return update_user(self.student.id, fields, initiated_by=self.admin)

    def test_a_new_email_that_doesnt_exist_is_refused(self):
        self.answer(qev("invalid", "rejected_email", did_you_mean="wren@gmail.com"))
        result = self.update(email="wren@gmial.com")
        self.assertEqual(result, {
            "msg": "This email address doesn't appear to exist. Did you mean wren@gmail.com?", "data": None,
        })
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "ward@example.com")
        self.assertEqual(self.http.call_count, 1)

    def test_a_new_email_that_exists_is_saved_after_one_lookup(self):
        self.answer(qev("valid"))
        self.assertIsNotNone(self.update(email="wren@example.com")["data"])
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "wren@example.com")
        self.assertEqual(self.http.call_count, 1)

    def test_a_guardian_email_that_doesnt_exist_is_refused(self):
        self.on_file("parent@exmaple.com", "invalid", did_you_mean="parent@example.com")
        result = self.update(guardianEmail="parent@exmaple.com")
        self.assertEqual(
            result["msg"],
            "The guardian's email address doesn't appear to exist. Did you mean parent@example.com?",
        )
        self.assertEqual(StudentProfile.objects.get(user=self.student).pg_email, "pat@example.com")

    def test_unchanged_addresses_are_not_checked(self):
        self.assertIsNotNone(self.update(email="Ward@example.com", guardianEmail="PAT@example.com", schoolName="New High")["data"])
        self.http.assert_not_called()

    @override_settings(EMAIL_CHECK_ON_EDIT=False)
    def test_switched_off_nothing_is_checked(self):
        self.on_file("gone@example.com", "invalid")
        self.assertIsNotNone(self.update(email="gone@example.com")["data"])
        self.http.assert_not_called()


@override_settings(**ON)
class StudentGuardianTests(MockedQev, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.student = _student()
        self.client = APIClient()
        self.client.force_authenticate(self.student)

    def put(self, email):
        return self.client.put(
            reverse("me-guardian"), {"first_name": "Robin", "last_name": "Carer", "email": email}, format="json",
        )

    def test_a_guardian_email_that_doesnt_exist_is_refused_on_its_field(self):
        self.answer(qev("invalid", "rejected_email"))
        response = self.put("robin@exmaple.com")
        self.assertEqual(response.status_code, 400, response.data)
        body = str(response.data)
        self.assertIn("email", body)
        self.assertIn("Your guardian's email address doesn't appear to exist.", body)
        self.assertEqual(StudentProfile.objects.get(user=self.student).pg_email, "pat@example.com")
        self.assertEqual(self.http.call_count, 1)

    def test_a_guardian_email_that_exists_is_saved_after_one_lookup(self):
        self.answer(qev("valid"))
        self.assertEqual(self.put("robin@example.com").status_code, 200)
        self.assertEqual(StudentProfile.objects.get(user=self.student).pg_email, "robin@example.com")
        self.assertEqual(self.http.call_count, 1)

    def test_the_same_guardian_again_is_not_checked(self):
        self.assertEqual(self.put("pat@example.com").status_code, 200)
        self.http.assert_not_called()


@override_settings(**ON)
class RegistrationUnaffectedTests(MockedQev, RegistrationSetup, TestCase):
    def test_registering_makes_no_lookup_with_the_switch_on(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)
        self.http.assert_not_called()
