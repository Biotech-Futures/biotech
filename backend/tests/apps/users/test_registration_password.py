"""Setting a password straight after registering (apps.users.registration_password):
someone registering themselves gets a token with their receipt, which sets
their first password and signs them in. A student someone else registers is
emailed a link with one instead, and gives their guardian there if we don't
have them."""
import time
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.resources.models import RoleAssignmentHistory, Roles
from apps.services.system_email import render_system_email
from apps.users.models import RegistrationSubmission, StudentProfile, User
from apps.users.registration_password import EMAIL_MAX_AGE_SECONDS, MAX_AGE_SECONDS, needs_policies
from tests.apps.users.test_registration_latelink import RegistrationSetup
from tests.apps.users.test_registration_mentor import mentor_body
from tests.apps.users.test_registration_multi_student import MultiStudentSetup, batch, student
from tests.apps.users.test_registration_supervisor import supervisor_body

PASSWORD = "/api/v1/registration/password/"
SEND = "apps.users.registration_emails.send_system_email"


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

    def test_a_mentor_too_active_at_once(self):
        receipt = self.registered(mentor_body())
        response = self.set_password(receipt["passwordToken"])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["signedIn"])
        user = User.objects.get(email="jordan.ng@uni.example.test")
        self.assertTrue(user.check_password("a-good-password"))
        self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_an_account_that_isnt_active_sets_its_password_but_isnt_signed_in(self):
        receipt = self.registered(mentor_body())
        User.objects.get(email="jordan.ng@uni.example.test").mark_pending()
        response = self.set_password(receipt["passwordToken"])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {"signedIn": False})
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


