"""
The three auth emails go through the shared system email path.
Run with: python manage.py test tests.apps.services.test_auth_system_emails
"""

from django.core import mail
from django.test import TestCase, override_settings

from apps.services import auth_service
from apps.services.models import PasswordResetToken, SystemEmailSettings, SystemEmailTemplate
from apps.users.models import User

STRONG_PWD_OLD = "OldStrongPass!42"
STRONG_PWD_NEW = "NewStrongPass!7Q"


def _user(email="auth.emails@example.com"):
    return User.objects.create_user(
        email=email,
        password=STRONG_PWD_OLD,
        first_name="Ada",
        last_name="Lovelace",
        account_status=User.AccountStatus.ACTIVE,
    )


def _html(message):
    return next(body for body, mimetype in message.alternatives if mimetype == "text/html")


@override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
class UneditedAuthEmailsTests(TestCase):
    """With nothing saved, the auth emails look exactly as they did before."""

    def test_login_code_keeps_its_subject_template_and_plain_text(self):
        user = _user()
        self.assertTrue(auth_service.send_login_code(user.email))

        message = mail.outbox[0]
        self.assertEqual(message.subject, "BIOTech Futures: Log in securely")
        self.assertIn("Use this link to log in:", message.body)
        self.assertIn("Hi Ada", _html(message))
        self.assertEqual(message.mixed_subtype, "related")  # logo attached

    def test_password_reset_keeps_its_subject_and_plain_text(self):
        user = _user()
        auth_service.send_password_reset(user.email)

        message = mail.outbox[0]
        token = PasswordResetToken.objects.get(user=user).token
        self.assertEqual(message.subject, "BIOTech Futures: Update your password")
        self.assertIn(token, message.body)
        self.assertIn(token, _html(message))

    def test_password_changed_keeps_its_subject_and_plain_text(self):
        user = _user()
        auth_service._send_password_changed_notification(user, ip="203.0.113.7")

        message = mail.outbox[0]
        self.assertEqual(message.subject, "BIOTech Futures: Your password was changed")
        self.assertIn("password was just changed", message.body)
        self.assertIn("203.0.113.7", _html(message))


@override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
class EditedAuthEmailsTests(TestCase):
    def test_edited_login_email_derives_plain_text_from_the_new_body(self):
        SystemEmailTemplate.objects.create(
            key="login_code",
            subject="Your code",
            body_html="<p>Hi {{ first_name }}, your code is {{ otp_code }}.</p>",
        )
        user = _user()
        auth_service.send_login_code(user.email)

        message = mail.outbox[0]
        self.assertEqual(message.subject, "Your code")
        self.assertRegex(message.body, r"^Hi Ada, your code is \d{6}\.$")

    def test_edited_password_changed_email_uses_the_saved_wording(self):
        SystemEmailTemplate.objects.create(
            key="password_changed",
            subject="Heads up {{ first_name }}",
            body_html="<p>Changed from {{ request_ip }}.</p>",
        )
        user = _user()
        auth_service._send_password_changed_notification(user, ip="203.0.113.7")

        message = mail.outbox[0]
        self.assertEqual(message.subject, "Heads up Ada")
        self.assertIn("<p>Changed from 203.0.113.7.</p>", _html(message))


@override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
class AuthEmailTogglesTests(TestCase):
    def test_locked_reset_still_sends_even_with_its_own_row_disabled(self):
        SystemEmailTemplate.objects.create(key="password_reset", is_enabled=False)
        user = _user()
        auth_service.send_password_reset(user.email)

        # Password reset is account-critical: it cannot be switched off, so the
        # email still goes out even if a row with is_enabled=False exists.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(PasswordResetToken.objects.filter(user=user).count(), 1)

    def test_locked_password_changed_notification_still_sends_even_disabled(self):
        SystemEmailTemplate.objects.create(key="password_changed", is_enabled=False)
        user = _user()
        token = PasswordResetToken.create_for_user(user).token

        auth_service.confirm_password_reset(token=token, new_password=STRONG_PWD_NEW)

        user.refresh_from_db()
        self.assertTrue(user.check_password(STRONG_PWD_NEW))
        # Account-security emails are locked: the notification still goes out.
        self.assertEqual(len(mail.outbox), 1)

    def test_login_code_sends_with_every_switch_off(self):
        SystemEmailSettings.objects.create(emails_enabled=False)
        SystemEmailTemplate.objects.create(key="login_code", is_enabled=False)
        user = _user()

        self.assertTrue(auth_service.send_login_code(user.email))
        self.assertEqual(len(mail.outbox), 1)
