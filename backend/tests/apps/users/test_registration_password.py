"""Setting a password straight after registering (apps.users.registration_password):
someone registering themselves gets a token with their receipt, which sets
their first password and signs them in."""
import time
from unittest.mock import patch

from django.test import TestCase

from apps.resources.models import Roles
from apps.users.models import RegistrationSubmission, User
from apps.users.registration_password import MAX_AGE_SECONDS
from tests.apps.users.test_registration_latelink import RegistrationSetup
from tests.apps.users.test_registration_mentor import mentor_body
from tests.apps.users.test_registration_supervisor import supervisor_body

PASSWORD = "/api/v1/registration/password/"


class RegistrationPasswordTests(RegistrationSetup, TestCase):
    def setUp(self):
        super().setUp()
        Roles.objects.get_or_create(role_name="mentor")

    def registered(self, body=None):
        with patch("apps.users.registration_emails.send_system_email"):
            response = self.submit(body=body)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def set_password(self, token, password="a-good-password"):
        return self.client.post(PASSWORD, {"token": token, "password": password}, format="json")

    def just_past_the_hour(self, receipt):
        """A second past the token's hour, counted from when the registration
        was saved: the time its token is signed with, on the app's clock,
        which the moved-clock runs move and time.time() doesn't."""
        registered_at = RegistrationSubmission.objects.get(reference=receipt["reference_code"]).created_at
        return registered_at.timestamp() + MAX_AGE_SECONDS + 1

    def test_a_student_sets_their_password_and_is_signed_in(self):
        receipt = self.registered()
        self.assertTrue(receipt["passwordToken"])
        response = self.set_password(receipt["passwordToken"])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["signedIn"])
        self.assertTrue(response.data["csrfToken"])
        user = User.objects.get(email="jordan.lee@example.com")
        self.assertTrue(user.check_password("a-good-password"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        # Signed in: their own details load.
        self.assertEqual(self.client.get("/api/v1/users/me/").status_code, 200)

    def test_a_supervisor_too(self):
        receipt = self.registered(supervisor_body())
        response = self.set_password(receipt["passwordToken"])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["signedIn"])

    def test_a_mentor_sets_theirs_but_waits_to_be_activated(self):
        receipt = self.registered(mentor_body())
        response = self.set_password(receipt["passwordToken"])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {"signedIn": False})
        user = User.objects.get(email="jordan.ng@uni.example.test")
        self.assertTrue(user.check_password("a-good-password"))
        self.assertEqual(user.account_status, User.AccountStatus.PENDING)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_once_only_and_at_least_eight_characters(self):
        receipt = self.registered()
        response = self.set_password(receipt["passwordToken"], "short")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data["fields"])
        self.assertEqual(self.set_password(receipt["passwordToken"]).status_code, 200)
        # Set: the reset link changes it, not this.
        again = self.set_password(receipt["passwordToken"], "another-password")
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data["error"], "Your password is already set. Sign in with it.")
        self.assertTrue(User.objects.get(email="jordan.lee@example.com").check_password("a-good-password"))

    def test_a_retry_a_moment_later_gets_the_very_same_token(self):
        key = "0b3c5a4e-8f61-4d2a-9c7e-5f1a2b3c4d5e"
        with patch("apps.users.registration_emails.send_system_email"):
            first = self.submit(key=key)
            later = time.time() + 5
            with patch("django.core.signing.time.time", return_value=later):
                again = self.submit(key=key)
        self.assertEqual(again.data["passwordToken"], first.data["passwordToken"])

    def test_the_hour_counts_from_registering(self):
        receipt = self.registered()
        later = self.just_past_the_hour(receipt)
        with patch("django.core.signing.time.time", return_value=later):
            response = self.set_password(receipt["passwordToken"])
        self.assertEqual(response.status_code, 400)

    def test_a_made_up_or_expired_token_is_refused(self):
        receipt = self.registered()
        token = receipt["passwordToken"]
        for bad in ("", "123:abc", token[:-1] + ("A" if token[-1] != "A" else "B")):
            with self.subTest(token=bad):
                self.assertEqual(self.set_password(bad).status_code, 400)
        later = self.just_past_the_hour(receipt)
        with patch("django.core.signing.time.time", return_value=later):
            response = self.set_password(token)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.get(email="jordan.lee@example.com").has_usable_password())

    def test_no_token_for_students_a_supervisor_registers(self):
        receipt = self.registered(supervisor_body())
        self.set_password(receipt["passwordToken"])
        # Signed in as that supervisor, they register a student.
        self.body["journey"] = "supervisor_individual"
        del self.body["payload"]["supervisor"]
        self.body["payload"]["source"] = {"method": "supervisor_individual"}
        self.body["payload"]["students"][0]["email"] = "pupil@example.com"
        receipt = self.registered()
        self.assertNotIn("passwordToken", receipt)

    def test_a_retry_gets_the_token_while_no_password_is_set(self):
        key = "6f1f8f8e-3b7a-4c1e-9a52-2b8f4c1d0e11"
        with patch("apps.users.registration_emails.send_system_email"):
            first = self.submit(key=key)
            again = self.submit(key=key)
        self.assertEqual(again.status_code, 200)
        # The same receipt, token and all, whenever the retry comes.
        self.assertEqual(again.data, first.data)
        self.assertEqual(self.set_password(first.data["passwordToken"]).status_code, 200)
        with patch("apps.users.registration_emails.send_system_email"):
            third = self.submit(key=key)
        self.assertNotIn("passwordToken", third.data)
