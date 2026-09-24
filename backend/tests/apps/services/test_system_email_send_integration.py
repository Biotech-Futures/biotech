"""Integration tests: real senders consume admin-configured system-emails.

These pin the end-to-end contract: a sender such as ``send_login_code`` or
``notify_waitlist_promoted`` must honour the wording and the on/off switches
that the admin editor saves, via the shared send helpers in
``apps/services.system_email``. The senders are now wired through
``render_system_email`` / ``is_email_enabled``, so these are green (and must
stay green) — do NOT mark them ``@unittest.expectedFailure``.

Note the three *account-security* types (``login_code``, ``password_reset``,
``password_changed``) are locked: an admin cannot switch them off, and these
tests pin that they keep sending even when the global switch is off or their
own row says disabled. Toggle tests therefore use an unlocked type
(``event_promotion``) as the sender under test.

Run with::

    python manage.py test tests.apps.services.test_system_email_send_integration \
        --settings=config.settings_test
"""

from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings

from apps.admin.services.system_email import (
    update_email_settings,
    update_email_template,
)
from apps.events.models import Events
from apps.events.promotion_email import notify_waitlist_promoted
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


def _event():
    start = datetime.now(dt_timezone.utc) + timedelta(days=1)
    return Events.objects.create(
        event_name="BIOTech Symposium",
        start_datetime=start,
        ends_datetime=start + timedelta(hours=2),
        event_format="in_person",
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
    """The per-type and global switches an admin flips must gate real sends.

    Uses the unlocked ``event_promotion`` sender: the account-security types
    are locked and must keep sending (covered below).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="promoted@example.com", password="pw"
        )

    def test_per_type_switch_off_suppresses_the_sender(self):
        owner = _owner()
        event = _event()
        update_email_template("event_promotion", {"enabled": False}, requested_by=owner)
        mail.outbox = []

        notify_waitlist_promoted(event_id=event.id, user_id=self.user.id)

        self.assertEqual(mail.outbox, [])

    def test_global_switch_off_suppresses_unlocked_sender_emails(self):
        owner = _owner()
        event = _event()
        update_email_settings(False, requested_by=owner)
        mail.outbox = []

        notify_waitlist_promoted(event_id=event.id, user_id=self.user.id)

        self.assertEqual(mail.outbox, [])

    def test_global_switch_off_never_blocks_locked_account_security_emails(self):
        # Sign-in, password reset and password change must always be able to
        # reach the user; the shared toggle path knows they are locked.
        owner = _owner()
        update_email_settings(False, requested_by=owner)
        user = _active_user()
        mail.outbox = []

        self.assertTrue(send_login_code(user.email))
        send_password_reset(user.email)

        self.assertEqual(len(mail.outbox), 2)