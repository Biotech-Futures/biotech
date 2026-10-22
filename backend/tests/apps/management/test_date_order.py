"""The year's dates in order: registration opens before the challenge
starts, and submissions close after both the challenge start and
registration's close. Each save is checked both ways; an unset date is never
checked against."""
from datetime import datetime, timezone as dt_timezone

from django.test import TestCase
from rest_framework.test import APIClient

from apps.management.models import ChallengeStart
from apps.submissions.models import Deadline
from apps.submissions.services import current_cohort
from apps.users.models import RegistrationWindow, User

CHALLENGE = "/api/v1/management/challenge-start/"
DEADLINE = "/api/v1/management/deadline/"
REGISTRATION = "/api/v1/registration-management/"


def at(month, day, hour=0):
    return datetime(2026, month, day, hour, tzinfo=dt_timezone.utc)


class DateOrderTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="staff@example.test", first_name="Staff", last_name="Member", is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        # This year's dates: registration 1 Feb to 1 Mar, the deadline 1 Oct.
        Deadline.objects.create(closes_at=at(10, 1), grace_hours=0, is_active=True)
        self.year = current_cohort()
        self.window, _ = RegistrationWindow.objects.update_or_create(
            year=self.year, defaults={"opens_at": at(2, 1), "closes_at": at(3, 1)},
        )

    def put_start(self, when):
        return self.client.put(CHALLENGE, {"starts_at": when.isoformat() if when else None}, format="json")

    def post_deadline(self, when):
        return self.client.post(DEADLINE, {"closes_at": when.isoformat(), "grace_hours": 0}, format="json")

    def post_window(self, **dates):
        payload = {"action": "window", **{key: value.isoformat() for key, value in dates.items()}}
        return self.client.post(REGISTRATION, payload, format="json")

    def test_the_challenge_starts_after_registration_opens_and_before_the_deadline(self):
        for too_early in (at(1, 15), at(2, 1)):
            response = self.put_start(too_early)
            self.assertEqual(response.status_code, 400)
            self.assertIn("Challenge Start must be later than Registration Opens (01/02/2026 at 00:00).", str(response.json()))
        response = self.put_start(at(10, 1))
        self.assertEqual(response.status_code, 400)
        self.assertIn("earlier than the Submission Deadline (01/10/2026 at 00:00)", str(response.json()))
        self.assertEqual(self.put_start(at(4, 1)).status_code, 200)
        # Clearing it is always fine.
        self.assertEqual(self.put_start(None).status_code, 200)

    def test_the_deadline_is_after_the_challenge_start_and_registration_closing(self):
        ChallengeStart.objects.update_or_create(year=self.year, defaults={"starts_at": at(4, 1)})
        response = self.post_deadline(at(4, 1))
        self.assertEqual(response.status_code, 400)
        self.assertIn("must be later than Challenge Start (01/04/2026 at 00:00)", str(response.json()))
        # With no challenge start, registration's close still counts.
        ChallengeStart.objects.filter(year=self.year).update(starts_at=None)
        response = self.post_deadline(at(2, 20))
        self.assertEqual(response.status_code, 400)
        self.assertIn("must be later than Registration Closes (01/03/2026 at 00:00)", str(response.json()))
        self.assertEqual(self.post_deadline(at(9, 1)).status_code, 200)

    def test_registration_opens_before_the_challenge_and_closes_before_the_deadline(self):
        ChallengeStart.objects.update_or_create(year=self.year, defaults={"starts_at": at(4, 1)})
        response = self.post_window(opens_at=at(4, 2), closes_at=at(5, 1))
        self.assertEqual(response.status_code, 400)
        self.assertIn("Registration Opens must be earlier than Challenge Start (01/04/2026 at 00:00).", str(response.json()))
        response = self.post_window(closes_at=at(10, 2))
        self.assertEqual(response.status_code, 400)
        self.assertIn("Registration Closes must be earlier than the Submission Deadline (01/10/2026 at 00:00).", str(response.json()))
        self.assertEqual(self.post_window(opens_at=at(1, 1), closes_at=at(9, 1)).status_code, 200)

    def test_dates_not_set_are_not_checked_against(self):
        Deadline.objects.all().delete()
        RegistrationWindow.objects.filter(pk=self.window.pk).update(opens_at=None, closes_at=None)
        self.assertEqual(self.put_start(at(1, 1)).status_code, 200)
        ChallengeStart.objects.filter(year=self.year).update(starts_at=None)
        self.assertEqual(self.post_window(opens_at=at(6, 1), closes_at=at(7, 1)).status_code, 200)
