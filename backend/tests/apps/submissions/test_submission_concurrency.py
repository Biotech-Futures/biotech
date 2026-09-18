"""Tests for teammates editing one entry at once; the same question is last-write-wins."""
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.storage import reset_managed_storage_caches
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import Deadline, Submission, SubmissionQuestion
from apps.users.models import User

from .seed_data import install_question_set


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class ConcurrentEditTests(TestCase):
    def setUp(self):
        self.role = Roles.objects.create(role_name="student")
        self.group = Groups.objects.create(group_name="BTF-CONCURRENT")
        self.ada = self._student("ada@test.local")
        self.grace = self._student("grace@test.local")
        self.questions = install_question_set()
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)
        self.url = reverse("group-submission", kwargs={"group_id": self.group.id})

    def _student(self, email):
        user = User.objects.create_user(
            email=email, password="testUser@123", first_name="Test", last_name="Student"
        )
        RoleAssignmentHistory.objects.create(
            user=user, role=self.role, valid_from=timezone.now(), valid_to=None
        )
        GroupMembership.objects.create(
            group=self.group, user=user, membership_role="student"
        )
        return user

    def _client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _save(self, user, answers):
        return self._client_for(user).put(self.url, {"answers": answers}, format="json")

    def _stored(self):
        return Submission.objects.get(group=self.group).answers

    def test_teammates_on_different_questions_do_not_overwrite_each_other(self):
        first, second = self.questions[0].key, self.questions[1].key

        self.assertEqual(self._save(self.ada, {first: "Ada's answer."}).status_code, 200)
        self.assertEqual(self._save(self.grace, {second: "Grace's answer."}).status_code, 200)

        stored = self._stored()
        self.assertEqual(stored[first], "Ada's answer.")
        self.assertEqual(stored[second], "Grace's answer.")

    def test_a_save_leaves_untouched_answers_alone(self):
        first, second = self.questions[0].key, self.questions[1].key
        self._save(self.ada, {first: "Kept.", second: "Also kept."})

        self._save(self.ada, {first: "Edited."})

        stored = self._stored()
        self.assertEqual(stored[first], "Edited.")
        self.assertEqual(stored[second], "Also kept.")

    def test_clearing_an_answer_requires_an_explicit_empty_string(self):
        key = self.questions[0].key
        self._save(self.ada, {key: "Written."})

        self._save(self.ada, {key: ""})

        self.assertEqual(self._stored()[key], "")

    def test_the_same_question_is_still_last_write_wins(self):
        key = self.questions[0].key

        self._save(self.ada, {key: "Ada's version."})
        self._save(self.grace, {key: "Grace's version."})

        self.assertEqual(self._stored()[key], "Grace's version.")

    def test_an_empty_answers_payload_changes_nothing(self):
        key = self.questions[0].key
        self._save(self.ada, {key: "Untouched."})

        self.assertEqual(self._save(self.grace, {}).status_code, 200)
        self.assertEqual(self._stored()[key], "Untouched.")


def _pdf(name="poster.pdf"):
    return SimpleUploadedFile(
        name, b"%PDF-1.7\nposter\n%%EOF\n", content_type="application/pdf"
    )


# Sends inline so mail work does not leak past the end of a test.
@override_settings(USE_AZURE_BLOB_STORAGE=False, AUTH_EMAIL_DISPATCH_SYNC=True)
class ConcurrentSubmitTests(TestCase):
    """SQLite has no row locks, so the submit lock is asserted structurally rather than raced."""

    def setUp(self):
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        self.role = Roles.objects.create(role_name="student")
        self.group = Groups.objects.create(group_name="BTF-SUBMIT-RACE")
        self.ada = self._student("ada.submit@test.local")
        self.grace = self._student("grace.submit@test.local")
        install_question_set()
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)

        self.detail_url = reverse("group-submission", kwargs={"group_id": self.group.id})
        self.submit_url = reverse(
            "group-submission-submit", kwargs={"group_id": self.group.id}
        )
        self.file_url = reverse(
            "group-submission-file",
            kwargs={"group_id": self.group.id, "slot": "poster"},
        )

    def _student(self, email):
        user = User.objects.create_user(
            email=email, password="testUser@123", first_name="Test", last_name="Student"
        )
        RoleAssignmentHistory.objects.create(
            user=user, role=self.role, valid_from=timezone.now(), valid_to=None
        )
        GroupMembership.objects.create(
            group=self.group, user=user, membership_role="student"
        )
        return user

    def _client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _answers(self, text="An answer."):
        return {q.key: text for q in SubmissionQuestion.active()}

    def _make_submittable(self, user):
        client = self._client_for(user)
        client.put(self.detail_url, {"answers": self._answers()}, format="json")
        client.post(self.file_url, {"file": _pdf()}, format="multipart")
        return client

    def test_submitting_claims_the_row_for_update_before_overwriting_it(self):
        client = self._make_submittable(self.ada)

        locked_models = []
        original = QuerySet.select_for_update

        def recording(self, *args, **kwargs):
            locked_models.append(self.model)
            return original(self, *args, **kwargs)

        with patch.object(QuerySet, "select_for_update", recording):
            response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            Submission,
            locked_models,
            "submitting read the entry without locking it, so a teammate's save "
            "landing mid-submit would be silently overwritten",
        )

    def test_the_frozen_copy_carries_an_answer_saved_moments_earlier(self):
        client = self._make_submittable(self.ada)
        key = SubmissionQuestion.active().first().key
        self._client_for(self.grace).put(
            self.detail_url, {"answers": {key: "Grace's late edit."}}, format="json"
        )

        self.assertEqual(client.post(self.submit_url, {}, format="json").status_code, 200)

        submission = Submission.objects.get(group=self.group)
        self.assertEqual(submission.submitted_answers[key], "Grace's late edit.")
        self.assertEqual(submission.answers[key], "Grace's late edit.")

    def test_a_second_submit_is_refused_rather_than_recorded_twice(self):
        client = self._make_submittable(self.ada)
        self.assertEqual(client.post(self.submit_url, {}, format="json").status_code, 200)
        after_first = len(mail.outbox)
        self.assertEqual(after_first, 2)

        second = self._client_for(self.grace).post(self.submit_url, {}, format="json")

        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data["code"], "submission_locked")
        self.assertEqual(len(mail.outbox), after_first)
