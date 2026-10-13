"""Tests for admins acting on a team's behalf: any time, without the template checks, but with the checklist."""
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from apps.submissions.storage import submission_file_service
from apps.users.models import AdminScope, User

from .seed_data import CONFIRMED_CHECKLIST
from .test_poster_checklist import ChecklistTestCase, _poster
from .test_poster_checks import US_LETTER


class AdminAccessTests(ChecklistTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(email="admin@test.local", password="x", first_name="Ada")
        AdminScope.objects.create(user=self.admin)

    def _tick(self, user):
        self._client(user).put(self._url("group-submission"), {"poster_checklist": CONFIRMED_CHECKLIST}, format="json")

    def _close(self):
        self.deadline.closes_at = timezone.now() - timedelta(days=1)
        self.deadline.save()

    def test_an_admin_works_on_a_teams_entry_after_the_deadline(self):
        self._close()
        admin = self._client(self.admin)

        self.assertEqual(self._upload(self.student, _poster()).status_code, 403)
        self.assertEqual(self._upload(self.admin, _poster()).status_code, 200)
        self._fill(self.admin)
        self._tick(self.admin)
        response = admin.post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(response.status_code, 200)
        entry = self._entry()
        self.assertTrue(entry.is_submitted)
        self.assertTrue(entry.is_late)
        self.assertEqual(response.data["submission"]["submitted_by_name"], "BIOTech Futures")

    def test_an_admin_skips_the_template_checks_but_confirms_the_checklist(self):
        response = self._upload(self.admin, _poster(*US_LETTER, text="nothing"))
        self._fill(self.admin)
        admin = self._client(self.admin)

        unticked = admin.post(self._url("group-submission-submit"), {}, format="json")
        self._tick(self.admin)
        ticked = admin.post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(unticked.data["code"], "poster_checklist_incomplete")
        self.assertEqual(ticked.status_code, 200)

    def test_an_admin_still_cannot_submit_an_incomplete_entry(self):
        self._upload(self.admin, _poster())

        response = self._client(self.admin).post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(response.status_code, 400)

    def test_an_admin_submission_belongs_to_the_groups_own_year(self):
        self._upload(self.admin, _poster())
        self._fill(self.admin)
        self._tick(self.admin)

        self._client(self.admin).post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(self._entry().cohort, 2025)

    def test_an_admin_can_reopen_after_the_deadline(self):
        self._upload(self.admin, _poster())
        self._fill(self.admin)
        self._tick(self.admin)
        admin = self._client(self.admin)
        admin.post(self._url("group-submission-submit"), {}, format="json")
        self._close()

        self.assertEqual(admin.post(self._url("group-submission-reopen"), {}, format="json").status_code, 200)
        self.assertFalse(self._entry().is_locked)

    def test_the_page_is_told_who_acts_for_teams(self):
        self.assertTrue(self._client(self.admin).get(self._url("group-submission")).data["admin_access"])
        self.assertFalse(self._client(self.student).get(self._url("group-submission")).data["admin_access"])

    def _submitted_by_team(self):
        self._upload(self.student, _poster())
        self._fill(self.student)
        client = self._client(self.student)
        client.put(self._url("group-submission"), {"poster_checklist": CONFIRMED_CHECKLIST}, format="json")
        client.post(self._url("group-submission-submit"), {}, format="json")
        return self._entry()

    def test_an_admin_edits_a_submitted_entry_without_reopening_it(self):
        entry = self._submitted_by_team()
        key = self.questions[0].key

        response = self._client(self.admin).put(
            self._url("group-submission"), {"answers": {key: "Corrected by the programme."}}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.assertTrue(entry.is_locked)
        self.assertEqual(entry.answers[key], "Corrected by the programme.")
        self.assertEqual(entry.submitted_answers[key], "An answer.")

    def test_the_team_still_cannot_edit_its_submitted_entry(self):
        self._submitted_by_team()

        response = self._client(self.student).put(
            self._url("group-submission"), {"project_title": "Changed"}, format="json"
        )

        self.assertEqual(response.status_code, 409)

    def test_an_admin_replaces_a_submitted_poster_and_resubmits_in_one_go(self):
        entry = self._submitted_by_team()
        old_key = entry.submitted_poster["storage_key"]

        self.assertEqual(self._upload(self.admin, _poster(*US_LETTER, text="new")).status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.submitted_poster["storage_key"], old_key)
        self.assertTrue(submission_file_service("poster").exists(old_key))
        self._tick(self.admin)

        response = self._client(self.admin).post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.assertNotEqual(entry.submitted_poster["storage_key"], old_key)
        self.assertFalse(submission_file_service("poster").exists(old_key))
        self.assertEqual(response.data["submission"]["submitted_by_name"], "BIOTech Futures")

    def test_an_admin_save_tells_the_teams_open_pages(self):
        with patch("apps.submissions.views.notify_changed") as notify:
            self._client(self.admin).put(self._url("group-submission"), {"project_title": "Fixed"}, format="json")

        notify.assert_called_once_with("submission", self.group.id, "draft", by=self.admin)
