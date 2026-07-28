"""
Tests for custom LoginToken OTP system in auth_service
Run with: python manage.py test apps.services
"""

from django.test import TestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock

from apps.services.auth_service import send_login_code, verify_login_code
from apps.services.models import LoginToken
from apps.users.models import AdminScope

User = get_user_model()


class LoginTokenTest(TestCase):
    """Test our custom LoginToken OTP system"""

    def setUp(self):
        """Create test user for testing"""
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User"
        )

    def test_imports(self):
        """Test that all required imports work"""
        try:
            from apps.services.auth_service import send_login_code, verify_login_code
            from apps.services.models import LoginToken
            self.assertTrue(True, "All imports successful")
        except ImportError as e:
            self.fail(f"Import error: {e}")

    def test_token_generation(self):
        """Test secure token generation"""
        token = LoginToken.generate_token()

        self.assertIsInstance(token, str)
        self.assertEqual(len(token), 6)
        self.assertTrue(token.isdigit())

    def test_login_token_creation(self):
        """Test LoginToken creation for user"""
        login_token = LoginToken.create_for_user(self.user, expiry_minutes=10)

        self.assertEqual(login_token.user, self.user)
        self.assertEqual(len(login_token.token), 6)
        self.assertTrue(login_token.token.isdigit())
        self.assertFalse(login_token.used)
        self.assertTrue(login_token.is_valid)

    def test_token_expiration(self):
        """Test token expiration logic"""
        # Create expired token
        login_token = LoginToken.objects.create(
            user=self.user,
            token="123456",
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        self.assertTrue(login_token.is_expired)
        self.assertFalse(login_token.is_valid)

    def test_token_verification_success(self):
        """Test successful token verification"""
        login_token = LoginToken.create_for_user(self.user)

        # Verify token
        verified_token = LoginToken.verify_token_for_user(self.user, login_token.token)

        self.assertIsNotNone(verified_token)
        self.assertEqual(verified_token.id, login_token.id)

        # Refresh from database
        login_token.refresh_from_db()
        self.assertTrue(login_token.used)

    def test_token_single_use(self):
        """Test that tokens can only be used once"""
        login_token = LoginToken.create_for_user(self.user)

        # First verification should succeed
        verified_token1 = LoginToken.verify_token_for_user(self.user, login_token.token)
        self.assertIsNotNone(verified_token1)

        # Second verification should fail (token already used)
        verified_token2 = LoginToken.verify_token_for_user(self.user, login_token.token)
        self.assertIsNone(verified_token2)

    def test_invalid_token_verification(self):
        """Test verification with invalid token"""
        verified_token = LoginToken.verify_token_for_user(self.user, "invalid_token")
        self.assertIsNone(verified_token)

    def test_expired_token_verification(self):
        """Test verification with expired token"""
        # Create expired token
        login_token = LoginToken.objects.create(
            user=self.user,
            token="123456",
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        verified_token = LoginToken.verify_token_for_user(self.user, login_token.token)
        self.assertIsNone(verified_token)

    def test_cleanup_expired_tokens(self):
        """Test cleanup of expired tokens"""
        # Create some expired and valid tokens
        LoginToken.objects.create(
            user=self.user,
            token="111111",
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        LoginToken.objects.create(
            user=self.user,
            token="222222",
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        LoginToken.create_for_user(self.user)  # Valid token

        # Before cleanup
        self.assertEqual(LoginToken.objects.count(), 3)

        # Cleanup expired
        count = LoginToken.cleanup_expired()
        self.assertEqual(count, 2)
        self.assertEqual(LoginToken.objects.count(), 1)


class AuthServiceTest(TestCase):
    """Test auth service functions with LoginToken"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="authtest@example.com",
            password="testpass123",
            first_name="Auth",
            last_name="Test"
        )

    @patch('apps.services.auth_service.render_to_string')
    @patch('apps.services.auth_service.EmailMultiAlternatives')
    def test_send_login_code_success(self, mock_email, mock_render):
        """Test successful login code sending (mocked email)"""
        # Mock template rendering and email sending
        mock_render.return_value = "<html>Test email template</html>"
        mock_msg = MagicMock()
        mock_email.return_value = mock_msg

        result = send_login_code(self.user.email)

        self.assertTrue(result)
        # Verify template was rendered and email was sent
        mock_render.assert_called_once()
        mock_email.assert_called_once()
        mock_msg.send.assert_called_once()

        # Verify token was created in database
        self.assertEqual(LoginToken.objects.filter(user=self.user).count(), 1)

    def test_send_login_code_invalid_email(self):
        """Test login code sending with non-existent user"""
        result = send_login_code("nonexistent@example.com")
        self.assertFalse(result)
        self.assertEqual(LoginToken.objects.count(), 0)

    def test_verify_login_code_success(self):
        """Test successful login code verification"""
        # Create a login token
        login_token = LoginToken.create_for_user(self.user)

        # Verify the token
        result = verify_login_code(self.user.email, login_token.token)
        self.assertTrue(result)

        # Token should be marked as used
        login_token.refresh_from_db()
        self.assertTrue(login_token.used)

    def test_verify_login_code_invalid_user(self):
        """Test verification with non-existent user"""
        result = verify_login_code("nonexistent@example.com", "123456")
        self.assertFalse(result)

    def test_verify_login_code_invalid_token(self):
        """Test verification with invalid token"""
        result = verify_login_code(self.user.email, "invalid_token")
        self.assertFalse(result)

    def test_verify_login_code_expired_token(self):
        """Test verification with expired token"""
        # Create expired token
        expired_token = LoginToken.objects.create(
            user=self.user,
            token="654321",
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        result = verify_login_code(self.user.email, expired_token.token)
        self.assertFalse(result)


class AuthServiceIntegrationTest(TestCase):
    """Integration tests for complete auth flow"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="integration@example.com",
            password="testpass123",
            first_name="Integration",
            last_name="Test"
        )

    @patch('apps.services.auth_service.render_to_string')
    @patch('apps.services.auth_service.EmailMultiAlternatives')
    def test_full_auth_flow(self, mock_email, mock_render):
        """Test complete authentication flow"""
        # Mock email rendering and sending
        mock_render.return_value = "<html>Mock email</html>"
        mock_msg = MagicMock()
        mock_email.return_value = mock_msg

        # Step 1: Send login code
        result1 = send_login_code(self.user.email)
        self.assertTrue(result1)

        # Step 2: Get the generated token and verify
        login_token = LoginToken.objects.get(user=self.user)
        result2 = verify_login_code(self.user.email, login_token.token)
        self.assertTrue(result2)

        # Step 3: Try to use same token again (should fail)
        result3 = verify_login_code(self.user.email, login_token.token)
        self.assertFalse(result3)

    def test_auto_invalidate_previous_tokens(self):
        """Test that generating a new token invalidates previous pending tokens"""
        # Create token 1
        token1 = LoginToken.create_for_user(self.user)
        self.assertTrue(token1.is_valid)
        
        # Create token 2
        token2 = LoginToken.create_for_user(self.user)
        
        token1.refresh_from_db()
        # Token 1 should be immediately invalidated (used/burned)
        self.assertTrue(token1.used)
        self.assertTrue(token2.is_valid)


class LoginTokenReuseTest(TestCase):
    """Resending must not burn the code already sitting in the user's inbox —
    slow mail means users often open an older email than the one just sent."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="reuse@example.com",
            password="testpass123",
            first_name="Re",
            last_name="Use",
        )

    def test_resend_returns_the_same_code(self):
        first = LoginToken.get_or_create_active(self.user)
        second = LoginToken.get_or_create_active(self.user)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.token, second.token)
        self.assertEqual(LoginToken.objects.filter(user=self.user).count(), 1)

    def test_resend_refreshes_the_expiry_window(self):
        first = LoginToken.get_or_create_active(self.user)
        LoginToken.objects.filter(pk=first.pk).update(
            expires_at=timezone.now() + timedelta(minutes=2)
        )

        refreshed = LoginToken.get_or_create_active(self.user)
        self.assertEqual(refreshed.pk, first.pk)
        self.assertGreater(refreshed.expires_at, timezone.now() + timedelta(minutes=9))

    def test_expired_token_is_replaced(self):
        stale = LoginToken.create_for_user(self.user)
        LoginToken.objects.filter(pk=stale.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        fresh = LoginToken.get_or_create_active(self.user)
        self.assertNotEqual(fresh.pk, stale.pk)
        self.assertTrue(fresh.is_valid)

    def test_refresh_is_capped_at_the_absolute_lifetime(self):
        # Otherwise a caller who can trigger resends keeps a 6-digit secret alive
        # forever.
        token = LoginToken.get_or_create_active(self.user)
        created = timezone.now() - timedelta(minutes=25)
        LoginToken.objects.filter(pk=token.pk).update(
            created_at=created, expires_at=timezone.now() + timedelta(minutes=1)
        )

        refreshed = LoginToken.get_or_create_active(self.user)
        self.assertEqual(refreshed.pk, token.pk)
        self.assertLessEqual(refreshed.expires_at, created + timedelta(minutes=30))

    def test_near_expiry_token_is_replaced_rather_than_resent(self):
        # Past the absolute cap the window can't move, so reusing would email a
        # code that dies in seconds while the email promises 10 minutes — and the
        # 60s send cooldown would leave the user with no way to get a live one.
        token = LoginToken.get_or_create_active(self.user)
        LoginToken.objects.filter(pk=token.pk).update(
            created_at=timezone.now() - timedelta(minutes=29),
            expires_at=timezone.now() + timedelta(seconds=30),
        )

        fresh = LoginToken.get_or_create_active(self.user)
        self.assertNotEqual(fresh.pk, token.pk)
        self.assertGreater(fresh.expires_at, timezone.now() + timedelta(minutes=9))

    def test_consumed_token_is_not_resurrected(self):
        token = LoginToken.get_or_create_active(self.user)
        LoginToken.objects.filter(pk=token.pk).update(used=True)

        fresh = LoginToken.get_or_create_active(self.user)
        self.assertNotEqual(fresh.pk, token.pk)
        self.assertTrue(fresh.is_valid)

    @patch('apps.services.auth_service.render_to_string', return_value="<html></html>")
    @patch('apps.services.auth_service.EmailMultiAlternatives')
    def test_mixed_case_email_still_delivers(self, mock_email, _mock_render):
        # Stored emails are lowercased on create, so an exact-match lookup would
        # silently drop anything typed with a capital and never send at all.
        mock_msg = MagicMock()
        mock_email.return_value = mock_msg

        self.assertTrue(send_login_code("Reuse@Example.com"))
        self.assertEqual(LoginToken.objects.filter(user=self.user).count(), 1)
        # Assert the send itself, not just the return value — otherwise this
        # passes even if dispatch were a no-op.
        mock_msg.send.assert_called_once()
        self.assertEqual(mock_email.call_args.kwargs["to"], [self.user.email])

    def test_mixed_case_email_verifies(self):
        token = LoginToken.get_or_create_active(self.user)
        self.assertTrue(verify_login_code("REUSE@example.com", token.token))


class LoginEndpointsTest(TestCase):
    """Integration tests for the HTTP Login Endpoints (OTP & Magic)"""
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.user_email = "api_test@example.com"
        self.user = User.objects.create_user(
            email=self.user_email,
            password="testpass123",
            first_name="API",
            last_name="Test",
            account_status=User.AccountStatus.ACTIVE
        )

    def test_otp_login_endpoint_success(self):
        token = LoginToken.create_for_user(self.user)
        response = self.client.post(
            "/services/verify-login-code/",
            {"email": self.user_email, "code": token.token},
            format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("sessionid", response.cookies)
        self.assertTrue(response.cookies["sessionid"].value)
        # Token is consumed
        token.refresh_from_db()
        self.assertTrue(token.used)

    def test_otp_login_endpoint_brute_force_lockout(self):
        # Trigger lockout
        for _ in range(5):
            self.client.post(
                "/services/verify-login-code/",
                {"email": self.user_email, "code": "000000"},
                format="json"
            )
        
        # Valid code should be blocked by 429
        token = LoginToken.create_for_user(self.user)
        response = self.client.post(
            "/services/verify-login-code/",
            {"email": self.user_email, "code": token.token},
            format="json"
        )
        self.assertEqual(response.status_code, 429)

    def test_magic_link_get_hands_off_without_consuming_the_code(self):
        token = LoginToken.create_for_user(self.user)
        url = f"/services/magic/?email={self.user_email}&code={token.token}&redirect_url=http://localhost:5173"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"code={token.token}", response.url)
        # The GET must open no session and burn no token — see MagicLinkScannerSafetyTest.
        self.assertNotIn("sessionid", response.cookies)
        token.refresh_from_db()
        self.assertFalse(token.used)


class MagicLinkScannerSafetyTest(TestCase):
    """Mail security products (Outlook Safe Links, Defender, spam filters) fetch
    every URL in an email. The magic-link GET must therefore be side-effect free,
    or the scanner consumes the code and the student is locked out of their own
    login link — observed twice in three minutes for two different students."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="scanned@example.com",
            password="testpass123",
            first_name="Scan",
            last_name="Target",
            account_status=User.AccountStatus.ACTIVE,
        )

    def _magic_url(self, code: str) -> str:
        return f"/services/magic/?email={self.user.email}&code={code}"

    def test_scanner_prefetch_leaves_the_code_usable(self):
        token = LoginToken.create_for_user(self.user)

        # Three scanners hit the link before the student ever sees the email.
        for _ in range(3):
            self.client.get(self._magic_url(token.token))

        token.refresh_from_db()
        self.assertFalse(token.used)

        # The student then signs in normally.
        response = self.client.post(
            "/services/verify-login-code/",
            {"email": self.user.email, "code": token.token},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_scanner_prefetch_opens_no_session(self):
        token = LoginToken.create_for_user(self.user)
        response = self.client.get(self._magic_url(token.token))

        self.assertNotIn("sessionid", response.cookies)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_scanner_prefetch_does_not_burn_verify_attempts(self):
        # A scanner hitting a stale link must not consume the student's 5 tries.
        for _ in range(10):
            self.client.get(self._magic_url("000000"))

        token = LoginToken.create_for_user(self.user)
        response = self.client.post(
            "/services/verify-login-code/",
            {"email": self.user.email, "code": token.token},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_handoff_target_comes_from_redirect_url_not_the_account(self):
        # Routing must not depend on a user lookup: the GET does not validate the
        # code, so branching on is_admin() would be a free admin-enumeration oracle.
        from urllib.parse import quote

        AdminScope.objects.create(user=self.user)
        token = LoginToken.create_for_user(self.user)
        callback = "http://localhost:5173/#/auth/callback"
        response = self.client.get(
            f"{self._magic_url(token.token)}&redirect_url={quote(callback, safe='')}"
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(callback), response.url)
        self.assertNotIn("mentoringadmin", response.url)

    def test_disallowed_redirect_url_falls_back_to_the_user_app(self):
        from urllib.parse import quote

        token = LoginToken.create_for_user(self.user)
        response = self.client.get(
            f"{self._magic_url(token.token)}&redirect_url={quote('https://evil.example.com/x', safe='')}"
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.url.startswith(settings.MAGIC_LINK_REDIRECT_URL),
            f"unexpected redirect: {response.url}",
        )


class MagicLinkErrorRedirectTest(TestCase):
    """Error redirects must reach the frontend route that renders the explanation."""

    def setUp(self):
        from django.core.cache import cache
        from rest_framework.test import APIClient

        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="err@example.com",
            password="testpass123",
            first_name="Err",
            last_name="User",
            account_status=User.AccountStatus.ACTIVE,
        )

    def _bad_code_url(self, redirect_url: str | None = None) -> str:
        # A malformed link (no code at all) — the GET no longer validates codes,
        # so this is the only shape that still errors server-side.
        url = f"/services/magic/?email={self.user.email}"
        if redirect_url is not None:
            from urllib.parse import quote

            url += f"&redirect_url={quote(redirect_url, safe='')}"
        return url

    def test_error_redirect_keeps_the_hash_route(self):
        """The user app routes on the hash, so a stripped fragment strands ?error= at the site root."""
        callback = "http://localhost:5173/#/auth/callback"
        response = self.client.get(self._bad_code_url(callback))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{callback}?error=invalid_or_expired_code")

    def test_error_redirect_without_redirect_url_targets_the_user_app(self):
        response = self.client.get(self._bad_code_url())

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.url.startswith(settings.MAGIC_LINK_REDIRECT_URL),
            f"unexpected redirect: {response.url}",
        )


class PasswordResetAdminRedirectTest(TestCase):
    """Password-reset emails point admins at the admin portal and regular users at the user app."""

    def setUp(self):
        self.regular_user = User.objects.create_user(
            email="pwreset_regular@example.com",
            password="testpass123",
            first_name="Reg",
            last_name="User",
            account_status=User.AccountStatus.ACTIVE,
        )
        self.admin_user = User.objects.create_user(
            email="pwreset_admin@example.com",
            password="testpass123",
            first_name="Adm",
            last_name="User",
            account_status=User.AccountStatus.ACTIVE,
        )
        AdminScope.objects.create(user=self.admin_user)

    @patch("apps.services.auth_service.render_to_string")
    @patch("apps.services.auth_service.EmailMultiAlternatives")
    def test_admin_reset_email_uses_admin_portal_base(self, mock_email, mock_render):
        from apps.services.auth_service import send_password_reset

        mock_render.return_value = "<html>reset</html>"
        mock_msg = MagicMock()
        mock_email.return_value = mock_msg

        send_password_reset(self.admin_user.email, ip="127.0.0.1", user_agent="pytest")

        ctx = mock_render.call_args[0][1]
        self.assertIn(
            f"{settings.ADMIN_PASSWORD_RESET_REDIRECT_URL}?token=",
            ctx["RESET_PASSWORD_LINK"],
        )
        # The admin SPA serves this page at /reset-password (no /auth prefix, unlike
        # the Vue app and the /auth/callback magic-link route) — guard the link path.
        self.assertIn("/reset-password?token=", ctx["RESET_PASSWORD_LINK"])
        self.assertNotIn("/auth/reset-password", ctx["RESET_PASSWORD_LINK"])
        # Plaintext body must also use the admin portal base
        text_body = mock_email.call_args.kwargs["body"]
        self.assertIn(settings.ADMIN_PASSWORD_RESET_REDIRECT_URL, text_body)

    @patch("apps.services.auth_service.render_to_string")
    @patch("apps.services.auth_service.EmailMultiAlternatives")
    def test_regular_user_reset_email_uses_user_frontend_base(self, mock_email, mock_render):
        from apps.services.auth_service import send_password_reset

        mock_render.return_value = "<html>reset</html>"
        mock_msg = MagicMock()
        mock_email.return_value = mock_msg

        send_password_reset(self.regular_user.email, ip="127.0.0.1", user_agent="pytest")

        ctx = mock_render.call_args[0][1]
        self.assertNotIn("mentoringadmin.biotechfutures.org", ctx["RESET_PASSWORD_LINK"])
        self.assertIn("/auth/reset-password?token=", ctx["RESET_PASSWORD_LINK"])

    @patch("apps.services.auth_service.render_to_string")
    @patch("apps.services.auth_service.EmailMultiAlternatives")
    def test_admin_scope_user_reset_email_uses_admin_portal_base(self, mock_email, mock_render):
        """A user with an AdminScope row is routed to the admin portal."""
        from apps.users.models import AdminScope
        from apps.services.auth_service import send_password_reset

        scoped_admin = User.objects.create_user(
            email="pwreset_scoped@example.com",
            password="testpass123",
            first_name="Scoped",
            last_name="Admin",
            account_status=User.AccountStatus.ACTIVE,
        )
        AdminScope.objects.create(user=scoped_admin)

        mock_render.return_value = "<html>reset</html>"
        mock_msg = MagicMock()
        mock_email.return_value = mock_msg

        send_password_reset(scoped_admin.email, ip="127.0.0.1", user_agent="pytest")

        ctx = mock_render.call_args[0][1]
        self.assertIn(
            f"{settings.ADMIN_PASSWORD_RESET_REDIRECT_URL}?token=",
            ctx["RESET_PASSWORD_LINK"],
        )


class ContactEmailTemplateContextTest(TestCase):
    """Every transactional email passes a single CONTACT_EMAIL var (= SUPPORT_EMAIL).

    This pins the consolidation: contact mailtos must come from one
    settings-driven source (support@, via brand_context), not hardcoded in
    templates or auth_service. The sending mailbox (info@) is separate.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="contact_ctx@example.com",
            password="testpass123",
            first_name="Ctx",
            last_name="User",
            account_status=User.AccountStatus.ACTIVE,
        )

    @patch("apps.services.auth_service.render_to_string")
    @patch("apps.services.auth_service.EmailMultiAlternatives")
    def test_login_email_passes_contact_email(self, mock_email, mock_render):
        from apps.services.auth_service import send_login_code
        from django.conf import settings

        mock_render.return_value = "<html>login</html>"
        mock_email.return_value = MagicMock()

        self.assertTrue(send_login_code(self.user.email))

        ctx = mock_render.call_args[0][1]
        self.assertEqual(ctx["CONTACT_EMAIL"], settings.SUPPORT_EMAIL)

    @patch("apps.services.auth_service.render_to_string")
    @patch("apps.services.auth_service.EmailMultiAlternatives")
    def test_password_reset_email_passes_contact_email(self, mock_email, mock_render):
        from apps.services.auth_service import send_password_reset
        from django.conf import settings

        mock_render.return_value = "<html>reset</html>"
        mock_email.return_value = MagicMock()

        send_password_reset(self.user.email, ip="127.0.0.1", user_agent="pytest")

        ctx = mock_render.call_args[0][1]
        self.assertEqual(ctx["CONTACT_EMAIL"], settings.SUPPORT_EMAIL)

    @patch("apps.services.auth_service.render_to_string")
    @patch("apps.services.auth_service.EmailMultiAlternatives")
    def test_password_changed_email_passes_contact_email(self, mock_email, mock_render):
        from apps.services.auth_service import _send_password_changed_notification
        from django.conf import settings

        mock_render.return_value = "<html>changed</html>"
        mock_email.return_value = MagicMock()

        _send_password_changed_notification(self.user, ip="127.0.0.1")

        ctx = mock_render.call_args[0][1]
        self.assertEqual(ctx["CONTACT_EMAIL"], settings.SUPPORT_EMAIL)

    def test_no_hardcoded_biotech_email_in_email_templates(self):
        """Templates must not hardcode biotech.futures@sydney.edu.au — use {{ CONTACT_EMAIL }}."""
        import os
        templates_dir = os.path.join(
            os.path.dirname(__import__("apps.services", fromlist=["__file__"]).__file__),
            "templates", "emails",
        )
        for name in os.listdir(templates_dir):
            path = os.path.join(templates_dir, name)
            if not os.path.isfile(path) or not name.endswith(".html"):
                continue
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
            self.assertNotIn(
                "biotech.futures@sydney.edu.au", content,
                f"{name} hardcodes biotech.futures@sydney.edu.au; switch to {{{{ CONTACT_EMAIL }}}}",
            )
