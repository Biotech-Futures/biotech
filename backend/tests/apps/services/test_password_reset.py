"""
Tests for the user-facing password reset flow.
Run with: python manage.py test tests.apps.services.test_password_reset
"""

from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.services import auth_service
from apps.services.models import LoginToken, PasswordResetToken
from apps.user_sessions.models import UserSession
from config.errors import InvalidOrExpiredResetToken, WeakPassword

User = get_user_model()


# Strong enough to pass MinimumLength + CommonPassword + Numeric + similarity validators.
STRONG_PWD_OLD = "OldStrongPass!42"
STRONG_PWD_NEW = "NewStrongPass!7Q"


def _make_user(email="reset@example.com", *, password=STRONG_PWD_OLD,
               status=None, first_name="R", last_name="U"):
    return User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        account_status=status or User.AccountStatus.ACTIVE,
    )


# --- model -----------------------------------------------------------------

class PasswordResetTokenModelTest(TestCase):

    def setUp(self):
        self.user = _make_user()

    def test_generate_token_is_high_entropy_urlsafe(self):
        token = PasswordResetToken.generate_token()
        # secrets.token_urlsafe(32) -> 43 base64url chars, no padding
        self.assertGreaterEqual(len(token), 40)
        self.assertTrue(all(c.isalnum() or c in "-_" for c in token))

    def test_create_for_user_invalidates_prior_unused_tokens(self):
        first = PasswordResetToken.create_for_user(self.user)
        second = PasswordResetToken.create_for_user(self.user)

        first.refresh_from_db()
        self.assertTrue(first.used)
        self.assertIsNotNone(first.used_at)
        self.assertFalse(second.used)
        self.assertTrue(second.is_valid)

    def test_consume_marks_token_used_and_returns_row(self):
        token = PasswordResetToken.create_for_user(self.user)
        consumed = PasswordResetToken.consume(token.token)

        self.assertIsNotNone(consumed)
        self.assertEqual(consumed.id, token.id)
        token.refresh_from_db()
        self.assertTrue(token.used)
        self.assertIsNotNone(token.used_at)

    def test_consume_returns_none_for_unknown_token(self):
        self.assertIsNone(PasswordResetToken.consume("nope"))

    def test_consume_returns_none_for_used_token(self):
        token = PasswordResetToken.create_for_user(self.user)
        PasswordResetToken.consume(token.token)
        self.assertIsNone(PasswordResetToken.consume(token.token))

    def test_consume_returns_none_for_expired_token(self):
        # bypass create_for_user which would set a fresh expiry
        token = PasswordResetToken.objects.create(
            user=self.user,
            token=PasswordResetToken.generate_token(),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertIsNone(PasswordResetToken.consume(token.token))

    def test_cleanup_expired_drops_expired_only(self):
        PasswordResetToken.objects.create(
            user=self.user,
            token=PasswordResetToken.generate_token(),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        PasswordResetToken.create_for_user(self.user)  # valid
        deleted = PasswordResetToken.cleanup_expired()

        self.assertEqual(deleted, 1)
        self.assertEqual(PasswordResetToken.objects.count(), 1)


# --- service: send ---------------------------------------------------------

@patch('apps.services.auth_service.EmailMultiAlternatives')
class SendPasswordResetServiceTest(TestCase):

    def setUp(self):
        self.user = _make_user()

    def test_unknown_email_silent_no_op(self, mock_mail):
        auth_service.send_password_reset("ghost@example.com")
        self.assertEqual(PasswordResetToken.objects.count(), 0)
        mock_mail.assert_not_called()

    def test_active_user_creates_token_and_sends_email(self, mock_mail):
        msg = MagicMock()
        mock_mail.return_value = msg

        auth_service.send_password_reset(self.user.email, ip="1.2.3.4", user_agent="UA")

        self.assertEqual(PasswordResetToken.objects.filter(user=self.user).count(), 1)
        token = PasswordResetToken.objects.get(user=self.user)
        self.assertEqual(token.requested_ip, "1.2.3.4")
        self.assertEqual(token.requested_user_agent, "UA")

        mock_mail.assert_called_once()
        msg.send.assert_called_once()

    def test_email_link_carries_token_and_redirect_url(self, mock_mail):
        msg = MagicMock()
        mock_mail.return_value = msg

        with override_settings(PASSWORD_RESET_REDIRECT_URL="https://app.example/reset"):
            auth_service.send_password_reset(self.user.email)

        token = PasswordResetToken.objects.get(user=self.user)
        # body kwarg holds the plaintext fallback containing the link
        kwargs = mock_mail.call_args.kwargs
        self.assertIn("https://app.example/reset", kwargs["body"])
        self.assertIn(token.token, kwargs["body"])
        self.assertEqual(kwargs["to"], [self.user.email])

    def test_blocked_statuses_silent_no_op(self, mock_mail):
        for status_value in ('invited', 'pending', 'suspended', 'deactivated'):
            self.user.apply_account_status(status_value)

            auth_service.send_password_reset(self.user.email)

        self.assertEqual(PasswordResetToken.objects.count(), 0)
        mock_mail.assert_not_called()

    def test_issuing_twice_invalidates_first_token(self, mock_mail):
        auth_service.send_password_reset(self.user.email)
        first = PasswordResetToken.objects.get(user=self.user)

        auth_service.send_password_reset(self.user.email)
        first.refresh_from_db()

        self.assertTrue(first.used)
        self.assertEqual(
            PasswordResetToken.objects.filter(user=self.user, used=False).count(), 1,
        )

    def test_smtp_failure_does_not_raise(self, mock_mail):
        # If SMTP errors propagated, the view would 500 for known emails while
        # unknown ones return 200 — that gap is the enumeration vector we close.
        msg = MagicMock()
        msg.send.side_effect = RuntimeError("smtp down")
        mock_mail.return_value = msg

        auth_service.send_password_reset(self.user.email)  # must not raise

        # Token still gets persisted; user can request another link once SMTP recovers.
        self.assertEqual(PasswordResetToken.objects.filter(user=self.user).count(), 1)


# --- service: confirm ------------------------------------------------------

@patch('apps.services.auth_service.EmailMultiAlternatives')
class ConfirmPasswordResetServiceTest(TestCase):

    def setUp(self):
        self.user = _make_user()
        self.token_row = PasswordResetToken.create_for_user(self.user, ip="9.9.9.9")
        self.token = self.token_row.token

    def test_happy_path_updates_password(self, _mock_mail):
        auth_service.confirm_password_reset(token=self.token, new_password=STRONG_PWD_NEW)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(STRONG_PWD_NEW))
        self.assertFalse(self.user.check_password(STRONG_PWD_OLD))

    def test_happy_path_sends_notification_email(self, mock_mail):
        msg = MagicMock()
        mock_mail.return_value = msg

        auth_service.confirm_password_reset(token=self.token, new_password=STRONG_PWD_NEW)

        mock_mail.assert_called_once()
        # subject confirms it's the change-notification email, not the reset request
        self.assertIn("changed", mock_mail.call_args.kwargs["subject"].lower())
        msg.send.assert_called_once()

    def test_happy_path_marks_token_used(self, _mock_mail):
        auth_service.confirm_password_reset(token=self.token, new_password=STRONG_PWD_NEW)
        self.token_row.refresh_from_db()
        self.assertTrue(self.token_row.used)

    def test_happy_path_revokes_user_sessions(self, _mock_mail):
        open_session = UserSession.objects.create(user=self.user)

        auth_service.confirm_password_reset(token=self.token, new_password=STRONG_PWD_NEW)

        open_session.refresh_from_db()
        self.assertIsNotNone(open_session.revoked_at)
        self.assertIsNotNone(open_session.ended_at)

    def test_happy_path_burns_outstanding_login_tokens(self, _mock_mail):
        login_token = LoginToken.create_for_user(self.user)

        auth_service.confirm_password_reset(token=self.token, new_password=STRONG_PWD_NEW)

        login_token.refresh_from_db()
        self.assertTrue(login_token.used)

    def test_happy_path_does_not_change_account_status(self, _mock_mail):
        original = self.user.account_status
        auth_service.confirm_password_reset(token=self.token, new_password=STRONG_PWD_NEW)
        self.user.refresh_from_db()
        self.assertEqual(self.user.account_status, original)

    def test_invalid_token_raises_and_does_not_notify(self, mock_mail):
        with self.assertRaises(InvalidOrExpiredResetToken):
            auth_service.confirm_password_reset(token="bogus", new_password=STRONG_PWD_NEW)
        mock_mail.assert_not_called()

    def test_used_token_raises(self, _mock_mail):
        auth_service.confirm_password_reset(token=self.token, new_password=STRONG_PWD_NEW)
        with self.assertRaises(InvalidOrExpiredResetToken):
            auth_service.confirm_password_reset(token=self.token, new_password=STRONG_PWD_NEW)

    def test_weak_password_raises_with_field_errors(self, mock_mail):
        with self.assertRaises(WeakPassword) as cm:
            auth_service.confirm_password_reset(token=self.token, new_password="abc")

        self.assertIn("fields", cm.exception.extra)
        self.assertIn("new_password", cm.exception.extra["fields"])
        self.assertGreater(len(cm.exception.extra["fields"]["new_password"]), 0)
        # notification only fires after a successful reset
        mock_mail.assert_not_called()

    def test_notification_email_failure_does_not_rollback(self, mock_mail):
        # Render call inside the notification helper; force send() to blow up.
        msg = MagicMock()
        msg.send.side_effect = RuntimeError("smtp down")
        mock_mail.return_value = msg

        # Should NOT raise — password change must persist regardless of email failure.
        auth_service.confirm_password_reset(token=self.token, new_password=STRONG_PWD_NEW)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(STRONG_PWD_NEW))


