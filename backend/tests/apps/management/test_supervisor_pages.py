"""Management's Pages Visibility (on Challenge Start): the pages hidden until
the date and time set, and while none is; readable by anyone signed in,
changed by admins only."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.management.models import ChallengeStart
from apps.submissions.services import current_cohort
from apps.users.models import AdminScope, User

URL = "/api/v1/management/supervisor-pages/"


class PagesVisibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin-pages@test.com", password="pw12345!", first_name="Ada", last_name="Admin",
        )
        AdminScope.objects.create(user=self.admin)
        self.student = User.objects.create_user(email="student-pages@test.com", password="pw12345!")

    def put(self, shown_from):
        self.client.force_authenticate(self.admin)
        return self.client.put(URL, {"shown_from": shown_from}, format="json")

    def test_hidden_while_no_date_is_set(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(
            self.client.get(URL).json(),
            {"shown": False, "shown_from": None, "set_by": "", "updated_at": None, "challenge_starts_at": None},
        )

    def test_anyone_signed_in_reads_when_this_years_challenge_starts(self):
        starts = timezone.now() + timedelta(days=7)
        ChallengeStart.objects.create(year=current_cohort(), starts_at=starts)
        ChallengeStart.objects.create(year=current_cohort() - 1, starts_at=starts - timedelta(days=365))
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(URL).json()["challenge_starts_at"], starts.isoformat())

    def test_hidden_until_the_date_then_shown(self):
        later = timezone.now() + timedelta(days=2)
        response = self.put(later.isoformat())
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["shown"])
        self.assertEqual(response.json()["set_by"], "Ada Admin")

        earlier = timezone.now() - timedelta(minutes=1)
        self.put(earlier.isoformat())
        self.client.force_authenticate(self.student)
        body = self.client.get(URL).json()
        self.assertTrue(body["shown"])
        self.assertIsNotNone(body["shown_from"])

    def test_clearing_the_date_hides_them_again(self):
        self.put((timezone.now() - timedelta(days=1)).isoformat())
        body = self.put(None).json()
        self.assertEqual((body["shown"], body["shown_from"]), (False, None))

    def test_only_admins_change_it(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.put(URL, {"shown_from": None}, format="json").status_code, 403)

    def test_needs_a_date_and_time_or_null(self):
        self.assertEqual(self.put("next week").status_code, 400)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.put(URL, {}, format="json").status_code, 400)

    def test_needs_signing_in(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(URL).status_code, (401, 403))
