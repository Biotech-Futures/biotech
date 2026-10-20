"""Bounce notices in the sending mailboxes: read (only them, once), matched to
the email that bounced, and the person noted as missed. The Mail API is
mocked throughout; nothing here reaches Hostinger."""
from datetime import timedelta
from email.utils import format_datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.grading.models import FinalistFlag
from apps.groups.models import Groups
from apps.management.models import BounceCheckpoint, BounceNotice, EmailDelivery, EmailSendRun
from apps.management.services.bounce_check import (
    ALREADY_RUNNING, RUNNING, STARTED, SWITCHED_OFF, _run_check, check_bounces,
)
from apps.services import hostinger_mail
from apps.services.bounces import (
    MAILBOX_FULL, NO_MAILBOX, email_for_subject, looks_like_bounce, parse_bounce, reason_for,
)
from apps.services.email_registry import EMAIL_TYPES
from apps.services.hostinger_mail import MailApiError, MailMessage
from apps.services.email_log import email_log, mark_failures_seen, unseen_failures
from apps.services.models import EmailBounce, SystemEmailLog
from apps.services.system_email import senders

FINALIST_SUBJECT = "Congratulations – You’re a BIOTech Futures Finalist!"


def report(*recipients, subject=FINALIST_SUBJECT, sent_at=None):
    """A standard delivery report (RFC 3464): each recipient ``(address,
    action, status, diagnostic)``, quoting the bounced email's headers."""
    blocks = "".join(
        f"Final-Recipient: rfc822; {address}\nAction: {action}\nStatus: {status}\n"
        f"Diagnostic-Code: smtp; {diagnostic}\n\n"
        for address, action, status, diagnostic in recipients
    )
    sent = format_datetime(sent_at or timezone.now())
    return (
        "From: Mail Delivery System <MAILER-DAEMON@mx.example>\n"
        "Subject: Undelivered Mail Returned to Sender\n"
        "MIME-Version: 1.0\n"
        'Content-Type: multipart/report; report-type=delivery-status; boundary="B"\n\n'
        "--B\nContent-Type: text/plain\n\nYour message could not be delivered.\n\n"
        "--B\nContent-Type: message/delivery-status\n\nReporting-MTA: dns; mx.example\n\n"
        f"{blocks}"
        "--B\nContent-Type: text/rfc822-headers\n\n"
        f"From: BIOTech Futures <info@example.org>\nSubject: {subject}\nDate: {sent}\n\n"
        "--B--\n"
    ).encode()


EXIM = (
    "From: Mail Delivery System <Mailer-Daemon@server.example>\n"
    "Subject: Mail delivery failed: returning message to sender\n"
    "X-Failed-Recipients: Pat@School.example\n"
    "Content-Type: text/plain\n\n"
    "A message that you sent could not be delivered to one or more of its recipients.\n"
    "  pat@school.example\n    mailbox is full: retry timeout exceeded\n"
).encode()


class ReadingNoticesTests(SimpleTestCase):
    def test_a_standard_report_gives_who_why_and_the_email(self):
        sent = timezone.now().replace(microsecond=0)
        [bounce] = parse_bounce(report(("Amy@Example.com", "failed", "5.1.1", "550 user unknown"), sent_at=sent))
        self.assertEqual(bounce.address, "amy@example.com")
        self.assertEqual(bounce.reason, NO_MAILBOX)
        self.assertTrue(bounce.permanent)
        self.assertEqual(bounce.subject, FINALIST_SUBJECT)
        self.assertEqual(bounce.sent_at, sent)

    def test_only_failures_count(self):
        bounces = parse_bounce(report(
            ("a@x.example", "delayed", "4.4.1", "still trying"),
            ("b@x.example", "failed", "4.2.2", "452 mailbox full"),
        ))
        self.assertEqual([(b.address, b.reason, b.permanent) for b in bounces], [("b@x.example", MAILBOX_FULL, False)])

    def test_a_plain_notice_names_who_failed_in_its_header(self):
        [bounce] = parse_bounce(EXIM)
        self.assertEqual((bounce.address, bounce.reason, bounce.subject), ("pat@school.example", MAILBOX_FULL, ""))

    def test_a_message_that_isnt_a_notice_gives_nobody(self):
        self.assertEqual(parse_bounce(b"From: amy@x.example\nSubject: Thanks!\n\nSee you there."), [])

    def test_notices_are_known_by_sender_or_subject(self):
        self.assertTrue(looks_like_bounce("Mail Delivery System <MAILER-DAEMON@x>", "Anything"))
        self.assertTrue(looks_like_bounce("postmaster@school.example", ""))
        self.assertTrue(looks_like_bounce("someone@x", "Delivery Status Notification (Failure)"))
        self.assertFalse(looks_like_bounce("amy@x.example", "Re: Congratulations"))

    def test_reasons_in_plain_words(self):
        self.assertEqual(reason_for("5.1.1", ""), NO_MAILBOX)
        self.assertEqual(reason_for("", "550 No such user here"), NO_MAILBOX)
        self.assertEqual(reason_for("5.1.2", ""), "domain doesn't exist")
        self.assertEqual(reason_for("5.7.1", "message rejected as spam"), "blocked by their mail server")
        self.assertEqual(reason_for("4.3.0", ""), "temporarily undeliverable")
        self.assertEqual(reason_for("5.0.0", ""), "couldn't be delivered")


