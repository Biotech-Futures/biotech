"""Tests for who receives a submission reminder, and when."""
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import (
    Deadline,
    GroupExtension,
    Submission,
    SubmissionQuestion,
    SubmissionReminder,
)
from apps.submissions.reminders import send_due_reminders, teams_due
from apps.users.models import User

from .seed_data import install_question_set


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class ReminderTests(TestCase):
    def setUp(self):
        self.role = Roles.objects.create(role_name="student")
        install_question_set()
        # Eight days out, so the reminder window opens tomorrow.
        self.deadline = Deadline.objects.create(
            closes_at=timezone.now() + timedelta(days=8), is_active=True
        )

    def _team(self, name):
        group = Groups.objects.create(group_name=name)
        user = User.objects.create_user(
            email=f"{name.lower()}@test.local", password="testUser@123",
            first_name="Test", last_name="Student",
        )
        RoleAssignmentHistory.objects.create(
            user=user, role=self.role, valid_from=timezone.now(), valid_to=None
        )
        GroupMembership.objects.create(group=group, user=user, membership_role="student")
        return group

    def _inside_window(self):
        return self.deadline.closes_at - timedelta(days=3)

    def _complete(self, group):
        submission = Submission.objects.create(
            group=group,
            answers={q.key: "An answer." for q in SubmissionQuestion.active()},
            poster={"storage_key": "k", "name": "poster.pdf", "mime": "application/pdf"},
        )
        return submission

    def _names_due(self, now):
        return {group.group_name for group, _, _ in teams_due(now)}

    def test_a_team_that_never_started_is_reminded(self):
        self._team("BTF-NOTHING")

        self.assertIn("BTF-NOTHING", self._names_due(self._inside_window()))

    def test_a_team_with_a_half_finished_entry_is_reminded(self):
        group = self._team("BTF-PARTIAL")
        Submission.objects.create(group=group, answers={"solution_purpose": "Only one."})

        self.assertIn("BTF-PARTIAL", self._names_due(self._inside_window()))

    def test_a_team_that_has_submitted_is_left_alone(self):
        group = self._team("BTF-DONE")
        submission = self._complete(group)
        submission.snapshot(None)
        submission.save()

        self.assertNotIn("BTF-DONE", self._names_due(self._inside_window()))

    def test_nobody_is_reminded_before_the_final_week(self):
        self._team("BTF-EARLY")

        self.assertEqual(self._names_due(timezone.now()), set())

    def test_nobody_is_reminded_once_the_deadline_has_passed(self):
        self._team("BTF-LATE")

        after = self.deadline.closes_at + timedelta(minutes=1)
        self.assertEqual(self._names_due(after), set())

    def test_a_team_with_no_students_is_not_chased(self):
        Groups.objects.create(group_name="BTF-EMPTY")

        result = send_due_reminders(self._inside_window())

        self.assertEqual(result["sent"], 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_an_extended_team_is_reminded_against_their_own_deadline(self):
        group = self._team("BTF-EXTENDED")
        GroupExtension.objects.create(
            group=group, extended_until=timezone.now() + timedelta(days=30)
        )

        self.assertNotIn("BTF-EXTENDED", self._names_due(self._inside_window()))

    def test_an_extended_team_is_told_their_own_closing_date(self):
        group = self._team("BTF-EXTENDED")
        extended_until = timezone.now() + timedelta(days=2)
        GroupExtension.objects.create(group=group, extended_until=extended_until)

        send_due_reminders(timezone.now())

        self.assertEqual(len(mail.outbox), 1)
        expected = timezone.localtime(extended_until).strftime("%A")
        self.assertIn(expected, mail.outbox[0].body)

    def test_a_team_is_written_to_once_a_day_however_often_the_job_runs(self):
        self._team("BTF-DAILY")
        moment = self._inside_window()

        send_due_reminders(moment)
        send_due_reminders(moment)

        self.assertEqual(len(mail.outbox), 1)

    def test_the_next_day_brings_another_reminder(self):
        group = self._team("BTF-DAILY")
        send_due_reminders(self._inside_window())

        SubmissionReminder.objects.filter(group=group).update(
            last_sent_on=timezone.localdate(self._inside_window()) - timedelta(days=1)
        )
        send_due_reminders(self._inside_window())

        self.assertEqual(len(mail.outbox), 2)

    def test_a_dry_run_sends_nothing_and_records_nothing(self):
        self._team("BTF-DRY")

        result = send_due_reminders(self._inside_window(), dry_run=True)

        self.assertEqual(result["sent"], 1)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(SubmissionReminder.objects.exists())

    def test_the_email_names_the_required_components_the_right_way_round(self):
        self._team("BTF-COPY")

        send_due_reminders(self._inside_window())

        body = mail.outbox[0].body
        required, optional = body.split("OPTIONAL COMPONENTS")
        self.assertIn("Poster", required)
        self.assertIn("Short Answer Questions", required)
        self.assertIn("Scientific Report", optional)
        self.assertIn("Prototype", optional)

    def test_a_component_already_uploaded_is_not_reported_as_missing(self):
        group = self._team("BTF-HALF")
        Submission.objects.create(
            group=group,
            poster={"storage_key": "k", "name": "poster.pdf", "mime": "application/pdf"},
        )

        send_due_reminders(self._inside_window())

        body = mail.outbox[0].body
        poster_line = body.split("Poster")[1].split("Short Answer")[0]
        self.assertIn("Submitted", poster_line)
        self.assertNotIn("Not Submitted", poster_line)

    def test_the_reminder_reaches_the_team(self):
        self._team("BTF-TO")

        send_due_reminders(self._inside_window())

        self.assertEqual(mail.outbox[0].to, ["btf-to@test.local"])
        self.assertIn("BTF-TO", mail.outbox[0].subject)


@override_settings(USE_AZURE_BLOB_STORAGE=False, SUBMISSION_REMINDER_TOKEN="s3cret")
class ReminderTriggerEndpointTests(TestCase):
    def setUp(self):
        from django.urls import reverse

        self.url = reverse("submission-send-reminders")

    def test_the_right_token_runs_the_job(self):
        response = self.client.post(self.url, HTTP_X_REMINDER_TOKEN="s3cret")

        self.assertEqual(response.status_code, 200)
        self.assertIn("sent", response.data)

    def test_a_wrong_token_is_refused(self):
        response = self.client.post(self.url, HTTP_X_REMINDER_TOKEN="wrong")

        self.assertEqual(response.status_code, 401)

    def test_no_token_at_all_is_refused(self):
        self.assertEqual(self.client.post(self.url).status_code, 401)

    @override_settings(SUBMISSION_REMINDER_TOKEN="")
    def test_an_unconfigured_trigger_refuses_rather_than_standing_open(self):
        response = self.client.post(self.url, HTTP_X_REMINDER_TOKEN="")

        self.assertEqual(response.status_code, 503)


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class IndividualDeliveryTests(TestCase):
    def setUp(self):
        self.role = Roles.objects.create(role_name="student")
        install_question_set()
        self.deadline = Deadline.objects.create(
            closes_at=timezone.now() + timedelta(days=3), is_active=True
        )
        self.group = Groups.objects.create(group_name="BTF-TEAM")
        for name in ("ada", "grace", "alan"):
            user = User.objects.create_user(
                email=f"{name}@test.local", password="testUser@123",
                first_name=name.title(), last_name="Student",
            )
            RoleAssignmentHistory.objects.create(
                user=user, role=self.role, valid_from=timezone.now(), valid_to=None
            )
            GroupMembership.objects.create(
                group=self.group, user=user, membership_role="student"
            )

    def test_every_student_gets_their_own_message(self):
        send_due_reminders()

        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(
            sorted(m.to[0] for m in mail.outbox),
            ["ada@test.local", "alan@test.local", "grace@test.local"],
        )

    def test_no_student_can_see_a_teammates_address(self):
        send_due_reminders()

        for message in mail.outbox:
            self.assertEqual(len(message.to), 1)
            self.assertFalse(message.cc)
            self.assertFalse(message.bcc)

    def test_everyone_receives_the_same_email(self):
        send_due_reminders()

        subjects = {m.subject for m in mail.outbox}
        bodies = {m.body for m in mail.outbox}
        self.assertEqual(len(subjects), 1)
        self.assertEqual(len(bodies), 1, "students were sent differing text")

    def test_one_bad_address_does_not_cost_the_rest_of_the_team_their_copy(self):
        from unittest.mock import patch

        real_send = mail.EmailMessage.send

        def flaky(self, *args, **kwargs):
            if self.to == ["grace@test.local"]:
                raise OSError("mailbox unavailable")
            return real_send(self, *args, **kwargs)

        with patch.object(mail.EmailMessage, "send", flaky):
            result = send_due_reminders()

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(result["sent"], 1, "the team should still count as reminded")

    def test_a_team_nobody_could_be_reached_on_is_tried_again_tomorrow(self):
        from unittest.mock import patch

        with patch.object(mail.EmailMessage, "send", side_effect=OSError("relay down")):
            result = send_due_reminders()

        self.assertEqual(result["failed"], 1)
        self.assertFalse(SubmissionReminder.objects.exists())
