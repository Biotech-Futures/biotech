"""Admin > Users > Add user: its email boxes checked as each is left
(apps.admin.user_email_check), and what saving refuses. All HTTP is mocked
(QevTestCase), so no test can spend real credits."""
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.admin.user_email_check import NOT_AN_EMAIL, TAKEN
from apps.admin.services.user import create_user
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import AdminScope, User
from apps.users.serializers import GUARDIAN_HAS_ACCOUNT, GUARDIAN_IS_SELF, GUARDIAN_IS_STUDENT, PLACEHOLDER_EMAIL
from tests.apps.users.test_email_verification import QevTestCase, qev
from tests.apps.users.test_registration_email_warnings import answer

URL = "/api/v1/admin/user/email-check/"
UNKNOWN = "This email address couldn't be verified. Please check it, or confirm if this is correct."
GONE = "This email address doesn't appear to exist. Please correct it, or confirm if this is correct."


def hard(message):
    return {"ok": False, "severity": "hard", "code": "email_refused", "message": message}


class UserEmailCheckTests(QevTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        # Any lookup a test doesn't set up says the address exists.
        self.answer_always(qev())
        self.admin = User.objects.create_user(email="admin@example.test", first_name="Ada", last_name="Admin")
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def one(self, kind, email, **extra):
        response = self.client.post(URL, {"fields": [{"field": "box", "kind": kind, "email": email, **extra}]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["results"]["box"]

    def test_admins_only(self):
        student = User.objects.create_user(email="kid@example.test")
        self.client.force_authenticate(student)
        response = self.client.post(URL, {"fields": [{"field": "box", "kind": "account", "email": "a@b.test"}]}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_an_account_address_format_placeholder_and_one_in_use(self):
        User.objects.create_user(email="taken@example.test")

        self.assertEqual(self.one("account", "nope"), hard(NOT_AN_EMAIL))
        self.assertEqual(self.one("account", "x@example.invalid"), hard(PLACEHOLDER_EMAIL))
        self.assertEqual(self.one("account", "Taken@example.test"), hard(TAKEN))
        # Editing that user: their own address is theirs.
        taken = User.objects.get(email="taken@example.test")
        self.assertEqual(self.one("account", "taken@example.test", userId=taken.pk), {"ok": True})
        self.assertEqual(self.one("account", ""), {"ok": True})

    def test_a_mailbox_warns_rather_than_refuses(self):
        answer("gone@example.test")
        answer("unsure@example.test", "unknown")

        self.assertEqual(self.one("account", "gone@example.test"), {
            "ok": False, "severity": "soft", "warnings": [{"code": "email_invalid", "message": GONE}],
        })
        self.assertEqual(self.one("account", "unsure@example.test")["warnings"][0]["message"], UNKNOWN)
        # Answers on file: no lookup.
        self.assertEqual(self.http.call_count, 0)

    def test_a_new_address_is_looked_up_once_and_kept(self):
        self.answer_always(qev("invalid", "rejected_email"))

        self.assertEqual(self.one("account", "new@example.test")["severity"], "soft")
        self.assertEqual(self.one("account", "new@example.test")["severity"], "soft")
        self.assertEqual(self.http.call_count, 1)

    def test_a_name_that_looks_like_a_typo_of_the_address(self):
        result = self.one("account", "jordn.lee@example.test", firstName="Jordan", lastName="Lee")

        self.assertEqual(result["warnings"][0]["code"], "name_email_mismatch")
        self.assertIn("the user's name", result["warnings"][0]["message"])

    def test_a_guardian(self):
        kid = User.objects.create_user(email="other.kid@example.test")
        RoleAssignmentHistory.objects.create(
            user=kid, role=Roles.objects.get_or_create(role_name="student")[0], valid_from=timezone.now(),
        )
        User.objects.create_user(email="parent@example.test")

        self.assertEqual(self.one("guardian", "pupil@example.test", accountEmail="Pupil@example.test"), hard(GUARDIAN_IS_SELF))
        self.assertEqual(self.one("guardian", "other.kid@example.test", accountEmail="pupil@example.test"), hard(GUARDIAN_IS_STUDENT))
        self.assertEqual(self.one("guardian", "parent@example.test", accountEmail="pupil@example.test"), {
            "ok": False, "severity": "soft",
            "warnings": [{"code": "guardian_email_has_account", "message": GUARDIAN_HAS_ACCOUNT}],
        })
        self.assertEqual(self.one("guardian", "mum@example.test", accountEmail="pupil@example.test"), {"ok": True})

    def test_at_most_sixty_a_minute(self):
        for _ in range(60):
            self.one("account", "")
        refused = self.client.post(URL, {"fields": [{"field": "box", "kind": "account", "email": ""}]}, format="json")
        self.assertEqual(refused.status_code, 429)


class AddUserRefusesTests(QevTestCase):
    def add(self, **fields):
        return create_user({"firstName": "Pip", "lastName": "Pupil", "role": "student", **fields})

    def test_what_the_check_refuses_saving_refuses(self):
        self.assertEqual(self.add(email="nope")["msg"], NOT_AN_EMAIL)
        self.assertEqual(self.add(email="pip@example.invalid")["msg"], PLACEHOLDER_EMAIL)
        self.assertEqual(self.add(email="pip@example.test", guardianEmail="Pip@example.test")["msg"], GUARDIAN_IS_SELF)
        self.assertFalse(User.objects.filter(email__iexact="pip@example.test").exists())
