"""Emails the mail server couldn't be reached to send: a dropped connection is
opened again and the email sent once more; when the server still can't be
reached, the email is kept and sent every 10 minutes for 3 days
(apps.services.waiting_email)."""
import smtplib
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.services import waiting_email
from apps.services.email_log import UNREACHABLE, WAITING_REASON, email_log, unseen_failures
from apps.services.models import EmailDeliveryMetric, SystemEmailLog, SystemEmailTemplate, WaitingEmail
from apps.services.retry import WAITING, MailServerDown, lost_connection, send_reconnecting
from apps.services.system_email import SENT, send_system_email, sender_for
from apps.services.waiting_email import WAIT_FOR, send_or_wait, send_waiting

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
DROPPED = smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
REFUSED = smtplib.SMTPRecipientsRefused({"to@example.com": (550, b"No such user")})
CONTEXT = {"First_Name": "Amy", "YEAR": "2026"}
URL = "/api/v1/management/send-waiting-emails/"


def _message(connection=None, to="amy@example.test"):
    return EmailMultiAlternatives("Hi", "Body", sender_for("announcement").from_email, [to], connection=connection)


def _down():
    """Every send fails as a server that can't be reached does."""
    return mock.patch.object(EmailMultiAlternatives, "send", side_effect=DROPPED)


class LostConnectionTests(SimpleTestCase):
    def test_the_connection_failing_is_told_from_an_email_turned_away(self):
        for exc in (DROPPED, TimeoutError("timed out"), ConnectionResetError(), smtplib.SMTPConnectError(421, b"busy"),
                    smtplib.SMTPResponseException(421, b"Service not available")):
            with self.subTest(exc=exc):
                self.assertTrue(lost_connection(exc))
        for exc in (REFUSED, smtplib.SMTPDataError(554, b"rejected"), smtplib.SMTPSenderRefused(550, b"no", "a@x"),
                    ValueError("bad")):
            with self.subTest(exc=exc):
                self.assertFalse(lost_connection(exc))


class SendReconnectingTests(SimpleTestCase):
    def test_a_dropped_connection_is_opened_again_and_the_email_sent_once_more(self):
        connection, send = mock.Mock(), mock.Mock(side_effect=[DROPPED, 1])
        self.assertEqual(send_reconnecting(connection, send), 1)
        self.assertEqual(send.call_count, 2)
        connection.close.assert_called_once()
        connection.open.assert_called_once()

    def test_the_server_still_out_of_reach_is_mail_server_down(self):
        connection = mock.Mock()
        connection.open.side_effect = OSError("unreachable")
        with self.assertRaises(MailServerDown):
            send_reconnecting(connection, mock.Mock(side_effect=DROPPED))
        with self.assertRaises(MailServerDown):
            send_reconnecting(mock.Mock(), mock.Mock(side_effect=[DROPPED, DROPPED]))

    def test_an_email_turned_away_is_raised_without_opening_again(self):
        connection = mock.Mock()
        with self.assertRaises(smtplib.SMTPRecipientsRefused):
            send_reconnecting(connection, mock.Mock(side_effect=REFUSED))
        connection.open.assert_not_called()


@override_settings(EMAIL_BACKEND=LOCMEM)
class SendOrWaitTests(TestCase):
    def setUp(self):
        mail.outbox = []

    def test_an_email_the_server_cant_be_reached_for_is_kept_for_3_days(self):
        before = timezone.now()
        with _down() as send:
            self.assertIs(send_or_wait(_message(), key="announcement"), WAITING)
        # Tried, then tried again over a connection opened again.
        self.assertEqual(send.call_count, 2)
        kept = WaitingEmail.objects.get()
        self.assertEqual((kept.key, kept.mailbox, kept.recipients), ("announcement", "info", ["amy@example.test"]))
        self.assertIn(b"Subject: Hi", bytes(kept.message))
        self.assertGreaterEqual(kept.give_up_at, before + WAIT_FOR)

    def test_one_out_of_date_sooner_is_kept_until_then(self):
        soon = timezone.now() + timedelta(hours=2)
        with _down():
            send_or_wait(_message(), key="rsvp_reminder", until=soon)
        self.assertEqual(WaitingEmail.objects.get().give_up_at, soon)

    def test_login_codes_reset_links_and_ones_already_out_of_date_arent_kept(self):
        for key, until in (("login_code", None), ("password_reset", None), ("rsvp_reminder", timezone.now())):
            with self.subTest(key=key), _down(), self.assertRaises(smtplib.SMTPServerDisconnected):
                send_or_wait(_message(), key=key, until=until)
        self.assertFalse(WaitingEmail.objects.exists())

    def test_an_email_turned_away_is_raised_not_kept(self):
        with mock.patch.object(EmailMultiAlternatives, "send", side_effect=REFUSED):
            with self.assertRaises(smtplib.SMTPRecipientsRefused):
                send_or_wait(_message(), key="announcement")
        self.assertFalse(WaitingEmail.objects.exists())

    @override_settings(MAIL_SERVER_DOWN_SECONDS=60)
    def test_once_a_mailbox_is_found_down_the_rest_are_kept_at_once(self):
        self.addCleanup(waiting_email._note_up, "info")
        with _down() as send:
            send_or_wait(_message(to="a@example.test"), key="announcement")
            send_or_wait(_message(to="b@example.test"), key="announcement")
        # The second didn't wait on the server again.
        self.assertEqual(send.call_count, 2)
        self.assertEqual(WaitingEmail.objects.count(), 2)

    def test_a_system_email_kept_is_sent_and_the_log_lists_it_as_waiting(self):
        with _down():
            self.assertEqual(send_system_email("registration_student", "amy@example.test", CONTEXT), SENT)
        entry = next(item for item in email_log() if item["key"] == "registration_student")
        self.assertEqual(entry["missed"], [])
        self.assertEqual([person["who"] for person in entry["waiting"]], ["amy@example.test"])
        # Waiting isn't failed: the Failed Sending Emails count leaves it out.
        self.assertEqual(unseen_failures(), 0)


