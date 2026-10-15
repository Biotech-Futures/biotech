"""Every email gets one more try over a fresh connection, unless the mail
server refused the address itself: at once for a single email, or a few
seconds after a run of them has tried everyone (``RetryLater``)."""
import smtplib
from unittest import mock

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, TestCase, override_settings

from apps.services.models import SystemEmailLog
from apps.services.retry import RetryLater, send_with_retry
from apps.services.system_email import FAILED, SENT, send_system_email

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"

DROPPED = smtplib.SMTPServerDisconnected("dropped")
REFUSED = smtplib.SMTPRecipientsRefused({"to@example.com": (550, b"No such user")})
RESET_CONTEXT = {"First_Name": "Alex", "RESET_PASSWORD_LINK": "https://example.test/reset?token=abc", "EXPIRY_MINUTES": 30}


def _message(connection=None):
    return EmailMultiAlternatives("Hi", "Body", "from@example.com", ["to@example.com"], connection=connection)


@override_settings(EMAIL_BACKEND=LOCMEM)
class SendWithRetryTests(SimpleTestCase):
    def test_a_failed_send_goes_on_its_second_try_over_a_fresh_connection(self):
        connection = mock.Mock()
        with mock.patch.object(EmailMultiAlternatives, "send", side_effect=[DROPPED, 1]) as send:
            self.assertEqual(send_with_retry(_message(connection)), 1)
        self.assertEqual(send.call_count, 2)
        connection.close.assert_called_once()
        connection.open.assert_called_once()

    def test_a_second_failure_is_raised(self):
        with mock.patch.object(EmailMultiAlternatives, "send", side_effect=[DROPPED, DROPPED]) as send:
            with self.assertRaises(smtplib.SMTPServerDisconnected):
                send_with_retry(_message())
        self.assertEqual(send.call_count, 2)

    def test_a_refused_address_is_not_tried_again(self):
        with mock.patch.object(EmailMultiAlternatives, "send", side_effect=[REFUSED, 1]) as send:
            with self.assertRaises(smtplib.SMTPRecipientsRefused):
                send_with_retry(_message())
        self.assertEqual(send.call_count, 1)

    def test_a_send_that_goes_goes_once(self):
        send_with_retry(_message())
        self.assertEqual(len(mail.outbox), 1)


class RetryLaterTests(SimpleTestCase):
    def test_kept_sends_go_once_more_a_few_seconds_on_over_a_fresh_connection(self):
        connection = mock.Mock()
        later = RetryLater(connection)
        goes, fails = mock.Mock(), mock.Mock(side_effect=DROPPED)
        self.assertTrue(later.keep(DROPPED, "a", goes))
        self.assertTrue(later.keep(DROPPED, "b", fails))

        with override_settings(BULK_EMAIL_RETRY_SECONDS=5), mock.patch("apps.services.retry.time.sleep") as sleep:
            results = later.run()

        sleep.assert_called_once_with(5)
        self.assertEqual(results, [("a", None), ("b", DROPPED)])
        goes.assert_called_once_with()
        connection.open.assert_called_once()
        # Closed to start afresh, and closed again once done.
        self.assertEqual(connection.close.call_count, 2)
        self.assertFalse(later)

    def test_a_refused_address_is_not_kept(self):
        later = RetryLater()
        self.assertFalse(later.keep(REFUSED, "a", mock.Mock()))
        self.assertFalse(later)
        with mock.patch("apps.services.retry.time.sleep") as sleep:
            self.assertEqual(later.run(), [])
        sleep.assert_not_called()

    def test_none_go_when_the_server_cannot_be_reached_again(self):
        connection = mock.Mock()
        connection.open.side_effect = DROPPED
        later = RetryLater(connection)
        resend = mock.Mock()
        later.keep(DROPPED, "a", resend)
        with mock.patch("apps.services.retry.time.sleep"):
            self.assertEqual(later.run(), [("a", DROPPED)])
        resend.assert_not_called()


@override_settings(EMAIL_BACKEND=LOCMEM)
class SystemEmailRetryTests(TestCase):
    def test_a_system_email_that_fails_once_is_sent_and_logged_as_sent(self):
        with mock.patch.object(EmailMultiAlternatives, "send", side_effect=[DROPPED, 1]) as send:
            self.assertEqual(send_system_email("password_reset", "alex@example.test", RESET_CONTEXT), SENT)
        self.assertEqual(send.call_count, 2)
        log = SystemEmailLog.objects.get(key="password_reset")
        self.assertIsNotNone(log.last_sent_at)
        self.assertEqual(log.missed, [])

    def test_a_system_email_that_fails_twice_is_a_miss(self):
        with mock.patch.object(EmailMultiAlternatives, "send", side_effect=[DROPPED, DROPPED]) as send:
            self.assertEqual(send_system_email("password_reset", "alex@example.test", RESET_CONTEXT), FAILED)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(len(SystemEmailLog.objects.get(key="password_reset").missed), 1)

    @override_settings(AUTH_EMAIL_DISPATCH_SYNC=True)
    def test_one_sent_in_the_background_is_tried_again_too(self):
        with mock.patch.object(EmailMultiAlternatives, "send", side_effect=[DROPPED, 1]) as send:
            self.assertEqual(
                send_system_email("password_reset", "alex@example.test", RESET_CONTEXT, background=True), SENT,
            )
        self.assertEqual(send.call_count, 2)
        self.assertEqual(SystemEmailLog.objects.get(key="password_reset").missed, [])
