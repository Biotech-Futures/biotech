"""Tests for the submission confirmation email.

The email is the only record a team gets of what the platform actually
received, so the statuses it reports have to match the stored submission
exactly — a "Submitted" against a component that never arrived would be worse
than sending nothing.
"""
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.storage import reset_managed_storage_caches
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.emails import build_components, recipients_for
from apps.submissions.models import Deadline, Submission, SubmissionQuestion
from apps.users.models import User

from .seed_data import install_question_set


@override_settings(USE_AZURE_BLOB_STORAGE=False, AUTH_EMAIL_DISPATCH_SYNC=True)
class SubmissionEmailTests(TestCase):
    def setUp(self):
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        self.roles = {
            name: Roles.objects.create(role_name=name)
            for name in ("student", "mentor", "supervisor")
        }
        self.group = Groups.objects.create(group_name="BTF-EMAIL")

        self.students = []
        for i in (1, 2):
            user = User.objects.create_user(
                email=f"student{i}@test.local", password="testUser@123",
                first_name=f"Student{i}", last_name="Test",
            )
            RoleAssignmentHistory.objects.create(
                user=user, role=self.roles["student"], valid_from=timezone.now(), valid_to=None
            )
            GroupMembership.objects.create(
                group=self.group, user=user, membership_role="student"
            )
            self.students.append(user)

        for role in ("mentor", "supervisor"):
            user = User.objects.create_user(
                email=f"{role}@test.local", password="testUser@123",
                first_name=role.title(), last_name="Test",
            )
            RoleAssignmentHistory.objects.create(
                user=user, role=self.roles[role], valid_from=timezone.now(), valid_to=None
            )
            GroupMembership.objects.create(group=self.group, user=user, membership_role=role)

        install_question_set()
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)

        self.client = APIClient()
        self.client.force_authenticate(user=self.students[0])
        self.detail_url = reverse("group-submission", kwargs={"group_id": self.group.id})
        self.submit_url = reverse("group-submission-submit", kwargs={"group_id": self.group.id})

    def _complete_and_submit(self):
        submission, _ = Submission.objects.get_or_create(group=self.group)
        submission.answers = {q.key: "An answer." for q in SubmissionQuestion.active()}
        submission.poster = {
            "storage_key": "x/poster.pdf", "name": "poster.pdf",
            "mime": "application/pdf", "size": 100,
        }
        submission.save()
        return self.client.post(self.submit_url, {}, format="json")

    # ------------------------------------------------------------ recipients
    def test_only_students_are_emailed(self):
        # Mentors and supervisors have no part in submissions, so they do not
        # receive a copy of the team's entry summary either.
        self.assertEqual(
            recipients_for(self.group),
            ["student1@test.local", "student2@test.local"],
        )

    def test_every_student_on_the_team_is_emailed(self):
        self._complete_and_submit()

        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(
            mail.outbox[0].to, ["student1@test.local", "student2@test.local"]
        )

    # -------------------------------------------------------------- contents
    def test_sent_on_submit_with_the_group_in_the_subject(self):
        self._complete_and_submit()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("BTF-EMAIL", mail.outbox[0].subject)

    def test_a_complete_submission_reports_every_required_component(self):
        self._complete_and_submit()
        body = mail.outbox[0].alternatives[0][0]

        self.assertIn("Poster", body)
        self.assertIn("Short Answer Questions (SAQs)", body)
        self.assertIn("Submitted", body)
        # The "not yet complete" warning would undermine a valid confirmation.
        self.assertNotIn("Your submission is not yet complete", body)

    def test_missing_optional_components_are_marked_absent(self):
        self._complete_and_submit()
        body = mail.outbox[0].alternatives[0][0]

        self.assertIn("Scientific Report", body)
        self.assertIn("Absent", body)

    def test_statuses_describe_the_submitted_copy_not_the_draft(self):
        # A team that reopens and edits must not receive an email implying the
        # edits were recorded; only a completed submission changes the record.
        self._complete_and_submit()
        mail.outbox.clear()

        submission = Submission.objects.get(group=self.group)
        submission.report = {
            "storage_key": "x/report.pdf", "name": "report.pdf",
            "mime": "application/pdf", "size": 50,
        }
        submission.save()

        required, optional = build_components(Submission.objects.get(group=self.group))
        report = next(item for item in optional if item["label"] == "Scientific Report")
        self.assertEqual(report["status"], "Absent")
        self.assertTrue(all(item["submitted"] for item in required))

    def test_a_prototype_link_alone_counts_as_submitted(self):
        submission, _ = Submission.objects.get_or_create(group=self.group)
        submission.answers = {q.key: "An answer." for q in SubmissionQuestion.active()}
        submission.poster = {"storage_key": "x/p.pdf", "name": "p.pdf", "mime": "", "size": 1}
        submission.prototype_url = "https://example.com/demo"
        submission.save()
        self.client.post(self.submit_url, {}, format="json")

        _, optional = build_components(Submission.objects.get(group=self.group))
        prototype = next(item for item in optional if item["label"] == "Prototype")
        self.assertEqual(prototype["status"], "Submitted")

    # --------------------------------------------------------------- failure
    def test_a_failed_send_does_not_fail_the_submission(self):
        # The submission is already saved by this point; losing the email is a
        # far better outcome than telling a team their entry did not go through.
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from unittest.mock import patch

            with patch("apps.submissions.emails.render_to_string", side_effect=OSError("boom")):
                response = self._complete_and_submit()

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(Submission.objects.get(group=self.group).submitted_at)