@override_settings(EMAIL_BACKEND=LOCMEM)
class SendWaitingTests(TestCase):
    def setUp(self):
        mail.outbox = []
        with _down():
            send_system_email("registration_student", "amy@example.test", CONTEXT)
        self.kept = WaitingEmail.objects.get()

    def test_old_queued_email_counts_in_the_window_when_it_is_sent(self):
        from apps.admin.services.analytics import get_email_delivery_analytics

        sent_at = timezone.now()
        WaitingEmail.objects.filter(pk=self.kept.pk).update(
            created_at=sent_at - timedelta(hours=25),
        )
        with mock.patch("django.utils.timezone.now", return_value=sent_at):
            self.assertEqual(send_waiting("info"), {"sent": 1, "failed": 0})
            metric = EmailDeliveryMetric.objects.get(email_type="registration_student")
            self.assertEqual(metric.started_at, sent_at)
            self.assertEqual(metric.completed_at, sent_at)
            self.assertEqual(get_email_delivery_analytics()["totals"]["attempted"], 1)

        with mock.patch("django.utils.timezone.now", return_value=sent_at + timedelta(hours=24)):
            self.assertEqual(get_email_delivery_analytics()["totals"]["attempted"], 0)

    def test_old_queued_email_failure_is_timestamped_when_resolved(self):
        from apps.admin.services.analytics import get_email_delivery_analytics

        resolved_at = timezone.now()
        WaitingEmail.objects.filter(pk=self.kept.pk).update(
            created_at=resolved_at - timedelta(hours=25),
        )
        self.kept.refresh_from_db()
        with mock.patch("django.utils.timezone.now", return_value=resolved_at):
            waiting_email._missed(self.kept, {"amy@example.test": "address refused"})
            metric = EmailDeliveryMetric.objects.get(email_type="registration_student")
            self.assertEqual(metric.started_at, resolved_at)
            self.assertEqual((metric.attempted_count, metric.delivered_count, metric.failed_count), (1, 0, 1))
            self.assertEqual(get_email_delivery_analytics()["totals"]["failed"], 1)

    def test_once_the_server_can_be_reached_it_goes_as_it_was_built(self):
        self.assertEqual(send_waiting("info"), {"sent": 1, "failed": 0})
        [sent] = mail.outbox
        self.assertEqual(sent.to, ["amy@example.test"])
        self.assertIn("registration", sent.subject.lower())
        self.assertFalse(WaitingEmail.objects.exists())
        # Counted once it went, and the Log lists it as waiting no more.
        self.assertEqual(EmailDeliveryMetric.objects.get(email_type="registration_student").delivered_count, 1)
        entry = next(item for item in email_log() if item["key"] == "registration_student")
        self.assertEqual((entry["waiting"], entry["missed"]), ([], []))

    def test_delayed_send_metric_uses_the_actual_retry_time(self):
        started = self.kept.created_at + timedelta(hours=2)
        completed = started + timedelta(seconds=3)
        with mock.patch(
            "apps.services.waiting_email.timezone.now",
            # Retry start, retry completion, then the System Email Log time.
            side_effect=[started, completed, completed],
        ):
            self.assertEqual(send_waiting("info", now=started), {"sent": 1, "failed": 0})

        metric = EmailDeliveryMetric.objects.get(email_type="registration_student")
        self.assertEqual((metric.started_at, metric.completed_at), (started, completed))

    def test_partial_retry_is_one_partial_metric_not_success_and_failure_rows(self):
        self.kept.recipients = ["amy@example.test", "bob@example.test"]
        self.kept.save(update_fields=["recipients"])
        refused = {"bob@example.test": (550, b"No such user")}

        with mock.patch("apps.services.waiting_email.send_noting_refused", return_value=refused):
            self.assertEqual(send_waiting("info"), {"sent": 1, "failed": 0})

        [metric] = EmailDeliveryMetric.objects.filter(email_type="registration_student")
        self.assertEqual(metric.status, EmailDeliveryMetric.Status.PARTIAL)
        self.assertEqual(
            (metric.attempted_count, metric.delivered_count, metric.failed_count),
            (2, 1, 1),
        )
        self.assertEqual(
            list(metric.recipients.order_by("email").values_list("email", "status")),
            [
                ("amy@example.test", "delivered"),
                ("bob@example.test", "failed"),
            ],
        )

    def test_a_run_that_cant_reach_the_server_leaves_it_waiting(self):
        unreachable = mock.Mock()
        unreachable.open.side_effect = OSError("unreachable")
        with mock.patch("apps.services.system_email.get_connection", return_value=unreachable):
            self.assertEqual(send_waiting("info"), {"sent": 0, "failed": 0})
        self.kept.refresh_from_db()
        self.assertEqual(self.kept.tries, 1)
        self.assertEqual(mail.outbox, [])

    def test_one_switched_off_keeps_waiting(self):
        SystemEmailTemplate.objects.create(key="registration_student", is_enabled=False)
        send_waiting("info")
        self.assertEqual(mail.outbox, [])
        self.assertTrue(WaitingEmail.objects.exists())

    def test_one_held_by_another_run_isnt_sent_twice(self):
        WaitingEmail.objects.update(held_until=timezone.now() + timedelta(minutes=5))
        send_waiting("info")
        self.assertEqual(mail.outbox, [])

    def test_after_3_days_it_is_given_up_on_listed_as_missed_and_kept_for_resend(self):
        log = SystemEmailLog.objects.filter(key="registration_student").first()
        last_sent = log.last_sent_at if log else None
        send_waiting("info", now=self.kept.give_up_at + timedelta(minutes=1))
        self.assertEqual(mail.outbox, [])
        # Waiting no more: kept, as missed, for Resend on the Log.
        self.assertEqual(WaitingEmail.objects.get().state, WaitingEmail.State.MISSED)
        log = SystemEmailLog.objects.get(key="registration_student")
        self.assertEqual(log.missed[0]["missed"], [{"address": "amy@example.test", "reason": UNREACHABLE}])
        # It never went, so when the email last went out stays as it was.
        self.assertEqual(log.last_sent_at, last_sent)


