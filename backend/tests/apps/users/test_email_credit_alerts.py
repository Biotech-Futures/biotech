"""Low-credit alerts (apps.users.email_credit_alerts), sent through the system
email path when the QEV balance drops below 500 and 100. HTTP is mocked; the
alerts land in Django's test outbox."""
import smtplib
from unittest import mock

from django.core import mail
from django.test import override_settings

from apps.services.email_registry import get_email_type
from apps.services.models import SystemEmailSettings, SystemEmailTemplate
from apps.services.system_email import FAILED, SENT, SKIPPED, sender_for
from apps.users import email_credit_alerts, email_credits
from apps.users import email_verification as ev
from apps.users.models import EmailVerificationCredits

from .test_email_verification import KEY, QevTestCase, response

HEADER = "X-QEV-Remaining-Credits"


@override_settings(QEV_LOW_CREDIT_THRESHOLDS=(500, 100), QEV_ALERT_EMAIL="info@biotechfutures.org")
class AlertTestCase(QevTestCase):
    def read(self, remaining):
        """One QEV answer reporting ``remaining`` credits."""
        email_credits.record_remaining({HEADER: str(remaining)})

    def credits(self):
        return EmailVerificationCredits.get()

    def alerted(self):
        return self.credits().alerted_thresholds

    def assertAlerts(self, *thresholds):
        """The emails sent so far were alerts for these levels, in order."""
        self.assertEqual(len(mail.outbox), len(thresholds), [m.subject for m in mail.outbox])
        for message, threshold in zip(mail.outbox, thresholds):
            self.assertIn(f"alert level of {threshold}", message.body)


class AlertLevelTests(AlertTestCase):
    def test_a_balance_above_every_level_sends_nothing(self):
        self.read(2500)
        self.read(500)

        self.assertAlerts()
        self.assertEqual(self.alerted(), [])

    def test_dropping_below_500_sends_one_alert_and_not_again_at_450(self):
        self.read(2500)
        self.read(499)
        self.read(450)

        self.assertAlerts(500)
        self.assertEqual(self.alerted(), [500])
        self.assertEqual(self.credits().remaining, 450)

    def test_dropping_below_100_sends_one_more_alert(self):
        self.read(499)
        self.read(99)
        self.read(50)
        self.read(0)

        self.assertAlerts(500, 100)
        self.assertEqual(self.alerted(), [500, 100])

    def test_one_reading_below_both_levels_sends_a_single_alert_for_the_lower(self):
        self.read(80)

        self.assertAlerts(100)
        self.assertIn("<strong>80</strong>", mail.outbox[0].alternatives[0][0])
        self.assertEqual(self.alerted(), [500, 100])

    def test_a_top_up_lets_the_alerts_fire_again(self):
        self.read(80)
        self.read(2500)

        self.assertEqual(self.alerted(), [])
        self.read(499)
        self.read(99)

        self.assertAlerts(100, 500, 100)

    def test_a_partial_top_up_resets_only_the_levels_it_is_back_above(self):
        self.read(80)
        self.read(300)

        self.assertEqual(self.alerted(), [500])
        self.read(90)

        self.assertAlerts(100, 100)

    def test_two_rapid_readings_send_one_alert(self):
        self.answer(response(headers={HEADER: "499"}), response(headers={HEADER: "498"}))

        ev.verify_emails(["a@example.com", "b@example.com"])

        self.assertAlerts(500)
        self.assertEqual(self.credits().remaining, 498)

    def test_the_balance_row_is_locked_while_the_alert_is_decided(self):
        manager = EmailVerificationCredits.objects
        decided_while_locked = []
        original = email_credit_alerts.alert_if_low

        def spy(credits):
            decided_while_locked.append(lock.called)
            original(credits)

        with mock.patch.object(manager, "select_for_update", wraps=manager.select_for_update) as lock, \
                mock.patch.object(email_credit_alerts, "alert_if_low", side_effect=spy):
            self.read(450)

        self.assertEqual(decided_while_locked, [True])
        self.assertAlerts(500)

    @override_settings(QEV_LOW_CREDIT_THRESHOLDS=(1000,))
    def test_the_levels_come_from_the_setting(self):
        self.read(999)

        self.assertAlerts(1000)
        self.assertEqual(self.alerted(), [1000])


