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

from apps.services.views import _login_send_cooldown_key, _login_send_email_key

User = get_user_model()

SEND_URL = "/services/send-login-code/"


def _skip_send_cooldown(email):
    """Drop the 60s min-interval so a test can probe the fixed-window caps."""
    cache.delete(_login_send_cooldown_key(email))


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
            _skip_send_cooldown(self.user.email)
            r = self.client.post(SEND_URL, {"email": self.user.email}, format="json")
            self.assertEqual(r.status_code, 200, r.content)

    def test_per_email_limit_blocks_sixth(self, _mock_mail):
        for _ in range(5):
            _skip_send_cooldown(self.user.email)
            self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        _skip_send_cooldown(self.user.email)
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
            _skip_send_cooldown(ghost)
            r = self.client.post(SEND_URL, {"email": ghost}, format="json")
            self.assertEqual(r.status_code, 200)
        _skip_send_cooldown(ghost)
        r = self.client.post(SEND_URL, {"email": ghost}, format="json")
        self.assertEqual(r.status_code, 429)
        mock_mail.assert_not_called()

    # --- minimum interval between sends -------------------------------------

    def test_second_send_within_interval_is_throttled_with_retry_after(self, _mock_mail):
        first = self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        self.assertEqual(first.status_code, 200)

        second = self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        body = second.json()
        self.assertEqual(second.status_code, 429)
        self.assertEqual(body.get("code"), "login_send_rate_limited")
        self.assertGreater(body.get("retry_after"), 0)
        self.assertLessEqual(body.get("retry_after"), 60)
        self.assertEqual(second["Retry-After"], str(body["retry_after"]))

    def test_cooldown_response_is_identical_for_unknown_email(self, _mock_mail):
        # The cooldown must not become an account-enumeration oracle: a known and
        # an unknown address have to be indistinguishable on the second call.
        self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        known = self.client.post(SEND_URL, {"email": self.user.email}, format="json")

        ghost = "ghost@example.com"
        self.client.post(SEND_URL, {"email": ghost}, format="json")
        unknown = self.client.post(SEND_URL, {"email": ghost}, format="json")

        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.json().get("code"), unknown.json().get("code"))
        self.assertEqual(known.json().get("error"), unknown.json().get("error"))

    def test_cooldown_key_is_case_insensitive(self, _mock_mail):
        self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        r = self.client.post(
            SEND_URL, {"email": self.user.email.upper()}, format="json"
        )
        self.assertEqual(r.status_code, 429)

    def test_rejected_send_does_not_re_arm_the_cooldown(self, _mock_mail):
        # cache.add semantics: hammering must not push the deadline out forever.
        # Asserting only "second <= first" would pass even for a re-arming
        # implementation, since both calls land in the same wall-clock second —
        # so age the deadline and require the countdown to have actually moved.
        self.client.post(SEND_URL, {"email": self.user.email}, format="json")

        key = _login_send_cooldown_key(self.user.email)
        cache.set(key, cache.get(key) - 5, 60)  # pretend 5s have passed

        body = self.client.post(
            SEND_URL, {"email": self.user.email}, format="json"
        ).json()
        self.assertLessEqual(body["retry_after"], 55)

    def test_window_rejection_also_carries_retry_after(self, _mock_mail):
        for _ in range(5):
            _skip_send_cooldown(self.user.email)
            self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        _skip_send_cooldown(self.user.email)

        body = self.client.post(
            SEND_URL, {"email": self.user.email}, format="json"
        ).json()
        self.assertEqual(body["code"], "login_send_rate_limited")
        self.assertGreater(body["retry_after"], 60)

    def test_counter_without_a_deadline_key_cannot_lock_out_forever(self, _mock_mail):
        # Redis incr is EXISTS-then-INCRBY: if the key lapses between the two,
        # INCRBY recreates it with no TTL and the address would 429 forever.
        cache.set(_login_send_email_key(self.user.email), 99, None)

        _skip_send_cooldown(self.user.email)
        blocked = self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        self.assertEqual(blocked.status_code, 429)

        # The next successful bump must repair the counter and its expiry.
        cache.delete(_login_send_email_key(self.user.email))
        _skip_send_cooldown(self.user.email)
        recovered = self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        self.assertEqual(recovered.status_code, 200)

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
            _skip_send_cooldown(self.user.email)
            self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        _skip_send_cooldown(self.user.email)
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