class SubjectTests(TestCase):
    def test_a_quoted_subject_finds_its_system_email(self):
        login = next(t for t in EMAIL_TYPES if t.default_subject.endswith("Log in securely"))
        self.assertEqual(email_for_subject("BIOTech  Futures: Log in securely"), login.key)
        # A subject that's all merge tags would match anything: never chosen.
        self.assertIsNone(email_for_subject("Reminder: BIOTech Symposium"))
        self.assertIsNone(email_for_subject(""))


@override_settings(HOSTINGER_MAIL_API_URL="https://mail.example", HOSTINGER_MAIL_API_KEY="test-key")
class MailApiTests(SimpleTestCase):
    def response(self, status=200, body=None, content=b""):
        response = MagicMock(status_code=status, content=content)
        response.json.return_value = body
        return response

    @patch("apps.services.hostinger_mail.requests.get")
    def test_it_lists_the_mailboxes_signed_in_with_the_key(self, get):
        get.return_value = self.response(body={"data": {"mailboxes": [{"resourceId": "mb1", "address": "Info@X.org"}]}})
        self.assertEqual(hostinger_mail.mailboxes(), [{"id": "mb1", "address": "info@x.org"}])
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer test-key"})

    @patch("apps.services.hostinger_mail.requests.get")
    def test_it_pages_through_the_inbox_newest_first(self, get):
        page = [{"uid": 200 - i, "from": {"name": "Amy", "address": "amy@x"}, "subject": "Hi"} for i in range(100)]
        get.side_effect = [self.response(body={"data": page}), self.response(body={"data": [{"uid": 5}]})]
        messages = list(hostinger_mail.newest_messages("mb1"))
        self.assertEqual(len(messages), 101)
        self.assertEqual(messages[0].sender, "Amy <amy@x>")
        self.assertEqual(get.call_args_list[1].kwargs["params"], {"page": 2, "perPage": 100, "sort": "-uid"})

    @patch("apps.services.hostinger_mail.requests.get")
    def test_a_failure_says_its_status_only(self, get):
        get.return_value = self.response(status=401)
        with self.assertRaisesMessage(MailApiError, "The Mail API answered 401."):
            hostinger_mail.mailboxes()


