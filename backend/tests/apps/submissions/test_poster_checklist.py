"""Tests for the poster checklist a team confirms before submitting."""
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
from apps.submissions.checklist import CHECKLIST_ITEMS
from apps.submissions.models import Deadline, Submission
from apps.users.models import User

from .seed_data import CONFIRMED_CHECKLIST, install_question_set
from .test_poster_checks import A2, US_LETTER, _build_pdf, _mm


def _poster(width=A2[0], height=A2[1], text="BTF7 supervisor@school.edu.au"):
    return SimpleUploadedFile("poster.pdf", _build_pdf(width, height, text=text), content_type="application/pdf")


@override_settings(USE_AZURE_BLOB_STORAGE=False, AUTH_EMAIL_DISPATCH_SYNC=True, SUBMISSION_POSTER_CHECKS_ENABLED=True)
class ChecklistTestCase(TestCase):
    """A team of one with an open round; shared with the admin access tests."""

    def setUp(self):
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)
        role = Roles.objects.create(role_name="student")
        self.group = Groups.objects.create(group_name="BTF7", year=2025)
        self.student = User.objects.create_user(email="s@test.local", password="x", first_name="Sam")
        RoleAssignmentHistory.objects.create(user=self.student, role=role, valid_from=timezone.now(), valid_to=None)
        GroupMembership.objects.create(group=self.group, user=self.student, membership_role="student")
        self.deadline = Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)
        self.questions = install_question_set()

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _url(self, name, **kwargs):
        return reverse(name, kwargs={"group_id": self.group.id, **kwargs})

    def _upload(self, user, poster):
        return self._client(user).post(self._url("group-submission-file", slot="poster"), {"file": poster}, format="multipart")

    def _fill(self, user):
        self._client(user).put(self._url("group-submission"), {
            "project_title": "Our Project",
            "answers": {q.key: "An answer." for q in self.questions},
        }, format="json")

    def _entry(self):
        return Submission.objects.get(group=self.group)


class PosterChecklistTests(ChecklistTestCase):
    def test_an_a2_poster_ticks_what_the_checks_can_find(self):
        self._upload(self.student, _poster())

        self.assertEqual(self._entry().poster_checklist, {
            "supervisor_email": True, "btf_logo": False, "school_logo": False, "team_code": True, "page_size": True,
        })

    def test_another_a_series_size_leaves_page_size_for_the_team_to_confirm(self):
        response = self._upload(self.student, _poster(*_mm(594, 841)))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._entry().poster_checklist["page_size"])
        codes = {warning["code"] for warning in self._entry().poster_checks["warnings"]}
        self.assertIn("a2_size", codes)

    def test_a_page_outside_the_a_series_is_refused(self):
        self.assertEqual(self._upload(self.student, _poster(*US_LETTER)).status_code, 400)

    def test_the_teams_ticks_stand_whatever_was_detected(self):
        self._upload(self.student, _poster(*_mm(594, 841)))
        client = self._client(self.student)

        client.put(self._url("group-submission"), {"poster_checklist": {"page_size": True, "team_code": False}}, format="json")

        checklist = self._entry().poster_checklist
        self.assertTrue(checklist["page_size"])
        self.assertFalse(checklist["team_code"])

    def test_a_tick_tells_teammates_open_pages(self):
        self._upload(self.student, _poster(*A2))
        client = self._client(self.student)

        with patch("apps.submissions.views.notify_changed") as notify:
            client.put(self._url("group-submission"), {"poster_checklist": {"btf_logo": True}}, format="json")

        notify.assert_called_once_with("submission", self.group.id, "checklist", by=self.student)

    def test_an_unknown_checklist_item_is_refused(self):
        response = self._client(self.student).put(
            self._url("group-submission"), {"poster_checklist": {"colour": True}}, format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_submit_waits_for_the_whole_checklist(self):
        self._upload(self.student, _poster())
        self._fill(self.student)
        client = self._client(self.student)

        refused = client.post(self._url("group-submission-submit"), {}, format="json")
        client.put(self._url("group-submission"), {"poster_checklist": CONFIRMED_CHECKLIST}, format="json")
        accepted = client.post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(refused.status_code, 400)
        self.assertEqual(refused.data["code"], "poster_checklist_incomplete")
        self.assertEqual(accepted.status_code, 200)

    def test_a_new_poster_starts_a_fresh_checklist(self):
        self._upload(self.student, _poster())
        self._client(self.student).put(self._url("group-submission"), {"poster_checklist": CONFIRMED_CHECKLIST}, format="json")

        self._upload(self.student, _poster(text="no code here"))

        checklist = self._entry().poster_checklist
        self.assertFalse(checklist["school_logo"])
        self.assertFalse(checklist["team_code"])

    def test_removing_the_poster_clears_its_checklist(self):
        self._upload(self.student, _poster())

        self._client(self.student).delete(self._url("group-submission-file", slot="poster"))

        self.assertEqual(self._entry().poster_checklist, {item: False for item in CHECKLIST_ITEMS})
