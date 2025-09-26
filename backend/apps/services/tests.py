"""
Tests for custom LoginToken OTP system in auth_service
Run with: python manage.py test apps.services
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock

from .auth_service import send_login_code, verify_login_code
from .models import LoginToken

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
            from .auth_service import send_login_code, verify_login_code
            from .models import LoginToken
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

    def test_multiple_tokens_per_user(self):
        """Test that user can have multiple tokens (but only use each once)"""
        # Create multiple tokens
        token1 = LoginToken.create_for_user(self.user)
        token2 = LoginToken.create_for_user(self.user)

        # Both should be valid initially
        self.assertTrue(token1.is_valid)
        self.assertTrue(token2.is_valid)

        # Use first token
        result1 = verify_login_code(self.user.email, token1.token)
        self.assertTrue(result1)

        # First token should be used, second still valid
        token1.refresh_from_db()
        token2.refresh_from_db()
        self.assertTrue(token1.used)
        self.assertFalse(token2.used)

        # Second token should still work
        result2 = verify_login_code(self.user.email, token2.token)
        self.assertTrue(result2)