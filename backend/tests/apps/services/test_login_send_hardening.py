"""
Audit 2.2 regression tests — authentication abuse hardening.

Covers the three findings from the 2.2 audit pass:
    1. ``send-login-code`` never 404s (anti-enumeration: same response for
       known and unknown emails).
    2. Login/OTP endpoints rate-limit per email AND per IP — also exercised
       in test_login_send_throttle / test_services::LoginEndpointsTest, this
       module adds the explicit "no leak via response shape" assertions the
       audit asked for.
    3. Magic-link emails never embed ``localhost:8000`` when ``BACKEND_URL``
       is configured — i.e. the service code reads from settings instead of
       its own hardcoded fallback.

Run with::

    python manage.py test tests.apps.services.test_login_send_hardening \
        --settings=config.settings_test
"""

from unittest.mock import patch
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.services.auth_service import send_login_code

User = get_user_model()

SEND_URL = "/services/send-login-code/"


def _make_user(email="audit22@example.com"):
    return User.objects.create_user(
        email=email,
        password="OldStrongPass!42",
        first_name="Audit",
        last_name="TwoTwo",
        account_status=User.AccountStatus.ACTIVE,
    )


# --- Finding 1: no account-existence leak via status code -------------------

@patch("apps.services.auth_service.EmailMultiAlternatives")
class SendLoginCodeNoEnumerationTest(TestCase):
    """The endpoint MUST return the same shape (200 + generic message) for
    known and unknown emails. The previous OpenAPI contract advertised 404
    for unknown users; this test pins the runtime to the anti-enumeration
    contract and prevents a regression."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = _make_user()

    def test_known_email_returns_200_generic_message(self, _mock_mail):
        r = self.client.post(SEND_URL, {"email": self.user.email}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json().get("message"),
            "If an account exists for that email, a login code has been sent.",
        )

    def test_unknown_email_returns_200_same_message(self, mock_mail):
        r = self.client.post(SEND_URL, {"email": "ghost@example.com"}, format="json")
        # Identical to the known-email response — no 404, no different body.
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json().get("message"),
            "If an account exists for that email, a login code has been sent.",
        )
        # And we definitely don't send mail to a non-user.
        mock_mail.assert_not_called()

    def test_response_shape_identical_for_known_and_unknown(self, _mock_mail):
        # Same status code, same JSON keys, same message — by construction
        # the only signal an attacker could read.
        known = self.client.post(
            SEND_URL, {"email": self.user.email}, format="json"
        )
        unknown = self.client.post(
            SEND_URL, {"email": "ghost2@example.com"}, format="json"
        )
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(set(known.json().keys()), set(unknown.json().keys()))
        self.assertEqual(known.json()["message"], unknown.json()["message"])


# --- Finding 3: no localhost:8000 in magic-link emails ----------------------

class MagicLinkBackendUrlTest(TestCase):
    """The magic link href in the OTP email MUST come from settings.BACKEND_URL,
    not a hardcoded fallback in the service code. Stops a misconfigured deploy
    from emailing magic links that point at http://localhost:8000."""

    def setUp(self):
        cache.clear()
        self.user = _make_user(email="magic_url@example.com")

    @override_settings(BACKEND_URL="https://api.biotechfutures.org")
    @patch("apps.services.auth_service.render_to_string")
    @patch("apps.services.auth_service.EmailMultiAlternatives")
    def test_magic_link_uses_configured_backend_url(self, _mock_email, mock_render):
        mock_render.return_value = "<html>ignored</html>"
        self.assertTrue(send_login_code(self.user.email))

        ctx = mock_render.call_args[0][1]
        magic_link = ctx["MAGIC_LINK"]
        self.assertTrue(
            magic_link.startswith("https://api.biotechfutures.org/services/magic/"),
            f"magic link should anchor on configured BACKEND_URL, got {magic_link!r}",
        )
        # Origin of the magic link must not be localhost. The redirect_url
        # query param is independent (frontend SPA callback) so we inspect
        # scheme+host only, not the encoded query string.
        parsed = urlparse(magic_link)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.hostname, "api.biotechfutures.org")

    @override_settings(BACKEND_URL="https://api.biotechfutures.org/")
    @patch("apps.services.auth_service.render_to_string")
    @patch("apps.services.auth_service.EmailMultiAlternatives")
    def test_backend_url_trailing_slash_is_normalized(self, _mock_email, mock_render):
        # Tolerant of an env var with a trailing slash — must not produce a
        # double slash like https://host//services/magic/.
        mock_render.return_value = "<html>ignored</html>"
        self.assertTrue(send_login_code(self.user.email))

        magic_link = mock_render.call_args[0][1]["MAGIC_LINK"]
        self.assertIn(
            "https://api.biotechfutures.org/services/magic/", magic_link
        )
        self.assertNotIn(".org//services", magic_link)