class EmailedPasswordLinkTests(MultiStudentSetup, TestCase):
    """A student someone else registers (a teammate, their supervisor or an
    admin) is emailed a link to set their password, for 14 days, and gives
    their guardian there if we don't have them."""

    GUARDIAN = {"first_name": "Pat", "last_name": "Example", "email": "Pat@Guardians.example.test"}

    def links(self, body, client=None):
        """Each email's link to set a password, by who it went to (None: none)."""
        with patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            response = self.submit(body=body, client=client) if client else self.post_batch(body)
        self.assertEqual(response.status_code, 201, response.data)
        return {sent.args[1]: sent.args[2].get("SET_PASSWORD_URL") for sent in send.call_args_list}

    def teammate_link(self, body=None):
        body = body or batch("student_team")
        return self.links(body)[body["payload"]["students"][1]["email"]]

    @staticmethod
    def token(link):
        return parse_qs(urlsplit(link).fragment.partition("?")[2])["token"][0]

    def check(self, token):
        return self.client.get(PASSWORD, {"token": token})

    def set_password(self, token, guardian=None, *, agreed=True):
        body = {"token": token, "password": "a-good-password"}
        if guardian is not None:
            body["guardian"] = guardian
        if agreed:
            body["policiesAgreed"] = True
        return self.client.post(PASSWORD, body, format="json")

    def test_they_agree_to_the_policies_with_their_password(self):
        token = self.token(self.teammate_link())
        self.assertTrue(self.check(token).data["needsPolicies"])
        refused = self.set_password(token, self.GUARDIAN, agreed=False)
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(refused.data["fields"]["policiesAgreed"], ["Agree to the BIOTech Futures policies to continue."])
        teammate = User.objects.get(email="learner1@students.example.test")
        self.assertFalse(teammate.has_usable_password())
        self.assertIsNone(teammate.policies_agreed_at)

        self.assertEqual(self.set_password(token, self.GUARDIAN).status_code, 200)
        teammate.refresh_from_db()
        self.assertIsNotNone(teammate.policies_agreed_at)

    def test_first_sign_in_asks_the_same_of_someone_registered_by_others(self):
        body = batch("supervisor_individual")
        self.links(body)
        student = User.objects.get(email=body["payload"]["students"][0]["email"])
        client = APIClient()
        client.force_login(student)
        refused = client.post("/api/v1/set-password/", {"password": "a-good-password"}, format="json")
        self.assertEqual(refused.status_code, 400)
        self.assertIn("policiesAgreed", refused.data["fields"])
        student.refresh_from_db()
        self.assertFalse(student.has_usable_password())

        response = client.post(
            "/api/v1/set-password/", {"password": "a-good-password", "policiesAgreed": True}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        student.refresh_from_db()
        self.assertTrue(student.check_password("a-good-password"))
        self.assertIsNotNone(student.policies_agreed_at)
        # Read with their details, so the page knows not to ask again.
        self.assertTrue(client.get("/api/v1/users/me/").data["policies_agreed_at"])

    def test_not_asked_of_an_admin_or_someone_who_agreed_registering(self):
        admin = User.objects.create_user(email="first.admin@example.test", first_name="First", last_name="Admin")
        RoleAssignmentHistory.objects.create(
            user=admin, role=Roles.objects.get(role_name="admin"),
            valid_from=timezone.now() - timedelta(days=1), valid_to=timezone.now() + timedelta(days=30),
        )
        self.assertFalse(needs_policies(admin))
        # The person filling in a team's form agreed on it.
        body = batch("student_team")
        self.links(body)
        self.assertFalse(needs_policies(User.objects.get(email=body["payload"]["students"][0]["email"])))
        self.assertTrue(needs_policies(User.objects.get(email=body["payload"]["students"][1]["email"])))

    def test_a_teammate_is_emailed_a_link_but_not_the_one_who_registered_them(self):
        body = batch("student_team")
        links = self.links(body)
        first, second = (item["email"] for item in body["payload"]["students"])
        self.assertIsNone(links[first])
        self.assertTrue(links[second].startswith(f"{settings.FRONTEND_BASE_URL}/#/register/password?token="))

    def test_every_student_a_supervisor_or_an_admin_registers_is_too(self):
        body = batch("supervisor_group")
        links = self.links(body)
        for item in body["payload"]["students"]:
            self.assertTrue(links[item["email"]], item["email"])
        # Not the supervisor's own confirmation.
        self.assertIsNone(links["manager@example.test"])

        body = batch("supervisor_individual", offset=10)
        body["payload"]["supervisorEmail"] = "manager@example.test"
        links = self.links(body, client=self.staff_client)
        self.assertTrue(links[body["payload"]["students"][0]["email"]])

    def test_a_teammate_without_a_guardian_gives_them_with_their_password(self):
        token = self.token(self.teammate_link())
        check = self.check(token)
        self.assertEqual(check.status_code, 200, check.data)
        self.assertTrue(check.data["needsGuardian"])

        # Without them, or with their own email: refused, and no password set.
        self.assertEqual(self.set_password(token).status_code, 400)
        own = self.set_password(token, {**self.GUARDIAN, "email": "learner1@students.example.test"})
        self.assertEqual(own.status_code, 400)
        self.assertIn("email", own.data["fields"])
        teammate = User.objects.get(email="learner1@students.example.test")
        self.assertFalse(teammate.has_usable_password())

        with patch("apps.users.views.email_new_guardian") as consent:
            response = self.set_password(token, self.GUARDIAN)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["signedIn"])
        teammate.refresh_from_db()
        self.assertTrue(teammate.check_password("a-good-password"))
        profile = StudentProfile.objects.get(user=teammate)
        self.assertEqual(
            (profile.pg_first_name, profile.pg_last_name, profile.pg_email),
            ("Pat", "Example", "pat@guardians.example.test"),
        )
        # Their guardian is emailed the consent form, as from their profile.
        consent.assert_called_once_with(profile)
        self.assertEqual(int(self.client.session["_auth_user_id"]), teammate.pk)
        # Used: the link's done with.
        self.assertEqual(self.check(token).status_code, 400)

    def test_one_registered_with_their_guardian_just_sets_a_password(self):
        body = batch("student_team")
        body["payload"]["students"][1].update(guardianDeferred=False)
        body["payload"]["students"][1]["guardian"] = student(100, deferred=False)["guardian"]
        token = self.token(self.teammate_link(body))
        self.assertFalse(self.check(token).data["needsGuardian"])
        self.assertEqual(self.set_password(token).status_code, 200)

    def test_the_link_works_for_14_days(self):
        token = self.token(self.teammate_link())
        sent_at = time.time()
        with patch("django.core.signing.time.time", return_value=sent_at + EMAIL_MAX_AGE_SECONDS - 60):
            self.assertEqual(self.check(token).status_code, 200)
        with patch("django.core.signing.time.time", return_value=sent_at + EMAIL_MAX_AGE_SECONDS + 60):
            expired = self.check(token)
            self.assertEqual(self.set_password(token, self.GUARDIAN).status_code, 400)
        self.assertEqual(expired.status_code, 400)
        self.assertEqual(
            expired.data["error"], "This link to set your password has expired. Sign in with your email to set one.",
        )

    def test_the_email_has_the_button_only_with_a_link(self):
        link = "https://portal.test/#/register/password?token=abc"
        context = {"First_Name": "Ben", "YEAR": "2026", "SUPERVISOR_NAME": "Sam Lee"}
        for key in ("registration_group", "registration_by_supervisor", "registration_by_admin"):
            with self.subTest(key):
                html = render_system_email(key, {**context, "SET_PASSWORD_URL": link}).html
                self.assertIn(f'href="{link}"', html)
                self.assertIn("Set your password", html)
                self.assertIn("The link works for 14 days.", html)
                self.assertNotIn("Set your password", render_system_email(key, context).html)

    def test_system_emails_test_sends_carry_a_link_that_sets_no_ones_password(self):
        from apps.admin.services.system_email_recipients import recipient_context

        body = batch("student_team")
        self.links(body)
        teammate = User.objects.get(email=body["payload"]["students"][1]["email"])
        for key in ("registration_group", "registration_by_supervisor", "registration_by_admin"):
            with self.subTest(key):
                link = recipient_context(key, str(teammate.pk))["SET_PASSWORD_URL"]
                self.assertEqual(self.token(link), "sample")
                self.assertEqual(self.check("sample").status_code, 400)
