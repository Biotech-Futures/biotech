"""Resend on System Emails' Log: each email's own button, sending it again to
the people the Log lists as having missed it (apps.services.resend). Other
emails resend the copy kept when they failed; announcements are built again;
Management's bulk emails use their own Resend."""
import smtplib
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.announcements.models import Announcement, AnnouncementDelivery
from apps.admin.services.announcement import send_announcement_email
from apps.management.models import EmailSendRun
from apps.services import resend
from apps.services.email_log import email_log
from apps.services.models import SystemEmailLog, SystemEmailTemplate, WaitingEmail
from apps.services.system_email import FAILED, send_system_email
from apps.services.waiting_email import send_or_wait
from apps.users.models import User
from apps.users.models.admin_scope import AdminScope

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
REJECTED = smtplib.SMTPDataError(554, b"Message rejected")
DROPPED = smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
CONTEXT = {"First_Name": "Amy", "YEAR": "2026"}
MISSED = WaitingEmail.State.MISSED


def _entry(key):
    return next(email for email in email_log() if email["key"] == key)


def _url(key):
    return f"/api/v1/admin/email-log/{key}/resend/"


def _rejected():
    return mock.patch.object(EmailMultiAlternatives, "send", side_effect=REJECTED)


@override_settings(EMAIL_BACKEND=LOCMEM)
class KeptForResendTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.admin = User.objects.create_user(email="admin@example.com", password="x", first_name="Ada", last_name="Admin")
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _fail(self):
        with _rejected():
            self.assertEqual(send_system_email("registration_student", "amy@example.test", CONTEXT), FAILED)

    def test_an_email_that_fails_is_kept_for_resend_and_the_log_offers_it(self):
        self._fail()
        kept = WaitingEmail.objects.get()
        self.assertEqual((kept.key, kept.state, kept.recipients), ("registration_student", MISSED, ["amy@example.test"]))
        self.assertGreater(kept.give_up_at, timezone.now() + timedelta(days=29))
        entry = _entry("registration_student")
        self.assertTrue(entry["resendable"])
        self.assertEqual([p["who"] for send in entry["missed"] for p in send["people"]], ["amy@example.test"])
        # Waiting only lists those the mail server couldn't be reached for.
        self.assertEqual(entry["waiting"], [])

    def test_login_codes_and_reset_links_arent_kept_and_have_no_resend(self):
        for key in ("login_code", "password_reset"):
            with self.subTest(key=key), _rejected():
                send_system_email(key, "amy@example.test", {})
        self.assertFalse(WaitingEmail.objects.exists())
        self.assertFalse(_entry("login_code")["resendable"])
        self.assertEqual(self.client.post(_url("login_code")).status_code, 400)

    def test_resend_sends_the_kept_copy_and_takes_them_off_the_list(self):
        self._fail()
        response = self.client.post(_url("registration_student"))
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["msg"], resend.QUEUED)
        # Tests send the queue inline: it went in its turn.
        self.assertEqual([m.to for m in mail.outbox], [["amy@example.test"]])
        self.assertFalse(WaitingEmail.objects.exists())
        entry = _entry("registration_student")
        self.assertEqual((entry["missed"], entry["resendable"], entry["lastSentBy"]), ([], False, "Ada Admin"))

    def test_one_turned_away_again_is_listed_again_and_kept(self):
        self._fail()
        with mock.patch("apps.services.waiting_email.send_noting_refused", side_effect=REJECTED):
            self.client.post(_url("registration_student"))
        self.assertEqual(WaitingEmail.objects.get().state, MISSED)
        entry = _entry("registration_student")
        # The earlier entry gives way to this send's.
        self.assertEqual(
            [[p["reason"] for p in send["people"]] for send in entry["missed"]], [["mail server refused it"]],
        )
        self.assertTrue(entry["resendable"])

    def test_resent_while_the_mail_server_cant_be_reached_it_waits_for_it(self):
        self._fail()
        with mock.patch("apps.services.waiting_email.send_noting_refused", side_effect=DROPPED):
            self.client.post(_url("registration_student"))
        self.assertEqual(WaitingEmail.objects.get().state, WaitingEmail.State.WAITING)
        entry = _entry("registration_student")
        self.assertEqual(entry["missed"], [])
        self.assertEqual([p["who"] for p in entry["waiting"]], ["amy@example.test"])

    def test_nobody_to_resend_to_or_switched_off_is_refused_with_why(self):
        response = self.client.post(_url("registration_student"))
        self.assertEqual((response.status_code, response.json()["msg"]), (400, resend.NOBODY))
        self._fail()
        SystemEmailTemplate.objects.create(key="registration_student", is_enabled=False)
        response = self.client.post(_url("registration_student"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("switched off", response.json()["msg"])
        self.assertEqual(mail.outbox, [])

    def test_only_admins_resend(self):
        member = APIClient()
        member.force_authenticate(User.objects.create_user(email="member@example.com", password="x"))
        self.assertEqual(member.post(_url("registration_student")).status_code, 403)

    def test_an_expired_copy_isnt_offered_and_goes(self):
        self._fail()
        WaitingEmail.objects.update(give_up_at=timezone.now() - timedelta(minutes=1))
        self.assertFalse(_entry("registration_student")["resendable"])
        from apps.services.waiting_email import give_up

        give_up()
        self.assertFalse(WaitingEmail.objects.exists())

    def test_a_run_that_tries_it_again_at_its_end_keeps_only_what_that_wont_retry(self):
        def message():
            return EmailMultiAlternatives("Hi", "Hi", "BIOTech Futures <info@biotechfutures.org>", ["amy@example.test"])

        # Busy: the run tries it again at its end, so it isn't kept yet.
        with mock.patch.object(EmailMultiAlternatives, "send", side_effect=REJECTED):
            with self.assertRaises(smtplib.SMTPDataError):
                send_or_wait(message(), key="rsvp_reminder", later=True)
        self.assertFalse(WaitingEmail.objects.exists())
        # Its last try, or an address refused (never tried again): kept.
        refused = smtplib.SMTPRecipientsRefused({"amy@example.test": (550, b"No such user")})
        for exc, later in ((REJECTED, False), (refused, True)):
            with mock.patch.object(EmailMultiAlternatives, "send", side_effect=exc), self.assertRaises(type(exc)):
                send_or_wait(message(), key="rsvp_reminder", later=later)
        self.assertEqual(WaitingEmail.objects.filter(state=MISSED).count(), 2)


@override_settings(EMAIL_BACKEND=LOCMEM)
class AnnouncementResendTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.admin = User.objects.create_user(email="admin@example.com", password="x", first_name="Ada", last_name="Admin")
        AdminScope.objects.create(user=self.admin)
        for n in range(3):
            User.objects.create_user(email=f"r{n}@example.com", password="x", first_name=f"R{n}")
        self.announcement = Announcement.objects.create(
            author_user=self.admin, title="Hello", body="<p>Hi {{ first_name }}.</p>", visibility_scope="global",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _send_rejecting_all_but_the_first(self):
        real_send = mail.EmailMultiAlternatives.send
        tries = []

        def first_then_rejected(message, *args, **kwargs):
            tries.append(message.to[0])
            if len(tries) == 1:
                return real_send(message, *args, **kwargs)
            raise REJECTED

        with mock.patch.object(EmailMultiAlternatives, "send", new=first_then_rejected), \
                mock.patch("apps.services.retry.time.sleep"):
            return send_announcement_email(self.announcement.id, initiated_by=self.admin)

    def _resend_and_check(self, result):
        delivered_first = {m.to[0] for m in mail.outbox}
        mail.outbox = []
        self.assertTrue(_entry("announcement")["resendable"])
        self.assertEqual(self.client.post(_url("announcement")).status_code, 202)
        # Only those it missed get it, built again: greeted by name.
        resent = {m.to[0] for m in mail.outbox}
        self.assertEqual(len(resent), result["attempted"] - 1)
        self.assertFalse(resent & delivered_first)
        self.assertTrue(all("Hi R" in m.alternatives[0][0] or "Hi Ada" in m.alternatives[0][0] for m in mail.outbox))
        delivery = AnnouncementDelivery.objects.get(pk=result["deliveryId"])
        self.assertEqual(
            (delivery.status, delivery.success_count, delivery.failure_count, delivery.failed_recipients),
            (AnnouncementDelivery.Status.SUCCESS, result["attempted"], 0, []),
        )
        entry = _entry("announcement")
        self.assertEqual((entry["missed"], entry["resendable"]), ([], False))
        # Copies aren't kept for announcements: they're built again.
        self.assertFalse(WaitingEmail.objects.exists())

    def test_resend_builds_the_announcement_again_for_only_those_it_missed(self):
        result = self._send_rejecting_all_but_the_first()
        self.assertEqual(result["status"], AnnouncementDelivery.Status.PARTIAL)
        self._resend_and_check(result)

    def test_a_send_noted_before_sends_named_their_announcement_is_matched_by_time(self):
        result = self._send_rejecting_all_but_the_first()
        log = SystemEmailLog.objects.get(key="announcement")
        log.missed = [{key: value for key, value in entry.items() if key != "ref"} for entry in log.missed]
        log.save()
        self._resend_and_check(result)


class ManagementResendTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="admin@example.com", password="x")
        AdminScope.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_a_management_email_uses_its_own_resend_and_its_reasons(self):
        EmailSendRun.objects.create(
            key="finalist_notification", started_at=timezone.now(),
            missed=[{"who": "amy@x.com (BTF07, Amy Chen)", "reason": "address refused"}],
        )
        self.assertTrue(_entry("finalist_notification")["resendable"])
        with mock.patch.object(resend, "_management_blocked", return_value=""), \
                mock.patch.object(resend, "_management_start") as start:
            self.assertEqual(self.client.post(_url("finalist_notification")).status_code, 202)
        start.assert_called_once_with("finalist_notification", self.admin)

        with mock.patch.object(resend, "_management_blocked", return_value="Submissions are open."), \
                mock.patch.object(resend, "_management_start") as start:
            response = self.client.post(_url("finalist_notification"))
        self.assertEqual((response.status_code, response.json()["msg"]), (400, "Submissions are open."))
        start.assert_not_called()

    def test_its_real_checks_refuse_while_details_are_missing(self):
        response = self.client.post(_url("finalist_notification"))
        self.assertEqual(response.status_code, 400)
