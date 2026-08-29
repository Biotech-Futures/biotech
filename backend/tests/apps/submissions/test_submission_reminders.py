"""Who gets a submission reminder, and who does not.

The rules being pinned here are the ones a team would notice if they were
wrong: being chased after they have finished, being written to twice in a day,
being told the wrong closing date, or — the quietest failure of the four —
never being written to at all because they had not started.
"""
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
        # Announced in eight days, so the reminder window opens tomorrow.
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
        """A moment three days before the announced deadline."""
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

    # ------------------------------------------------------------- who is due
    def test_a_team_that_never_started_is_reminded(self):
        # The quietest failure this could have: these teams have no submission
        # row, so anything that queried submissions would skip exactly the
        # teams most in need of a reminder.
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

        # Eight days out, which is one day before the window opens.
        self.assertEqual(self._names_due(timezone.now()), set())

    def test_nobody_is_reminded_once_the_deadline_has_passed(self):
        # Reminders stop at the announced time rather than when writes are
        # actually refused: the grace period after it is not published, and an
        # email arriving inside it would announce it.
        self._team("BTF-LATE")

        after = self.deadline.closes_at + timedelta(minutes=1)
        self.assertEqual(self._names_due(after), set())

    def test_a_team_with_no_students_is_not_chased(self):
        Groups.objects.create(group_name="BTF-EMPTY")

        result = send_due_reminders(self._inside_window())

        self.assertEqual(result["sent"], 0)
        self.assertEqual(len(mail.outbox), 0)

    # ------------------------------------------------------------ extensions
    def test_an_extended_team_is_reminded_against_their_own_deadline(self):
        # Their week runs from the date they were granted, not the one the
        # programme published, so at this moment they are not yet due.
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

    # --------------------------------------------------------- sending once
    def test_a_team_is_written_to_once_a_day_however_often_the_job_runs(self):
        self._team("BTF-DAILY")
        moment = self._inside_window()

        send_due_reminders(moment)
        send_due_reminders(moment)

        self.assertEqual(len(mail.outbox), 1)

    def test_the_next_day_brings_another_reminder(self):
        group = self._team("BTF-DAILY")
        send_due_reminders(self._inside_window())

        # Move the record back a day, as tomorrow's run would find it.
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

    # ------------------------------------------------------------- contents
    def test_the_email_names_the_required_components_the_right_way_round(self):
        # The client's copy had the report required and the SAQs optional,
        # contradicting their own confirmation email and the question set. This
        # pins the correction so it cannot be quietly undone.
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
    """The scheduler's way in. Guarded by a shared secret, not a session."""

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
        # The dangerous failure would be a deploy that forgot the secret and
        # left an endpoint anyone could use to email every team.
        response = self.client.post(self.url, HTTP_X_REMINDER_TOKEN="")

        self.assertEqual(response.status_code, 503)
