"""Integration tests: real senders consume admin-configured system-emails.

These tests are currently FAILING.
They pin the end-to-end contract: a sender such as
``send_login_code`` or ``send_password_reset`` must honour the wording and the
on/off switches that the admin editor saves, via the shared send helpers in
``apps/services.system_email``.

Right now the senders still build their own messages and ignore the saved
registry state, so every test here (except the locked-login guard at the end)
fails until the send points are rewired to go through ``render_system_email`` /
``is_email_enabled``:

* ``apps/services/auth_service.send_login_code``          -> login_code
* ``apps/services/auth_service.send_password_reset``      -> password_reset
* ``apps/services/auth_service`` password-changed notify  -> password_changed
* ``apps/submissions/emails.py``                          -> submission_confirmation / reminder
* ``apps/events/services.py``                             -> event_promotion / rsvp_reminder
* ``apps/admin/services/announcement.py``                 -> announcement
* the chat digest                                         -> unread_messages
* the grading finalist notify                             -> finalist_notification

Once the senders are wired up, run this module with::

    python manage.py test tests.apps.services.test_system_email_send_integration \
        --settings=config.settings_test

and it should go fully green.

Warning: do NOT mark these ``@unittest.expectedFailure``. They must visibly fail
while the wiring is missing, so the red status is the signal that the work is
incomplete.
"""

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings

from apps.admin.services.system_email import (
    update_email_settings,
    update_email_template,
)
from apps.services.auth_service import send_login_code, send_password_reset
from apps.users.models import User

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


def _owner():
    return User.objects.create_user(
        email="owner@example.com", password="ownerpass"
    )


def _active_user(email="ada@example.com", first_name="Ada"):
    return User.objects.create_user(
        email=email,
        password="StrongPass!42",
        first_name=first_name,
        last_name="Lovelace",
        account_status=User.AccountStatus.ACTIVE,
    )


@override_settings(EMAIL_BACKEND=LOCMEM, AUTH_EMAIL_DISPATCH_SYNC=True)
class SenderConsumesSavedWordingTests(TestCase):
    """The subject/body an admin saves must be what the recipient actually gets."""

    def test_login_code_email_uses_saved_admin_wording(self):
        owner = _owner()
        update_email_template(
            "login_code",
            {
                "subject": "Sign in to {{ brand_name }}",
                "body": "<p>Hi {{ first_name }}, your sign-in code is {{ otp_code }}.</p>",
            },
            requested_by=owner,
        )
        user = _active_user()
        mail.outbox = []

        self.assertTrue(send_login_code(user.email))

        message = mail.outbox[0]
        self.assertEqual(message.subject, f"Sign in to {settings.BRAND_NAME}")
        html = next(
            alt[0] for alt in message.alternatives if alt[1] == "text/html"
        )
        self.assertIn("Hi Ada, your sign-in code is", html)

    def test_password_reset_email_uses_saved_admin_wording(self):
        owner = _owner()
        update_email_template(
            "password_reset",
            {
                "subject": "Reset now {{ first_name }}",
                "body": "<p>Hi {{ first_name }}, reset via {{ reset_link }}.</p>",
            },
            requested_by=owner,
        )
        user = _active_user()
        mail.outbox = []

        send_password_reset(user.email)

        message = mail.outbox[0]
        self.assertEqual(message.subject, "Reset now Ada")
        html = next(
            alt[0] for alt in message.alternatives if alt[1] == "text/html"
        )
        self.assertIn("Hi Ada, reset via", html)


@override_settings(EMAIL_BACKEND=LOCMEM, AUTH_EMAIL_DISPATCH_SYNC=True)
class SenderHonoursTogglesTests(TestCase):
    """The per-type and global switches an admin flips must gate real sends."""

    def test_per_type_switch_off_suppresses_the_sender(self):
        owner = _owner()
        update_email_template("password_reset", {"enabled": False}, requested_by=owner)
        user = _active_user()
        mail.outbox = []

        send_password_reset(user.email)

        self.assertEqual(mail.outbox, [])

    def test_global_switch_off_suppresses_unlocked_sender_emails(self):
        owner = _owner()
        update_email_settings(False, requested_by=owner)
        user = _active_user()
        mail.outbox = []

        send_password_reset(user.email)

        self.assertEqual(mail.outbox, [])

    def test_global_switch_off_never_blocks_the_locked_login_code(self):
        # This guard already passes: the login flow is locked by design. It
        # stays green after the rewiring because the shared toggle path knows
        # that locked types always send.
        owner = _owner()
        update_email_settings(False, requested_by=owner)
        user = _active_user()
        mail.outbox = []

        self.assertTrue(send_login_code(user.email))

        self.assertEqual(len(mail.outbox), 1)