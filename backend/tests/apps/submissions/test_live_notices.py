"""Tests that entry changes tell teammates' open pages to refresh."""
from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.storage import reset_managed_storage_caches
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import Deadline, Submission
from apps.users.models import User

from .seed_data import install_question_set


@override_settings(USE_AZURE_BLOB_STORAGE=False, AUTH_EMAIL_DISPATCH_SYNC=True)
class LiveNoticeTests(TestCase):
    def setUp(self):
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)
        role = Roles.objects.create(role_name="student")
        self.group = Groups.objects.create(group_name="BTF-NOTICE")
        self.student = User.objects.create_user(
            email="notice@test.local", password="testUser@123", first_name="Amy", last_name="Lee",
        )
        RoleAssignmentHistory.objects.create(user=self.student, role=role, valid_from=timezone.now(), valid_to=None)
        GroupMembership.objects.create(group=self.group, user=self.student, membership_role="student")
        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)
        self.questions = install_question_set()
        self.client = APIClient()
        self.client.force_authenticate(user=self.student)

    def _url(self, name, **kwargs):
        return reverse(name, kwargs={"group_id": self.group.id, **kwargs})

    def _notices(self, notify):
        return [(call.args[0], call.args[1], call.args[2], call.kwargs["by"]) for call in notify.call_args_list]

    def test_submitting_and_reopening_tell_the_team(self):
        submission, _ = Submission.objects.get_or_create(group=self.group)
        submission.project_title = "Our Project"
        submission.answers = {q.key: "An answer." for q in self.questions}
        submission.poster = {"storage_key": "n/poster.pdf", "name": "poster.pdf", "mime": "application/pdf", "size": 10}
        submission.save()

        with patch("apps.submissions.views.notify_changed") as notify:
            self.assertEqual(self.client.post(self._url("group-submission-submit"), {}, format="json").status_code, 200)
            self.assertEqual(self.client.post(self._url("group-submission-reopen"), {}, format="json").status_code, 200)

        self.assertEqual(self._notices(notify), [
            ("submission", self.group.id, "submitted", self.student),
            ("submission", self.group.id, "reopened", self.student),
        ])

    def test_adding_and_removing_a_file_tell_the_team(self):
        url = self._url("group-submission-file", slot="prototype")
        with patch("apps.submissions.views.notify_changed") as notify:
            upload = SimpleUploadedFile("model.zip", b"PK\x03\x04zip", content_type="application/zip")
            self.assertEqual(self.client.post(url, {"file": upload}, format="multipart").status_code, 200)
            self.assertEqual(self.client.delete(url).status_code, 200)

        self.assertEqual([notice[2] for notice in self._notices(notify)], ["files", "files"])

    def test_a_refused_action_tells_nobody(self):
        with patch("apps.submissions.views.notify_changed") as notify:
            response = self.client.post(self._url("group-submission-submit"), {}, format="json")

        self.assertNotEqual(response.status_code, 200)
        notify.assert_not_called()