@override_settings(HOSTINGER_MAIL_API_KEY="test-key", BOUNCE_LOOKBACK_DAYS=14)
class CheckBouncesTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.ours = senders()[0].address.lower()
        self.group = Groups.create_auto_named()
        FinalistFlag.objects.create(group=self.group, notified=True)
        EmailDelivery.objects.create(email="finalist_notification", group=self.group, address="amy@example.com")
        patcher = patch("apps.management.services.bounce_check.hostinger_mail")
        self.api = patcher.start()
        self.addCleanup(patcher.stop)
        self.api.mailboxes.return_value = [{"id": "mb1", "address": self.ours}]
        self.inbox(
            MailMessage(12, "Mail Delivery System <MAILER-DAEMON@mx.example>", "Undelivered Mail", self.now, "<b1@mx>"),
            MailMessage(11, "Teacher <teacher@school.example>", "Re: Congratulations", self.now, "<r1@school>"),
        )
        self.api.source.return_value = report(("amy@example.com", "failed", "5.1.1", "550 user unknown"))

    def inbox(self, *messages):
        self.api.newest_messages.side_effect = lambda mailbox_id: iter(messages)

    def log_entry(self, key):
        return next(item for item in email_log() if item["key"] == key)

    def test_a_finalist_bounce_puts_the_person_back_as_missed(self):
        result = check_bounces(self.now)
        self.assertEqual((result.mailboxes, result.notices, result.bounces, result.matched), (1, 1, 1, 1))
        # Only the notice is opened, never the reply.
        self.api.source.assert_called_once_with("mb1", 12)
        self.assertFalse(EmailDelivery.objects.exists())
        self.assertFalse(FinalistFlag.objects.get(group=self.group).notified)
        self.assertEqual(
            EmailSendRun.objects.get(key="finalist_notification").missed,
            [{"who": f"amy@example.com ({self.group.group_name})", "reason": "bounced: no such mailbox"}],
        )
        self.assertEqual(BounceCheckpoint.objects.get(mailbox=self.ours).last_uid, 12)

    def test_the_log_lists_bounces_apart_by_when_they_were_found(self):
        # The finalist send went out (and missed someone) before the check.
        EmailSendRun.objects.create(
            key="finalist_notification", started_at=self.now - timedelta(hours=2),
            missed=[{"who": "lee@x.example (BTF09)", "reason": "address refused"}],
        )
        check_bounces(self.now)
        entry = self.log_entry("finalist_notification")
        # Failed emails: the send's own misses, without the bounce.
        self.assertEqual([p["who"] for send in entry["missed"] for p in send["people"]], ["lee@x.example (BTF09)"])
        # Bounced emails: grouped by when the check found them.
        self.assertEqual(entry["bounced"], [{
            "at": self.now.isoformat(),
            "people": [{"who": f"amy@example.com ({self.group.group_name})", "reason": "no such mailbox"}],
        }])

    def test_a_bounce_counts_as_unseen_by_when_it_was_found(self):
        EmailSendRun.objects.create(key="finalist_notification", started_at=self.now - timedelta(hours=2))
        # An admin looked after the send went, before the bounce was found.
        self.assertEqual(mark_failures_seen(), 0)
        check_bounces(timezone.now() + timedelta(minutes=1))
        self.assertEqual(unseen_failures(), 1)

    def test_each_notice_is_read_once(self):
        check_bounces(self.now)
        # Even read from the start again, the notice isn't counted twice.
        BounceCheckpoint.objects.update(last_uid=0)
        result = check_bounces(self.now)
        self.assertEqual(result.notices, 0)
        self.assertEqual(self.api.source.call_count, 1)
        self.assertEqual(BounceNotice.objects.get().matched, 1)

    def test_a_system_email_bounce_goes_on_the_log(self):
        login = next(t for t in EMAIL_TYPES if t.default_subject.endswith("Log in securely"))
        self.api.source.return_value = report(
            ("pat@school.example", "failed", "5.2.2", "552 mailbox full"), subject="BIOTech Futures: Log in securely",
        )
        result = check_bounces(self.now)
        self.assertEqual(result.matched, 1)
        self.assertEqual(self.log_entry(login.key)["bounced"], [{
            "at": self.now.isoformat(), "people": [{"who": "pat@school.example", "reason": "mailbox full"}],
        }])
        # Not on its Failed emails, and the finalist email wasn't touched.
        self.assertFalse(SystemEmailLog.objects.exists())
        self.assertTrue(EmailDelivery.objects.exists())

    def test_a_bounce_marks_the_recipient_of_that_send_as_not_delivered(self):
        from apps.services.email_metrics import record_email_delivery
        from apps.services.models import EmailDeliveryRecipient

        record_email_delivery(
            "finalist_notification", source_mailbox=self.ours, attempted=2, delivered=2, failed=0,
            recipients=["amy@example.com", "bo@example.com"], started_at=self.now - timedelta(hours=1),
        )
        check_bounces(self.now)

        rows = {row.email: (row.status, row.reason) for row in EmailDeliveryRecipient.objects.all()}
        self.assertEqual(rows, {
            "amy@example.com": ("failed", "bounced: no such mailbox"),
            "bo@example.com": ("delivered", ""),
        })

    def test_a_bounce_matching_no_email_is_skipped(self):
        self.api.source.return_value = report(("someone@else.example", "failed", "5.1.1", "x"), subject="Hello there")
        result = check_bounces(self.now)
        self.assertEqual((result.bounces, result.matched), (1, 0))
        self.assertFalse(EmailSendRun.objects.exists())
        self.assertFalse(EmailBounce.objects.exists())
        self.assertTrue(FinalistFlag.objects.get(group=self.group).notified)

    def test_other_mailboxes_and_old_messages_are_left(self):
        self.api.mailboxes.return_value = [{"id": "mb9", "address": "someone@else.example"}]
        self.assertEqual(check_bounces(self.now).mailboxes, 0)
        self.api.newest_messages.assert_not_called()

        self.api.mailboxes.return_value = [{"id": "mb1", "address": self.ours}]
        old = self.now - timedelta(days=15)
        self.inbox(MailMessage(3, "MAILER-DAEMON@mx.example", "Undelivered Mail", old, "<old@mx>"))
        self.assertEqual(check_bounces(self.now).notices, 0)
        self.api.source.assert_not_called()

    @override_settings(HOSTINGER_MAIL_API_KEY="")
    def test_nothing_without_a_key(self):
        self.assertEqual(check_bounces(self.now).mailboxes, 0)
        self.api.mailboxes.assert_not_called()
        out = StringIO()
        call_command("check_bounced_emails", stdout=out)
        self.assertIn("HOSTINGER_MAIL_API_KEY isn't set", out.getvalue())


