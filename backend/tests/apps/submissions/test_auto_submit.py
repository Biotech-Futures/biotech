"""Tests for submitting complete drafts once a team's cut-off has passed."""
from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.groups.models import Groups
from apps.submissions.autosubmit import auto_submit_due
from apps.submissions.models import Deadline, GroupExtension, Submission
from apps.submissions.services import current_cohort

from .seed_data import install_question_set

POSTER = {"storage_key": "a/poster.pdf", "name": "poster.pdf", "mime": "application/pdf", "size": 10}


@override_settings(USE_AZURE_BLOB_STORAGE=False, EMAIL_JOBS_TOKEN="jobs-token")
class AutoSubmitTests(TestCase):
    def setUp(self):
        self.questions = install_question_set()
        # Announced an hour ago with two hours' grace: still being accepted.
        self.deadline = Deadline.objects.create(
            closes_at=timezone.now() - timedelta(hours=1), grace_hours=2, is_active=True,
        )
        self.group = Groups.objects.create(group_name="BTF-AUTO")

    def _entry(self, group=None, **fields):
        values = {
            "project_title": "Our Project",
            "answers": {q.key: "An answer." for q in self.questions},
            "poster": POSTER,
            **fields,
        }
        return Submission.objects.create(group=group or self.group, **values)

    def _close_grace(self):
        self.deadline.grace_hours = 0
        self.deadline.save()

    def test_a_complete_draft_is_submitted_once_the_grace_period_ends(self):
        entry = self._entry()
        self.assertEqual(auto_submit_due()["submitted"], [])

        self._close_grace()
        result = auto_submit_due()

        entry.refresh_from_db()
        self.assertEqual(result["submitted"], ["BTF-AUTO"])
        self.assertTrue(entry.is_submitted)
        self.assertTrue(entry.auto_submitted)
        self.assertIsNone(entry.submitted_by)
        self.assertTrue(entry.is_late)
        self.assertEqual(entry.submitted_answers, entry.answers)
        self.assertEqual(entry.submitted_poster, POSTER)
        self.assertEqual(mail.outbox, [])

    def test_waits_for_an_extension_and_its_grace(self):
        self._close_grace()
        self._entry()
        extension = GroupExtension.objects.create(
            group=self.group, extended_until=timezone.now() - timedelta(hours=1), grace_hours=2,
        )
        self.assertEqual(auto_submit_due()["submitted"], [])

        extension.grace_hours = 0
        extension.save()
        self.assertEqual(auto_submit_due()["submitted"], ["BTF-AUTO"])

    def test_incomplete_drafts_are_left_alone(self):
        self._close_grace()
        others = [Groups.objects.create(group_name=f"BTF-GAP{i}") for i in range(3)]
        self._entry(group=others[0], poster=None)
        self._entry(group=others[1], project_title="")
        self._entry(group=others[2], answers={self.questions[0].key: "Only one."})

        self.assertEqual(auto_submit_due()["submitted"], [])
        self.assertFalse(Submission.objects.filter(submitted_at__isnull=False).exists())

    def test_an_earlier_submission_stands(self):
        self._close_grace()
        earlier = timezone.now() - timedelta(days=2)
        self._entry(submitted_at=earlier)
        reopened = self._entry(
            group=Groups.objects.create(group_name="BTF-REOPENED"),
            submitted_at=earlier, reopened_at=earlier + timedelta(hours=1),
        )

        self.assertEqual(auto_submit_due()["submitted"], [])
        reopened.refresh_from_db()
        self.assertEqual(reopened.submitted_at, earlier)
        self.assertFalse(reopened.auto_submitted)

    def test_a_previous_rounds_draft_is_left_alone(self):
        self._close_grace()
        self._entry(cohort=current_cohort() - 1)

        self.assertEqual(auto_submit_due()["submitted"], [])

    def test_running_again_changes_nothing(self):
        self._close_grace()
        entry = self._entry()
        auto_submit_due()
        entry.refresh_from_db()
        first = entry.submitted_at

        self.assertEqual(auto_submit_due()["submitted"], [])
        entry.refresh_from_db()
        self.assertEqual(entry.submitted_at, first)

    def test_a_dry_run_only_lists_the_teams(self):
        self._close_grace()
        entry = self._entry()
        out = StringIO()

        call_command("auto_submit_entries", "--dry-run", stdout=out)

        entry.refresh_from_db()
        self.assertIn("BTF-AUTO", out.getvalue())
        self.assertIn("Would submit 1 team(s).", out.getvalue())
        self.assertFalse(entry.is_submitted)

    def test_the_scheduled_endpoint_needs_the_jobs_token(self):
        self._close_grace()
        self._entry()
        url = reverse("submission-auto-submit")

        self.assertNotEqual(APIClient().post(url).status_code, 200)
        response = APIClient().post(url, HTTP_X_EMAIL_JOBS_TOKEN="jobs-token")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["submitted"], ["BTF-AUTO"])
