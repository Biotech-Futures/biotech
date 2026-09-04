"""Tests for the submit / reopen / resubmit lifecycle.

The case that matters most is a team reopening their entry and then not
finishing: the version they submitted must survive untouched, because on
deadline day the alternative is a team losing a complete entry.
"""
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.storage import reset_managed_storage_caches
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import Deadline, Submission, SubmissionQuestion
from apps.submissions.storage import submission_file_service
from apps.users.models import User

from .seed_data import install_question_set


def _pdf(name="poster.pdf", body=b"poster"):
    return SimpleUploadedFile(
        name, b"%PDF-1.7\n" + body + b"\n%%EOF\n", content_type="application/pdf"
    )


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class SubmissionLifecycleTests(TestCase):
    def setUp(self):
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        role = Roles.objects.create(role_name="student")
        self.group = Groups.objects.create(group_name="BTF-LIFECYCLE")
        self.student = User.objects.create_user(
            email="lifecycle@test.local", password="testUser@123",
            first_name="Ada", last_name="Lovelace",
        )
        RoleAssignmentHistory.objects.create(
            user=self.student, role=role, valid_from=timezone.now(), valid_to=None
        )
        GroupMembership.objects.create(
            group=self.group, user=self.student, membership_role="student"
        )
        install_question_set()
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)

        self.client = APIClient()
        self.client.force_authenticate(user=self.student)

        self.detail_url = reverse("group-submission", kwargs={"group_id": self.group.id})
        self.submit_url = reverse("group-submission-submit", kwargs={"group_id": self.group.id})
        self.reopen_url = reverse("group-submission-reopen", kwargs={"group_id": self.group.id})

    # ------------------------------------------------------------- helpers
    def _file_url(self, slot):
        return reverse(
            "group-submission-file", kwargs={"group_id": self.group.id, "slot": slot}
        )

    def _answers(self, text="An answer."):
        return {q.key: text for q in SubmissionQuestion.active()}

    def _fill_and_submit(self, text="Original answer.", poster_name="original.pdf"):
        self.client.put(self.detail_url, {"answers": self._answers(text)}, format="json")
        self.client.post(self._file_url("poster"), {"file": _pdf(poster_name)}, format="multipart")
        return self.client.post(self.submit_url, {}, format="json")

    def _submission(self):
        return Submission.objects.get(group=self.group)

    # -------------------------------------------------------------- states
    def test_a_new_entry_is_in_progress(self):
        self.client.put(self.detail_url, {"answers": self._answers()}, format="json")

        submission = self._submission()
        self.assertEqual(submission.stage, "in_progress")
        self.assertFalse(submission.is_locked)

    def test_submitting_locks_the_entry(self):
        self.assertEqual(self._fill_and_submit().status_code, 200)

        submission = self._submission()
        self.assertEqual(submission.stage, "submitted")
        self.assertTrue(submission.is_locked)
        self.assertEqual(submission.submitted_by, self.student)

    def test_reopening_unlocks_it_again(self):
        self._fill_and_submit()

        response = self.client.post(self.reopen_url, {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._submission().stage, "revising")

    def test_reopening_an_unsubmitted_entry_is_refused(self):
        self.client.put(self.detail_url, {"answers": self._answers()}, format="json")
        self.assertEqual(self.client.post(self.reopen_url, {}, format="json").status_code, 400)

    # --------------------------------------------------------------- locking
    def test_a_locked_entry_refuses_edits(self):
        self._fill_and_submit()

        saved = self.client.put(
            self.detail_url, {"answers": self._answers("sneaky edit")}, format="json"
        )
        uploaded = self.client.post(
            self._file_url("report"), {"file": _pdf("report.pdf")}, format="multipart"
        )
        removed = self.client.delete(self._file_url("poster"))

        for response in (saved, uploaded, removed):
            self.assertEqual(response.status_code, 409)
        self.assertEqual(self._submission().submitted_answers, self._answers("Original answer."))

    def test_a_locked_entry_can_still_be_read(self):
        # Locking editing must not hide a team's own work from them.
        self._fill_and_submit()

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["submission"]["stage"], "submitted")
        self.assertEqual(response.data["submission"]["submitted_by_name"], "Ada Lovelace")

    def test_submitting_twice_without_reopening_is_refused(self):
        self._fill_and_submit()
        self.assertEqual(self.client.post(self.submit_url, {}, format="json").status_code, 409)

    # ------------------------------------------------- the abandoned revision
    def test_an_abandoned_revision_leaves_the_submitted_copy_intact(self):
        self._fill_and_submit("Original answer.", "original.pdf")
        original_key = self._submission().submitted_poster["storage_key"]

        # Reopen, change everything, then never submit again.
        self.client.post(self.reopen_url, {}, format="json")
        self.client.put(self.detail_url, {"answers": self._answers("Half-written.")}, format="json")
        self.client.post(
            self._file_url("poster"), {"file": _pdf("replacement.pdf")}, format="multipart"
        )

        submission = self._submission()
        # The draft has moved on...
        self.assertEqual(submission.answers, self._answers("Half-written."))
        self.assertEqual(submission.poster["name"], "replacement.pdf")
        # ...but what was submitted has not.
        self.assertEqual(submission.submitted_answers, self._answers("Original answer."))
        self.assertEqual(submission.submitted_poster["name"], "original.pdf")
        # And the submitted file itself still exists to be downloaded.
        self.assertTrue(submission_file_service("poster").exists(original_key))

    def test_removing_a_file_during_a_revision_keeps_the_submitted_one(self):
        self._fill_and_submit()
        original_key = self._submission().submitted_poster["storage_key"]

        self.client.post(self.reopen_url, {}, format="json")
        self.assertEqual(self.client.delete(self._file_url("poster")).status_code, 200)

        submission = self._submission()
        self.assertIsNone(submission.poster)
        self.assertIsNotNone(submission.submitted_poster)
        self.assertTrue(submission_file_service("poster").exists(original_key))

    def test_completing_a_revision_replaces_the_submitted_copy(self):
        self._fill_and_submit("Original answer.", "original.pdf")
        original_key = self._submission().submitted_poster["storage_key"]

        self.client.post(self.reopen_url, {}, format="json")
        self.client.put(self.detail_url, {"answers": self._answers("Revised.")}, format="json")
        self.client.post(
            self._file_url("poster"), {"file": _pdf("revised.pdf")}, format="multipart"
        )
        self.assertEqual(self.client.post(self.submit_url, {}, format="json").status_code, 200)

        submission = self._submission()
        self.assertEqual(submission.submitted_answers, self._answers("Revised."))
        self.assertEqual(submission.submitted_poster["name"], "revised.pdf")
        self.assertTrue(submission.is_locked)
        # The superseded file is only cleaned up now that it is genuinely unused.
        self.assertFalse(submission_file_service("poster").exists(original_key))

    def test_only_one_submission_record_exists_throughout(self):
        self._fill_and_submit()
        self.client.post(self.reopen_url, {}, format="json")
        self.client.put(self.detail_url, {"answers": self._answers("Revised.")}, format="json")
        self.client.post(self.submit_url, {}, format="json")

        self.assertEqual(Submission.objects.filter(group=self.group).count(), 1)


