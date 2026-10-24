"""Tests for the daily reminders to finalist teams before their slides are due."""
from datetime import time, timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.grading.models import FinalistFlag
from apps.groups.models import GroupMembership, Groups
from apps.management.models import FinalistEmailSettings, PresentationSettings, PresentationSlot
from apps.management.services.finalist_notify import SYMPOSIUM_TZ
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.services.models import SystemEmailTemplate
from apps.submissions.finalist import submit_team_times
from apps.submissions.finalist_reminders import send_due_reminders
from apps.submissions.models import FinalistEntry, FinalistReminder
from apps.submissions.services import current_cohort
from apps.users.models import User


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class FinalistReminderTests(TestCase):
    def setUp(self):
        roles = {name: Roles.objects.create(role_name=name) for name in ("student", "mentor", "supervisor")}
        self.group = Groups.objects.create(group_name="BTF-FIN", year=current_cohort())
        self.members = {}
        for role in ("student", "mentor", "supervisor"):
            user = User.objects.create_user(email=f"{role}@test.local", password="x", first_name=role.title())
            RoleAssignmentHistory.objects.create(user=user, role=roles[role], valid_from=timezone.now(), valid_to=None)
            GroupMembership.objects.create(group=self.group, user=user, membership_role=role)
            self.members[role] = user
        FinalistFlag.objects.create(group=self.group, notified=True)
        self.morning = PresentationSlot.objects.create(starts_at=time(10), ends_at=time(11))
        PresentationSlot.objects.create(starts_at=time(13), ends_at=time(14))
        PresentationSettings.objects.create(times_shown=True)
        # Slides due in three days' time, Sydney time.
        self.today = timezone.localtime(timezone.now(), SYMPOSIUM_TZ).date()
        self._due_in(3)

    def _due_in(self, days):
        details = FinalistEmailSettings.load()
        details.slides_due = None if days is None else self.today + timedelta(days=days)
        details.save()

    def _run(self, now=None):
        return send_due_reminders(now=now)

    def test_a_finalist_yet_to_submit_is_reminded_in_the_final_week(self):
        result = self._run()

        self.assertEqual(result["sent"], 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "BIOTech Futures: Presentation reminder for BTF-FIN")
        self.assertEqual(message.to, ["student@test.local"])
        self.assertEqual(sorted(message.cc), ["mentor@test.local", "supervisor@test.local"])
        self.assertIn("Presentation Slides\n  Status: Not uploaded", message.body)
        self.assertIn("Availability\n  Status: Not submitted", message.body)
        self.assertIn("Both are required: upload your slides and submit your availability, then press Submit.", message.body)
        self.assertIn("Slides are due on", message.body)

    def test_it_shows_the_slides_uploaded_and_the_times_selected(self):
        FinalistEntry.objects.create(group=self.group, presentation={"name": "deck.pdf", "storage_key": "k"})
        submit_team_times(self.members["student"], self.group, [self.morning.id])

        self._run()

        body = mail.outbox[0].body
        self.assertIn("Status: Uploaded\n  deck.pdf", body)
        self.assertIn("Status: Submitted\n  10:00 - 11:00", body)
        self.assertIn("Both are in. Press Submit on your finalist page to complete your submission.", body)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("Submission components", html)
        self.assertIn("background:#f4f7f5", html)

    def test_before_the_times_are_released_only_the_slides_are_asked_for(self):
        PresentationSettings.objects.update(times_shown=False)

        self._run()

        body = mail.outbox[0].body
        self.assertNotIn("Availability", body)
        self.assertIn("Your slides are required: upload them, then press Submit.", body)

    def test_the_next_step_names_only_what_is_still_missing(self):
        from apps.submissions.finalist_reminders import components_note

        def note(slides, times=None):
            rows = [{"submitted": slides}] + ([] if times is None else [{"submitted": times}])
            return components_note(rows)

        self.assertEqual(note(True, False), "Both are required: submit your availability, then press Submit.")
        self.assertEqual(note(False, True), "Both are required: upload your slides, then press Submit.")
        self.assertEqual(note(True), "Your slides are in. Press Submit on your finalist page to complete your submission.")

    def test_the_finalist_emails_write_out_their_contractions(self):
        self._run()
        message = mail.outbox[0]
        for text in (message.body, message.alternatives[0][0]):
            for short in ("We're", "We&rsquo;re", "they're", "they\u2019re", "We've", "We&rsquo;ve"):
                self.assertNotIn(short, text)

    def test_nobody_is_reminded_outside_the_final_week_or_without_a_due_date(self):
        for days in (10, -1, None):
            with self.subTest(days=days):
                self._due_in(days)
                self.assertEqual(self._run()["sent"], 0)
        self.assertEqual(mail.outbox, [])

    def test_a_team_is_reminded_once_a_day(self):
        self._run()
        self._run()
        self.assertEqual(len(mail.outbox), 1)

        self._run(now=timezone.now() + timedelta(days=1))
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(FinalistReminder.objects.get(group=self.group).last_sent_on, timezone.localdate() + timedelta(days=1))

    def test_a_team_that_has_submitted_is_left_alone_even_after_reopening(self):
        entry = FinalistEntry.objects.create(group=self.group, submitted_at=timezone.now())
        self.assertEqual(self._run()["sent"], 0)

        entry.reopened_at = timezone.now()
        entry.save()
        self.assertEqual(self._run()["sent"], 0)

    def test_only_this_years_notified_finalists_are_reminded(self):
        FinalistFlag.objects.filter(group=self.group).update(notified=False)
        self.assertEqual(self._run()["sent"], 0)

        FinalistFlag.objects.filter(group=self.group).update(notified=True)
        Groups.objects.filter(pk=self.group.pk).update(year=current_cohort() - 1)
        self.assertEqual(self._run()["sent"], 0)

    def test_switched_off_sends_and_records_nothing(self):
        SystemEmailTemplate.objects.create(key="finalist_submission_reminder", is_enabled=False)

        self.assertTrue(self._run()["disabled"])
        self.assertEqual(mail.outbox, [])
        self.assertFalse(FinalistReminder.objects.exists())

    def test_an_edited_reminder_shows_the_styled_section(self):
        SystemEmailTemplate.objects.create(
            key="finalist_submission_reminder",
            subject="Nearly there, {{ group_name }}",
            body_html="<p>Hi {{ group_name }}.</p>{{ submission_components }}",
        )

        self._run()

        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("<p>Hi BTF-FIN.</p>", html)
        self.assertIn("Not uploaded", html)
        self.assertNotIn("<ul>", html)


@override_settings(USE_AZURE_BLOB_STORAGE=False, EMAIL_JOBS_TOKEN="s3cret")
class DailyTriggerTests(TestCase):
    def test_the_daily_run_queues_the_finalist_reminders_too(self):
        from apps.management.models import EmailSendRun

        response = self.client.post(reverse("submission-send-reminders"), HTTP_X_EMAIL_JOBS_TOKEN="s3cret")

        self.assertEqual(response.status_code, 202)
        for key in ("submission_reminder", "finalist_submission_reminder"):
            self.assertIsNotNone(EmailSendRun.objects.get(key=key).finished_at, key)

    def test_a_wrong_token_queues_nothing(self):
        from apps.management.models import QueuedEmailSend

        response = self.client.post(reverse("submission-send-reminders"), HTTP_X_EMAIL_JOBS_TOKEN="wrong")

        self.assertEqual(response.status_code, 401)
        self.assertFalse(QueuedEmailSend.objects.exists())