@override_settings(EMAIL_BACKEND=LOCMEM, EMAIL_JOBS_TOKEN="secret-token")
class SendWaitingEmailsViewTests(TestCase):
    def test_the_10_minute_run_needs_the_token_and_sends_whats_waiting(self):
        with _down():
            send_system_email("registration_student", "amy@example.test", CONTEXT)
        mail.outbox = []
        self.assertEqual(APIClient().post(URL).status_code, 401)
        response = APIClient().post(URL, HTTP_X_EMAIL_JOBS_TOKEN="secret-token")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"status": "queued", "mailboxes": ["info"]})
        # Tests send the queue inline: it went in its turn.
        self.assertEqual([m.to for m in mail.outbox], [["amy@example.test"]])
        self.assertFalse(WaitingEmail.objects.exists())

    def test_with_nothing_waiting_it_queues_nothing(self):
        response = APIClient().post(URL, HTTP_X_EMAIL_JOBS_TOKEN="secret-token")
        self.assertEqual(response.json(), {"status": "queued", "mailboxes": []})


class ManagementLogTests(TestCase):
    def test_a_management_run_lists_those_waiting_apart_from_those_it_missed(self):
        from apps.management.models import EmailSendRun

        EmailSendRun.objects.create(
            key="finalist_notification", started_at=timezone.now(), missed=[
                {"who": "amy@x.com (BTF07, Amy Chen)", "reason": WAITING_REASON},
                {"who": "ben@x.com (BTF07, Ben Lee)", "reason": "address refused"},
            ],
        )
        entry = next(item for item in email_log() if item["key"] == "finalist_notification")
        self.assertEqual([p["who"] for send in entry["missed"] for p in send["people"]], ["ben@x.com (BTF07, Ben Lee)"])
        self.assertEqual(unseen_failures(), 1)
