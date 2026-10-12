"""Tests for admins acting on a team's behalf: any time, without the template checks or checklist."""
from datetime import timedelta

from django.utils import timezone

from apps.users.models import AdminScope, User

from .test_poster_checklist import ChecklistTestCase, _poster
from .test_poster_checks import US_LETTER


class AdminAccessTests(ChecklistTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(email="admin@test.local", password="x", first_name="Ada")
        AdminScope.objects.create(user=self.admin)

    def _close(self):
        self.deadline.closes_at = timezone.now() - timedelta(days=1)
        self.deadline.save()

    def test_an_admin_works_on_a_teams_entry_after_the_deadline(self):
        self._close()
        admin = self._client(self.admin)

        self.assertEqual(self._upload(self.student, _poster()).status_code, 403)
        self.assertEqual(self._upload(self.admin, _poster()).status_code, 200)
        self._fill(self.admin)
        response = admin.post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(response.status_code, 200)
        entry = self._entry()
        self.assertTrue(entry.is_submitted)
        self.assertTrue(entry.is_late)
        self.assertEqual(response.data["submission"]["submitted_by_name"], "BIOTech Futures")

    def test_an_admin_skips_the_template_checks_and_checklist(self):
        response = self._upload(self.admin, _poster(*US_LETTER, text="nothing"))
        self._fill(self.admin)

        submitted = self._client(self.admin).post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(submitted.status_code, 200)

    def test_an_admin_still_cannot_submit_an_incomplete_entry(self):
        self._upload(self.admin, _poster())

        response = self._client(self.admin).post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(response.status_code, 400)

    def test_an_admin_submission_belongs_to_the_groups_own_year(self):
        self._upload(self.admin, _poster())
        self._fill(self.admin)

        self._client(self.admin).post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(self._entry().cohort, 2025)

    def test_an_admin_can_reopen_after_the_deadline(self):
        self._upload(self.admin, _poster())
        self._fill(self.admin)
        admin = self._client(self.admin)
        admin.post(self._url("group-submission-submit"), {}, format="json")
        self._close()

        self.assertEqual(admin.post(self._url("group-submission-reopen"), {}, format="json").status_code, 200)
        self.assertFalse(self._entry().is_locked)

    def test_the_page_is_told_who_acts_for_teams(self):
        self.assertTrue(self._client(self.admin).get(self._url("group-submission")).data["admin_access"])
        self.assertFalse(self._client(self.student).get(self._url("group-submission")).data["admin_access"])
