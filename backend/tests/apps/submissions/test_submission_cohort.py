"""Tests for the cohort stamped on a submitted entry.

The cohort exists so a judging or reporting tool can ask "every entry in the
2026 competition" without inferring it from ``submitted_at``. The cases below
are the ones where the two genuinely disagree — which is the whole reason the
column is stored rather than derived.
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.storage import reset_managed_storage_caches
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import Deadline, GroupExtension, Submission
from apps.submissions.services import current_cohort
from apps.users.models import User

from .seed_data import install_question_set


@override_settings(USE_AZURE_BLOB_STORAGE=False, AUTH_EMAIL_DISPATCH_SYNC=True)
class SubmissionCohortTests(TestCase):
    def setUp(self):
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        role = Roles.objects.create(role_name="student")
        self.group = Groups.objects.create(group_name="BTF-COHORT")
        self.student = User.objects.create_user(
            email="cohort@test.local", password="testUser@123",
            first_name="Ada", last_name="Lovelace",
        )
        RoleAssignmentHistory.objects.create(
            user=self.student, role=role, valid_from=timezone.now(), valid_to=None
        )
        GroupMembership.objects.create(
            group=self.group, user=self.student, membership_role="student"
        )
        self.questions = install_question_set()

        self.client = APIClient()
        self.client.force_authenticate(user=self.student)
        self.submit_url = reverse("group-submission-submit", kwargs={"group_id": self.group.id})

    def _submit(self):
        submission, _ = Submission.objects.get_or_create(group=self.group)
        submission.answers = {q.key: "An answer." for q in self.questions}
        submission.poster = {
            "storage_key": "c/poster.pdf", "name": "poster.pdf",
            "mime": "application/pdf", "size": 10,
        }
        submission.save()
        return self.client.post(self.submit_url, {}, format="json")

    def test_cohort_comes_from_the_deadline_year(self):
        Deadline.objects.create(
            closes_at=timezone.now() + timedelta(days=1), is_active=True
        )
        expected = timezone.localtime(Deadline.objects.get().closes_at).year

        self.assertEqual(self._submit().status_code, 200)
        self.assertEqual(Submission.objects.get(group=self.group).cohort, expected)

    def test_an_extension_does_not_move_a_team_into_another_cohort(self):
        # The case the column exists for: a team extended into the following year
        # still competes in the same cohort, so the programme's deadline decides.
        closes = timezone.now().replace(month=9, day=18) + timedelta(days=1)
        Deadline.objects.create(closes_at=closes, is_active=True)
        GroupExtension.objects.create(
            group=self.group, extended_until=closes + timedelta(days=200)
        )

        self.assertEqual(self._submit().status_code, 200)
        self.assertEqual(
            Submission.objects.get(group=self.group).cohort,
            timezone.localtime(closes).year,
        )

    def test_cohort_is_indexed_for_bulk_lookup(self):
        # A judging tool's first query is "every entry in this cohort"; without
        # an index that is a full scan of every submission ever made.
        field = Submission._meta.get_field("cohort")
        self.assertTrue(field.db_index)

    def test_current_cohort_falls_back_to_the_current_year(self):
        # No deadline configured is a misconfiguration, not a normal state, but
        # it must not raise while stamping an entry.
        self.assertEqual(current_cohort(), timezone.localtime().year)