class SubmissionStageTests(TestCase):
    """The four stages an entry moves through, said without the deadline.

    Stage is deliberately blind to whether submissions are still open: that is
    a fact about the competition, not about this entry. Keeping them apart is
    what lets a caller say "submitted, and the window has closed" without
    inventing a fifth stage for it.
    """

    def setUp(self):
        self.group = Groups.objects.create(group_name="BTF-STAGE")

    def test_an_untouched_entry_has_not_started(self):
        submission = Submission.objects.create(group=self.group)

        self.assertEqual(submission.stage, "not_started")

    def test_whitespace_alone_does_not_count_as_started(self):
        submission = Submission.objects.create(
            group=self.group, answers={"solution_purpose": "   "}
        )

        self.assertEqual(submission.stage, "not_started")

    def test_a_written_answer_makes_it_in_progress(self):
        submission = Submission.objects.create(
            group=self.group, answers={"solution_purpose": "Something."}
        )

        self.assertEqual(submission.stage, "in_progress")

    def test_an_uploaded_file_alone_makes_it_in_progress(self):
        submission = Submission.objects.create(
            group=self.group, poster={"storage_key": "k", "name": "p.pdf"}
        )

        self.assertEqual(submission.stage, "in_progress")

    def test_a_prototype_link_alone_makes_it_in_progress(self):
        submission = Submission.objects.create(
            group=self.group, prototype_url="https://example.org/demo"
        )

        self.assertEqual(submission.stage, "in_progress")

    def test_a_completed_entry_is_submitted(self):
        submission = Submission.objects.create(
            group=self.group, answers={"solution_purpose": "Something."}
        )
        submission.snapshot(None)
        submission.save()

        self.assertEqual(submission.stage, "submitted")

    def test_reopening_moves_it_to_revising(self):
        submission = Submission.objects.create(
            group=self.group, answers={"solution_purpose": "Something."}
        )
        submission.snapshot(None)
        submission.save()
        submission.reopened_at = submission.submitted_at + timedelta(minutes=1)
        submission.save()

        self.assertEqual(submission.stage, "revising")

    def test_a_revising_entry_still_counts_as_submitted(self):
        # The distinction the old two-value status could not express: work is
        # under way *and* there is a completed entry on record.
        submission = Submission.objects.create(
            group=self.group, answers={"solution_purpose": "Something."}
        )
        submission.snapshot(None)
        submission.save()
        submission.reopened_at = submission.submitted_at + timedelta(minutes=1)
        submission.save()

        self.assertEqual(submission.stage, "revising")
        self.assertTrue(submission.is_submitted)
        self.assertFalse(submission.is_locked)
