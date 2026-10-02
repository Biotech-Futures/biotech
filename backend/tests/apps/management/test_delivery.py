"""Each copy of a bulk email: a dropped connection opened again for the rest,
a reason for each failure the page can show, and the back-fill of who
earlier runs reached."""
import smtplib
from importlib import import_module
from unittest import mock

from django.apps import apps as django_apps
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.grading.models import FinalistFlag
from apps.groups.models import GroupMembership, Groups
from apps.management.models import EmailDelivery, EmailSendRun
from apps.management.services import delivery
from apps.services.system_email import RenderedEmail
from apps.users.models import User

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
EMAIL = RenderedEmail(subject="Hello", text="Hi", html="<p>Hi</p>")


class FailureReasonTests(TestCase):
    def test_each_failure_is_worded_for_the_page(self):
        cases = [
            (smtplib.SMTPRecipientsRefused({"a@x.com": (550, b"No such user a@x.com")}), "address refused"),
            (smtplib.SMTPRecipientsRefused({"a@x.com": (450, b"Mailbox busy")}), "mail server busy"),
            (smtplib.SMTPDataError(451, b"Try again later"), "mail server busy"),
            (smtplib.SMTPDataError(554, b"Message rejected"), "mail server refused it"),
            (smtplib.SMTPDataError(550, b"Daily sending limit exceeded"), "sending limit reached"),
            (smtplib.SMTPAuthenticationError(535, b"Bad login"), "mail server login failed"),
            (smtplib.SMTPServerDisconnected("Connection unexpectedly closed"), "lost the mail server connection"),
            (TimeoutError("timed out"), "lost the mail server connection"),
            (ValueError("odd"), "couldn't be sent"),
        ]
        for exc, reason in cases:
            with self.subTest(exc=type(exc).__name__, reason=reason):
                self.assertEqual(delivery.failure_reason(exc), reason)
                # Never the server's own words, which can carry the address.
                self.assertNotIn("@", delivery.failure_reason(exc))


@override_settings(EMAIL_BACKEND=LOCMEM)
class SendEachTests(TestCase):
    def setUp(self):
        self.team = Groups.objects.create(group_name="BTF-DEL")
        self.real_send = mail.EmailMultiAlternatives.send

    def _patched(self, behaviour):
        return mock.patch("django.core.mail.EmailMultiAlternatives.send", autospec=True, side_effect=behaviour)

    def test_a_dropped_connection_is_opened_again_for_the_rest(self):
        tries = []

        def drop_once(message, *args, **kwargs):
            tries.append(message.to[0])
            if len(tries) == 1:
                raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")
            return self.real_send(message, *args, **kwargs)

        with self._patched(drop_once), self.assertLogs("apps.management.services.delivery", level="ERROR"), \
                mock.patch.object(delivery, "_reconnect", wraps=delivery._reconnect) as reconnect:
            failed = delivery.send_each(EMAIL, ["a@x.com", "b@x.com"], email="test", group=self.team, log_as="t")
        # Not retried here: the run tries it again at its end.
        self.assertEqual(failed, {"a@x.com": "lost the mail server connection"})
        self.assertEqual(tries, ["a@x.com", "b@x.com"])
        reconnect.assert_called_once()
        self.assertEqual([m.to[0] for m in mail.outbox], ["b@x.com"])

    def test_a_refused_address_keeps_the_connection_and_the_rest_still_go(self):
        tries = []

        def refuse_a(message, *args, **kwargs):
            tries.append(message.to[0])
            if message.to == ["a@x.com"]:
                raise smtplib.SMTPRecipientsRefused({"a@x.com": (550, b"No such user")})
            return self.real_send(message, *args, **kwargs)

        with self._patched(refuse_a), self.assertLogs("apps.management.services.delivery", level="ERROR"), \
                mock.patch.object(delivery, "_reconnect") as reconnect:
            failed = delivery.send_each(EMAIL, ["a@x.com", "b@x.com"], email="test", group=self.team, log_as="t")
        self.assertEqual(failed, {"a@x.com": "address refused"})
        self.assertEqual(tries, ["a@x.com", "b@x.com"])
        reconnect.assert_not_called()

    def test_each_copy_that_goes_is_recorded_and_not_sent_again(self):
        delivery.send_each(EMAIL, ["a@x.com"], email="test", group=self.team, log_as="t")
        self.assertTrue(EmailDelivery.objects.filter(email="test", group=self.team, address="a@x.com").exists())
        mail.outbox = []
        delivery.send_each(EMAIL, ["A@x.com", "b@x.com"], email="test", group=self.team, log_as="t")
        self.assertEqual([m.to for m in mail.outbox], [["b@x.com"]])
        self.assertEqual(delivery.still_due("test", self.team, ["a@x.com", "b@x.com", "c@x.com"]), ["c@x.com"])

    def test_without_a_team_nothing_is_recorded(self):
        delivery.send_each(EMAIL, ["sup@x.com"], email="test", log_as="t")
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(EmailDelivery.objects.exists())


class BackfillTests(TestCase):
    """The migration records, from the last run's missed list, who else on
    those teams it reached, so pressing Send again emails only the missed."""

    def _member(self, team, first, email, role="student"):
        user = User.objects.create_user(
            email=email, first_name=first, last_name="X", password="pw12345!", is_active=True,
        )
        GroupMembership.objects.create(group=team, user=user, membership_role=role)
        return user

    def test_the_others_on_a_team_the_last_run_missed_someone_on_are_recorded(self):
        partly = Groups.objects.create(group_name="BTF142")
        done = Groups.objects.create(group_name="BTF7")
        for team in (partly, done):
            FinalistFlag.objects.create(group=team, notified=team is done)
        self._member(partly, "Amy", "amy@x.com")
        self._member(partly, "Ben", "ben@x.com")
        self._member(partly, "Mo", "mo@x.com", role="mentor")
        self._member(done, "Cy", "cy@x.com")
        # A member who joined after the run wasn't sent it.
        late = self._member(partly, "Late", "late@x.com")
        GroupMembership.objects.filter(user=late).update(joined_at="2999-01-01T00:00:00Z")
        EmailSendRun.objects.create(
            key="finalist_notification", started_at=timezone.now(), missed=["(BTF142) Ben X", "(BTF7) Cy X"],
        )

        migration = import_module("apps.management.migrations.0003_email_delivery")
        migration.record_last_runs(django_apps, None)

        recorded = set(EmailDelivery.objects.values_list("email", "group__group_name", "address"))
        # Amy and the mentor got it; Ben didn't, the late joiner wasn't sent
        # it, and a team since notified is left alone.
        self.assertEqual(recorded, {
            ("finalist_notification", "BTF142", "amy@x.com"),
            ("finalist_notification", "BTF142", "mo@x.com"),
        })