class AlertEmailTests(AlertTestCase):
    def test_the_alert_goes_to_the_info_inbox_and_says_what_to_do(self):
        self.read(450)

        message = mail.outbox[0]
        self.assertEqual(message.to, ["info@biotechfutures.org"])
        self.assertIn("Email verification credits low (450 left)", message.subject)
        self.assertIn("450", message.body)
        self.assertIn("add more credits to the QuickEmailVerification account", message.body)
        self.assertIn("registrations still go through", message.body)

    @override_settings(QEV_ALERT_EMAIL="alerts@example.org")
    def test_the_recipient_comes_from_the_setting(self):
        self.read(450)

        self.assertEqual(mail.outbox[0].to, ["alerts@example.org"])

    def test_the_alert_type_is_locked(self):
        self.assertTrue(get_email_type("email_credits_low").locked)

    def test_switching_system_emails_off_does_not_stop_the_alert(self):
        SystemEmailSettings.objects.create(emails_enabled=False)
        SystemEmailTemplate.objects.create(key="email_credits_low", is_enabled=False)

        self.read(450)

        self.assertAlerts(500)

    def test_it_is_sent_straight_away_not_queued(self):
        with mock.patch.object(email_credit_alerts, "send_system_email", wraps=email_credit_alerts.send_system_email) as send:
            self.read(450)

        args, kwargs = send.call_args
        self.assertEqual(args, ("email_credits_low", "info@biotechfutures.org", {"REMAINING": 450, "THRESHOLD": 500}))
        self.assertFalse(kwargs["background"])
        self.assertAlerts(500)

    def test_it_goes_from_its_usual_mailbox_over_a_connection_with_a_short_timeout(self):
        sender = sender_for("email_credits_low")
        made = []
        real_connect = email_credit_alerts.sender_connection

        def connect_and_keep(*args, **kwargs):
            made.append(real_connect(*args, **kwargs))
            return made[-1]

        with mock.patch.object(email_credit_alerts, "sender_connection", side_effect=connect_and_keep) as connect, \
                mock.patch.object(email_credit_alerts, "send_system_email",
                                  wraps=email_credit_alerts.send_system_email) as send:
            self.read(450)

        self.assertEqual(email_credit_alerts.ALERT_SMTP_TIMEOUT_SECONDS, 5)
        connect.assert_called_once_with(sender, timeout=5)
        kwargs = send.call_args.kwargs
        self.assertIs(kwargs["connection"], made[0])
        self.assertEqual(kwargs["from_email"], sender.from_email)
        self.assertEqual(mail.outbox[0].from_email, sender.from_email)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_TIMEOUT=20)
    def test_the_smtp_connection_uses_the_short_timeout_not_the_site_wide_one(self):
        with mock.patch.object(email_credit_alerts, "send_system_email", return_value=SENT) as send:
            self.read(450)

        connection = send.call_args.kwargs["connection"]
        self.assertEqual(type(connection).__module__, "django.core.mail.backends.smtp")
        self.assertEqual(connection.timeout, 5)


class AlertFailureTests(AlertTestCase):
    def test_an_alert_that_raises_isnt_marked_sent_and_is_tried_next_reading(self):
        with mock.patch.object(email_credit_alerts, "send_system_email", side_effect=RuntimeError("smtp down")):
            with self.captured_logs() as records:
                self.read(450)

        self.assertEqual(self.alerted(), [])
        self.assertEqual(self.credits().remaining, 450)
        self.assertIn("email_credits.alert_failed threshold=500 error=RuntimeError", [r.getMessage() for r in records])

        self.read(440)
        self.assertAlerts(500)
        self.assertEqual(self.alerted(), [500])

    def test_a_mail_server_failure_isnt_marked_sent_and_is_tried_next_reading(self):
        # Turned away by the mail server (one it can't reach is kept to send later).
        failure = smtplib.SMTPDataError(554, b"Message rejected")
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=failure) as send:
            with self.captured_logs() as records:
                self.read(450)

        self.assertEqual(send.call_count, 2)  # the mail system's own retry, then it gives up
        self.assertEqual(mail.outbox, [])
        self.assertEqual(self.alerted(), [])
        self.assertEqual(self.credits().remaining, 450)
        self.assertIn("email_credits.alert_not_sent threshold=500 status=failed", [r.getMessage() for r in records])

        self.read(440)
        self.assertAlerts(500)
        self.assertEqual(self.alerted(), [500])

    def test_an_alert_the_mail_system_reports_not_sent_isnt_marked_sent(self):
        for status in (FAILED, SKIPPED):
            with self.subTest(status=status):
                with mock.patch.object(email_credit_alerts, "send_system_email", return_value=status):
                    self.read(80)

                self.assertEqual(self.alerted(), [])

    def test_a_failed_alert_doesnt_break_the_check(self):
        self.answer(response(headers={HEADER: "450"}))

        with mock.patch.object(email_credit_alerts, "send_system_email", side_effect=RuntimeError("smtp down")):
            result = ev.verify_email("kid@example.com")

        self.assertEqual(result.status, "valid")
        self.assertEqual(self.credits().remaining, 450)

    def test_a_broken_alert_record_still_keeps_the_balance(self):
        credits = self.credits()
        credits.alerted_thresholds = ["not a number"]
        credits.save()

        with self.captured_logs() as records:
            self.read(450)

        self.assertEqual(self.credits().remaining, 450)
        self.assertIn("email_credits.alert_check_failed error=TypeError", [r.getMessage() for r in records])

    def test_nothing_logged_names_the_key_or_the_address(self):
        self.answer(response(headers={HEADER: "80"}))

        with self.captured_logs() as records:
            ev.verify_email("kid@example.com")

        self.assertAlerts(100)
        self.assertNothingSecretIn(records, "kid@example.com")
        self.assertIn("email_credits.alert_sent threshold=100 remaining=80", [r.getMessage() for r in records])
        self.assertNotIn(KEY, mail.outbox[0].body)