# --- endpoints -------------------------------------------------------------

@patch('apps.services.auth_service.EmailMultiAlternatives')
class PasswordResetEndpointsTest(TestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = _make_user()

    # --- request endpoint ---

    def test_request_unknown_email_returns_200_no_leak(self, mock_mail):
        r = self.client.post(
            "/services/password-reset/request/",
            {"email": "ghost@example.com"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PasswordResetToken.objects.count(), 0)
        mock_mail.assert_not_called()

    def test_request_known_email_returns_200_and_creates_token(self, mock_mail):
        r = self.client.post(
            "/services/password-reset/request/",
            {"email": self.user.email},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PasswordResetToken.objects.filter(user=self.user).count(), 1)
        mock_mail.assert_called_once()

    def test_request_invalid_email_format_returns_400(self, _mock_mail):
        r = self.client.post(
            "/services/password-reset/request/",
            {"email": "not-an-email"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_request_per_email_rate_limit(self, _mock_mail):
        for _ in range(3):
            self.client.post(
                "/services/password-reset/request/",
                {"email": self.user.email},
                format="json",
            )
        r = self.client.post(
            "/services/password-reset/request/",
            {"email": self.user.email},
            format="json",
        )
        self.assertEqual(r.status_code, 429)

    # --- confirm endpoint ---

    def test_confirm_happy_path(self, _mock_mail):
        token = PasswordResetToken.create_for_user(self.user)
        r = self.client.post(
            "/services/password-reset/confirm/",
            {"token": token.token, "new_password": STRONG_PWD_NEW},
            format="json",
        )
        self.assertEqual(r.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(STRONG_PWD_NEW))

    def test_confirm_then_login_with_new_password_succeeds(self, _mock_mail):
        token = PasswordResetToken.create_for_user(self.user)
        self.client.post(
            "/services/password-reset/confirm/",
            {"token": token.token, "new_password": STRONG_PWD_NEW},
            format="json",
        )

        login_resp = self.client.post(
            "/users/login/",
            {"email": self.user.email, "password": STRONG_PWD_NEW},
            format="json",
        )
        self.assertEqual(login_resp.status_code, 200)

    def test_confirm_then_old_password_rejected(self, _mock_mail):
        token = PasswordResetToken.create_for_user(self.user)
        self.client.post(
            "/services/password-reset/confirm/",
            {"token": token.token, "new_password": STRONG_PWD_NEW},
            format="json",
        )

        login_resp = self.client.post(
            "/users/login/",
            {"email": self.user.email, "password": STRONG_PWD_OLD},
            format="json",
        )
        self.assertEqual(login_resp.status_code, 401)

    def test_confirm_invalid_token_returns_400_with_code(self, _mock_mail):
        r = self.client.post(
            "/services/password-reset/confirm/",
            {"token": "bogus-token-xyz", "new_password": STRONG_PWD_NEW},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json().get("code"), "invalid_or_expired_reset_token")

    def test_confirm_weak_password_returns_400_with_fields(self, _mock_mail):
        token = PasswordResetToken.create_for_user(self.user)
        r = self.client.post(
            "/services/password-reset/confirm/",
            {"token": token.token, "new_password": "abc"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        body = r.json()
        self.assertEqual(body.get("code"), "weak_password")
        self.assertIn("fields", body)
        self.assertIn("new_password", body["fields"])

    def test_confirm_brute_force_lockout(self, _mock_mail):
        token = PasswordResetToken.create_for_user(self.user)
        # 5 bad attempts on the SAME token (token itself is wrong, so each fails)
        for _ in range(5):
            self.client.post(
                "/services/password-reset/confirm/",
                {"token": "wrong-token", "new_password": STRONG_PWD_NEW},
                format="json",
            )
        r = self.client.post(
            "/services/password-reset/confirm/",
            {"token": "wrong-token", "new_password": STRONG_PWD_NEW},
            format="json",
        )
        self.assertEqual(r.status_code, 429)

    def test_confirm_per_ip_lockout_across_distinct_tokens(self, _mock_mail):
        # Per-token limit doesn't fire because each guess is unique. The per-IP
        # cap (20) is what actually stops the brute force in this scenario.
        for i in range(20):
            self.client.post(
                "/services/password-reset/confirm/",
                {"token": f"wrong-{i}", "new_password": STRONG_PWD_NEW},
                format="json",
            )
        r = self.client.post(
            "/services/password-reset/confirm/",
            {"token": "wrong-21", "new_password": STRONG_PWD_NEW},
            format="json",
        )
        self.assertEqual(r.status_code, 429)

    def test_confirm_flushes_django_session_rows_for_user(self, _mock_mail):
        # Log in via the real login endpoint to seed a django_session row.
        login_resp = self.client.post(
            "/users/login/",
            {"email": self.user.email, "password": STRONG_PWD_OLD},
            format="json",
        )
        self.assertEqual(login_resp.status_code, 200)
        sessions_before = Session.objects.count()
        self.assertGreaterEqual(sessions_before, 1)

        token = PasswordResetToken.create_for_user(self.user)
        self.client.post(
            "/services/password-reset/confirm/",
            {"token": token.token, "new_password": STRONG_PWD_NEW},
            format="json",
        )

        # The user's session row(s) must be gone — verify by decoding what's left.
        for s in Session.objects.all():
            self.assertNotEqual(
                str(s.get_decoded().get("_auth_user_id")), str(self.user.pk),
            )
