"""
The waitlist promotion and finalist emails go through the shared system email path.
Run with: python manage.py test tests.apps.services.test_promotion_and_finalist_emails
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings

from apps.events.models import Events
from apps.events.promotion_email import notify_waitlist_promoted
from apps.grading.models import FinalistFlag
from apps.grading.services.finalist_notify import notify_finalist
from apps.groups.models import GroupMembership, Groups
from apps.services.models import SystemEmailSettings, SystemEmailTemplate
from apps.users.models import User

# 9 Oct 2026 00:00 UTC is Friday 9 Oct 2026, 11:00 AM AEDT in Sydney.
START = datetime(2026, 10, 9, 0, 0, tzinfo=dt_timezone.utc)


def _html(message):
    return next(body for body, mimetype in message.alternatives if mimetype == "text/html")


def _event(**kwargs):
    defaults = dict(
        event_name="BIOTech Symposium",
        description="",
        start_datetime=START,
        ends_datetime=START + timedelta(hours=2),
        event_format="in_person",
    )
    defaults.update(kwargs)
    return Events.objects.create(**defaults)


class WaitlistPromotionEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="promoted@example.com", password="x", first_name="Ada", timezone="Australia/Sydney",
        )

    def _send(self, event):
        notify_waitlist_promoted(event_id=event.id, user_id=self.user.id)

    def test_unedited_email_keeps_subject_and_plain_text_and_gains_branded_html(self):
        event = _event(
            event_format="hybrid", location="Room 201", location_link="https://zoom.us/j/1",
        )
        self._send(event)

        message = mail.outbox[0]
        self.assertEqual(message.to, ["promoted@example.com"])
        self.assertEqual(message.subject, "You're in: BIOTech Symposium")
        self.assertEqual(
            message.body,
            "Hi Ada,\n\n"
            "A spot just opened up and you've been moved from the waitlist to confirmed for BIOTech Symposium.\n\n"
            "Event:  BIOTech Symposium\n"
            "When:   Friday, 09 October 2026 at 11:00 AM AEDT\n"
            "Join:   https://zoom.us/j/1\n"
            "Where:  Room 201\n\n"
            "See you there!\n\n"
            "The BIOTech Futures Team",
        )
        html = _html(message)
        self.assertIn("Friday, 09 October 2026 at 11:00 AM AEDT", html)
        self.assertIn("https://zoom.us/j/1", html)
        self.assertIn("Room 201", html)
        self.assertIn("cid:btf-logo", html)

    def test_virtual_event_shows_join_link_only(self):
        self._send(_event(event_format="virtual", location_link="https://zoom.us/j/2"))
        body = mail.outbox[0].body
        self.assertIn("Join:   https://zoom.us/j/2", body)
        self.assertNotIn("Where:", body)

    def test_in_person_event_shows_location_only(self):
        self._send(_event(location="Great Hall", location_link="https://maps.example/hall"))
        body = mail.outbox[0].body
        self.assertIn("Where:  Great Hall", body)
        self.assertNotIn("Join:", body)

    def test_switched_off_sends_nothing(self):
        SystemEmailTemplate.objects.create(key="event_promotion", is_enabled=False)
        self._send(_event(location="Great Hall"))
        self.assertEqual(mail.outbox, [])

    def test_edited_email_uses_the_saved_wording(self):
        SystemEmailTemplate.objects.create(
            key="event_promotion",
            subject="Good news {{ first_name }}",
            body_html="<p>You're confirmed for {{ event_name }} at {{ event_location }}.</p>",
        )
        self._send(_event(location="Great Hall"))
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Good news Ada")
        self.assertIn("<p>You're confirmed for BIOTech Symposium at Great Hall.</p>", _html(message))

    def test_send_failure_is_logged_not_raised(self):
        event = _event(location="Great Hall")
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("smtp down")), \
                self.assertLogs("apps.events.promotion_email", level="ERROR"):
            self._send(event)  # must not raise: the promotion already happened

    def test_missing_user_or_event_sends_nothing(self):
        event = _event(location="Great Hall")
        notify_waitlist_promoted(event_id=event.id, user_id=999999)
        notify_waitlist_promoted(event_id=999999, user_id=self.user.id)
        self.assertEqual(mail.outbox, [])


@override_settings(GRADING_FINALIST_EMAIL_ENABLED=True)
class FinalistEmailTests(TestCase):
    def setUp(self):
        self.group = Groups.objects.create(group_name="CRISPR Research 01")
        for email in ("one@example.com", "two@example.com"):
            member = User.objects.create_user(email=email, password="x", first_name="M", last_name="B")
            GroupMembership.objects.create(group=self.group, user=member, membership_role="student")
        self.admin = User.objects.create_user(email="admin@example.com", password="x")
        self.flag = FinalistFlag.objects.create(group=self.group, flagged_by=self.admin)

    def test_sends_one_email_per_member_and_marks_notified(self):
        self.assertTrue(notify_finalist(self.flag, actor=self.admin))

        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["one@example.com", "two@example.com"])
        for message in mail.outbox:
            self.assertEqual(len(message.to), 1)  # members never see each other's addresses
            self.assertEqual(message.subject, "Congratulations — CRISPR Research 01 is a BIOTech Futures finalist")
            self.assertIn("Your group (CRISPR Research 01) has been selected as a finalist", message.body)
            self.assertIn("CRISPR Research 01", _html(message))
        self.flag.refresh_from_db()
        self.assertTrue(self.flag.notified)
        self.assertEqual(self.flag.notified_by, self.admin)

    @override_settings(GRADING_FINALIST_EMAIL_ENABLED=False)
    def test_environment_switch_still_takes_priority(self):
        self.assertFalse(notify_finalist(self.flag))
        self.assertEqual(mail.outbox, [])

    def test_switched_off_by_admin_sends_nothing_and_leaves_flag_unnotified(self):
        SystemEmailTemplate.objects.create(key="finalist_notification", is_enabled=False)
        self.assertFalse(notify_finalist(self.flag))
        self.assertEqual(mail.outbox, [])
        self.flag.refresh_from_db()
        self.assertFalse(self.flag.notified)

    def test_global_switch_off_sends_nothing(self):
        SystemEmailSettings.objects.create(emails_enabled=False)
        self.assertFalse(notify_finalist(self.flag))
        self.assertEqual(mail.outbox, [])

    def test_nothing_delivered_leaves_flag_unnotified_for_a_retry(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("smtp down")), \
                self.assertLogs("apps.grading.services.finalist_notify", level="ERROR") as logs:
            self.assertFalse(notify_finalist(self.flag))
        self.flag.refresh_from_db()
        self.assertFalse(self.flag.notified)
        self.assertFalse(any("@example.com" in line for line in logs.output))

    def test_partial_delivery_still_marks_notified(self):
        real_send = mail.EmailMultiAlternatives.send

        def fail_for_one(message, *args, **kwargs):
            if message.to == ["one@example.com"]:
                raise OSError("rejected")
            return real_send(message, *args, **kwargs)

        with mock.patch("django.core.mail.EmailMultiAlternatives.send", autospec=True, side_effect=fail_for_one), \
                self.assertLogs("apps.grading.services.finalist_notify", level="ERROR"):
            self.assertTrue(notify_finalist(self.flag))
        self.assertEqual([m.to for m in mail.outbox], [["two@example.com"]])
        self.flag.refresh_from_db()
        self.assertTrue(self.flag.notified)

    def test_edited_email_uses_the_saved_wording(self):
        SystemEmailTemplate.objects.create(
            key="finalist_notification",
            subject="{{ group_name }} made the final!",
            body_html="<p>Well done, {{ group_name }}.</p>",
        )
        notify_finalist(self.flag)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "CRISPR Research 01 made the final!")
        self.assertIn("<p>Well done, CRISPR Research 01.</p>", _html(message))