TRIGGER = "/api/v1/management/bounce-check/"


@override_settings(EMAIL_JOBS_TOKEN="jobs-token", RSVP_REMINDER_TOKEN="", HOSTINGER_MAIL_API_KEY="test-key")
class TriggerTests(TestCase):
    """GitHub's schedule starts a check through the trigger, with the email
    jobs' shared token, as the other scheduled jobs do."""

    def setUp(self):
        cache.delete(RUNNING)
        self.addCleanup(cache.delete, RUNNING)
        patcher = patch("apps.management.services.bounce_check.threading.Thread")
        self.thread = patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, token="jobs-token"):
        return APIClient().post(TRIGGER, HTTP_X_EMAIL_JOBS_TOKEN=token)

    def test_it_starts_one_check_at_a_time(self):
        response = self.post()
        self.assertEqual((response.status_code, response.json()), (202, {"status": STARTED}))
        self.thread.return_value.start.assert_called_once()
        self.assertEqual(self.post().json(), {"status": ALREADY_RUNNING})
        self.thread.return_value.start.assert_called_once()

    def test_it_needs_the_jobs_token(self):
        self.assertEqual(self.post("wrong").status_code, 401)
        self.thread.assert_not_called()

    @override_settings(EMAIL_JOBS_TOKEN="", RSVP_REMINDER_TOKEN="")
    def test_it_refuses_while_the_jobs_arent_set_up(self):
        self.assertEqual(self.post().status_code, 503)

    @override_settings(HOSTINGER_MAIL_API_KEY="")
    def test_it_does_nothing_without_the_mail_key(self):
        self.assertEqual(self.post().json(), {"status": SWITCHED_OFF})
        self.thread.assert_not_called()

    @patch("apps.management.services.bounce_check.check_bounces", side_effect=MailApiError("The Mail API answered 401."))
    def test_a_failed_check_lets_the_next_one_run(self, check):
        cache.add(RUNNING, True)
        with self.assertLogs("apps.management.services.bounce_check", level="ERROR"):
            _run_check()
        self.assertIsNone(cache.get(RUNNING))



@override_settings(HOSTINGER_MAIL_API_KEY="test-key")
class MailApiStateTests(TestCase):
    """Failed Sending Emails says, at its top, when bounced emails can't be
    checked: no key, a key Hostinger refuses, or a check that couldn't get
    through. A check that can clears it."""

    URL = "/api/v1/admin/email-log/mail-api/"

    def _check(self, **mailboxes):
        from apps.management.services.bounce_check import check_bounces

        with patch.object(hostinger_mail, "mailboxes", **mailboxes):
            check_bounces()

    def _state(self):
        from apps.services.email_log import mail_api_state

        return mail_api_state()

    def test_a_refused_key_is_said_until_a_check_gets_through(self):
        with self.assertRaises(MailApiError):
            self._check(side_effect=MailApiError("The Mail API answered 403.", status=403))
        state = self._state()
        self.assertEqual((state["problem"], state["status"]), ("rejected", 403))
        self.assertIsNotNone(state["at"])

        self._check(return_value=[])
        self.assertEqual(self._state(), {"problem": "", "at": None, "status": None})

    def test_a_check_that_couldnt_get_through_is_said_with_no_status(self):
        with self.assertRaises(MailApiError):
            self._check(side_effect=MailApiError("Couldn't reach the Mail API (ConnectTimeout)."))
        self.assertEqual((self._state()["problem"], self._state()["status"]), ("failed", None))

    @override_settings(HOSTINGER_MAIL_API_KEY="")
    def test_no_key_is_said_too(self):
        self.assertEqual(self._state()["problem"], "unset")

    def test_admins_read_it_and_nobody_else_does(self):
        from apps.users.models import User
        from apps.users.models.admin_scope import AdminScope

        admin = User.objects.create_user(email="admin@example.com", password="x")
        AdminScope.objects.create(user=admin)
        client = APIClient()
        client.force_authenticate(admin)
        self.assertEqual(client.get(self.URL).json()["data"]["problem"], "")
        member = APIClient()
        member.force_authenticate(User.objects.create_user(email="member@example.com", password="x"))
        self.assertEqual(member.get(self.URL).status_code, 403)
