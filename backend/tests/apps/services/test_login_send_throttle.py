"""
Tests for the send-login-code throttle and the X-Forwarded-For trust gate.

Run with:
    python manage.py test tests.apps.services.test_login_send_throttle \
        --settings=config.settings_test
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

User = get_user_model()

SEND_URL = "/services/send-login-code/"


def _make_user(email="login_throttle@example.com"):
    return User.objects.create_user(
        email=email,
        password="OldStrongPass!42",
        first_name="Login",
        last_name="Throttle",
        account_status=User.AccountStatus.ACTIVE,
    )


@patch("apps.services.auth_service.EmailMultiAlternatives")
class SendLoginCodeThrottleTest(TestCase):
    """Closes the email-bombing surface flagged at services/views.py:71-94 —
    password reset throttles, login send must too."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = _make_user()

    # --- per-email cap ------------------------------------------------------

    def test_per_email_limit_allows_first_five(self, _mock_mail):
        for _ in range(5):
            r = self.client.post(SEND_URL, {"email": self.user.email}, format="json")
            self.assertEqual(r.status_code, 200, r.content)

    def test_per_email_limit_blocks_sixth(self, _mock_mail):
        for _ in range(5):
            self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        r = self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json().get("code"), "login_send_rate_limited")

    def test_per_email_budget_consumed_even_for_unknown_email(self, mock_mail):
        # Anti-enumeration path returns 200 silently — the bombing fix only
        # holds if these "silent" calls also consume budget. Otherwise an
        # attacker iterates unknown addresses to keep the per-IP counter low
        # for the *real* victim.
        ghost = "ghost@example.com"
        for _ in range(5):
            r = self.client.post(SEND_URL, {"email": ghost}, format="json")
            self.assertEqual(r.status_code, 200)
        r = self.client.post(SEND_URL, {"email": ghost}, format="json")
        self.assertEqual(r.status_code, 429)
        mock_mail.assert_not_called()

    # --- per-IP cap ---------------------------------------------------------

    def test_per_ip_limit_blocks_after_twenty_distinct_emails(self, _mock_mail):
        # 20 distinct emails from the same client IP → 21st must trip the IP
        # axis even though no single email reached its per-email cap.
        for i in range(20):
            r = self.client.post(SEND_URL, {"email": f"u{i}@example.com"}, format="json")
            self.assertEqual(r.status_code, 200, f"req {i} status={r.status_code}")
        r = self.client.post(SEND_URL, {"email": "u20@example.com"}, format="json")
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json().get("code"), "login_send_rate_limited")

    # --- response shape -----------------------------------------------------

    def test_throttle_response_is_429_with_stable_code(self, _mock_mail):
        for _ in range(5):
            self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        r = self.client.post(SEND_URL, {"email": self.user.email}, format="json")

        body = r.json()
        self.assertEqual(r.status_code, 429)
        self.assertEqual(body.get("code"), "login_send_rate_limited")
        # custom_exception_handler always tacks on a request id
        self.assertIn("request_id", body)

    def test_missing_email_returns_400_not_429(self, _mock_mail):
        r = self.client.post(SEND_URL, {}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json().get("code"), "email_required")


@patch("apps.services.auth_service.EmailMultiAlternatives")
class ClientIpForwardedForTrustTest(TestCase):
    """`_client_ip` must only honor X-Forwarded-For when explicitly opted in
    via TRUST_FORWARDED_FOR. Otherwise an attacker can rotate the header to
    spread bombing load across "different" IPs and never trip the per-IP cap."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        _make_user()

    @override_settings(TRUST_FORWARDED_FOR=False)
    def test_xff_ignored_by_default(self, _mock_mail):
        # 20 sends with 20 spoofed XFFs but the same REMOTE_ADDR (127.0.0.1)
        # must still trip the per-IP cap, because XFF is not trusted.
        for i in range(20):
            r = self.client.post(
                SEND_URL,
                {"email": f"u{i}@example.com"},
                format="json",
                HTTP_X_FORWARDED_FOR=f"203.0.113.{i}",
            )
            self.assertEqual(r.status_code, 200)
        r = self.client.post(
            SEND_URL,
            {"email": "u20@example.com"},
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.99",
        )
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json().get("code"), "login_send_rate_limited")

    @override_settings(TRUST_FORWARDED_FOR=True)
    def test_xff_honored_when_trusted(self, _mock_mail):
        # Behind a trusted proxy, each XFF maps to a distinct rate-limit key.
        # 20 sends across 20 IPs should NOT trip the per-IP cap on any single IP.
        for i in range(20):
            r = self.client.post(
                SEND_URL,
                {"email": f"u{i}@example.com"},
                format="json",
                HTTP_X_FORWARDED_FOR=f"203.0.113.{i}",
            )
            self.assertEqual(r.status_code, 200)
        # A 21st request from a fresh trusted IP and fresh email is still allowed.
        r = self.client.post(
            SEND_URL,
            {"email": "freshcaller@example.com"},
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.99",
        )
        self.assertEqual(r.status_code, 200)
