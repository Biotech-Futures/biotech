"""Inactive-account gating on the OTP and magic-link login paths.

Both paths hand-roll the check against ``User.INACTIVE_LOGIN_STATUSES`` (custom
session auth never calls Django's ``authenticate()``), so each needs its own
coverage — including proof that invited/pending are NOT blocked.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.services.models import LoginToken

User = get_user_model()


class InactiveLoginGateTests(TestCase):
    def setUp(self):
        cache.clear()  # OTP rate limits are cache-backed and leak across tests
        self.client = APIClient()
        self.email = "otpinactive@example.com"
        self.user = User.objects.create_user(
            email=self.email,
            password="SecurePass123",
            first_name="OTP",
            last_name="Test",
            account_status=User.AccountStatus.ACTIVE,
        )

    def _fresh_code(self):
        return LoginToken.create_for_user(self.user, expiry_minutes=10).token

    # --- OTP verify ------------------------------------------------------

    def test_verify_login_code_fails_deactivated_account(self):
        code = self._fresh_code()
        self.user.deactivate()

        response = self.client.post(
            reverse("verify_login_code"),
            {"email": self.email, "code": code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["code"], "account_inactive")

    def test_verify_login_code_fails_suspended_account(self):
        code = self._fresh_code()
        self.user.suspend()

        response = self.client.post(
            reverse("verify_login_code"),
            {"email": self.email, "code": code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["code"], "account_inactive")

    def test_verify_login_code_allowed_for_invited_and_pending(self):
        for transition in ("invite", "mark_pending"):
            with self.subTest(transition=transition):
                cache.clear()
                code = self._fresh_code()
                getattr(self.user, transition)()

                response = self.client.post(
                    reverse("verify_login_code"),
                    {"email": self.email, "code": code},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    # --- magic link ------------------------------------------------------

    def test_magic_login_redirects_with_account_inactive_error(self):
        code = self._fresh_code()
        self.user.deactivate()

        response = self.client.get(
            reverse("magic_login"), {"email": self.email, "code": code},
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertTrue(
            response["Location"].endswith("?error=account_inactive"),
            response["Location"],
        )

    def test_magic_login_redirects_with_account_inactive_error_when_suspended(self):
        code = self._fresh_code()
        self.user.suspend()

        response = self.client.get(
            reverse("magic_login"), {"email": self.email, "code": code},
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertTrue(
            response["Location"].endswith("?error=account_inactive"),
            response["Location"],
        )

    def test_magic_login_allowed_for_invited_and_pending(self):
        for transition in ("invite", "mark_pending"):
            with self.subTest(transition=transition):
                cache.clear()
                code = self._fresh_code()
                getattr(self.user, transition)()

                response = self.client.get(
                    reverse("magic_login"), {"email": self.email, "code": code},
                )
                self.assertEqual(response.status_code, status.HTTP_302_FOUND)
                self.assertIn("success=true", response["Location"])
