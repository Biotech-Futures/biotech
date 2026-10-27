"""Integration tests: the ``?mode=`` query parameter on both match endpoints.

These run the whole stack - DRF view, service, algorithm - because that is
where the coercion used to disagree with itself:

* the mentor view built its own ``(raw_mode if raw_mode in ...)`` tuple,
* the student view went through a helper in ``match_student``'s module, and
* the algorithms each had their own idea of the valid values.

All three now call ``apps.common.matching_modes.resolve_match_mode``, so these
tests pin the observable contract at the edge: every documented mode runs, an
unrecognised one returns exactly the payload ``balanced`` would (not coverage,
which is what the mentor algorithm would otherwise fall through to), and the
mode recorded on the run is the resolved one.

Requires the fixtures to make each mode *behave* differently, so the payload
comparisons are meaningful rather than vacuous.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.matching_modes import MATCHING_MODES
from apps.groups.models import Countries, GroupMembership, Groups
from apps.matching_runtime.models import MatchRun
from apps.users.models import (
    AdminScope,
    AreasOfInterest,
    MentorProfile,
    StudentProfile,
    UserInterest,
)


def _create_student(country, timezone_name, *, first_name, year_level="10", interests=()):
    user = get_user_model().objects.create_user(
        email=f"{first_name.lower()}@modes.test",
        password="pass1234",
        first_name=first_name,
        last_name="Mode",
        country=country,
        timezone=timezone_name,
    )
    StudentProfile.objects.create(
        user=user,
        pg_first_name="Parent",
        pg_last_name="Mode",
        school_name="School",
        year_lvl=year_level,
    )
    for interest_name in interests:
        interest = AreasOfInterest.objects.get_or_create(interest_desc=interest_name)[0]
        UserInterest.objects.create(user=user, interest=interest)
    return user


class StudentMatchEndpointModeTests(TestCase):
    """GET /match/student/?mode= - student side of the shared contract."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = get_user_model().objects.create_user(
            email="admin@modes.test",
            password="pass1234",
            is_staff=True,
        )
        AdminScope.objects.create(user=self.admin_user)
        self.client.force_authenticate(user=self.admin_user)

        australia = Countries.objects.create(country_name="Australia")
        canada = Countries.objects.create(country_name="Canada")

        # Since MA3 the matcher only ever forms new groups, so the country gate
        # has to show up in formation rather than in a join. One student per
        # country means neither has a same-country peer to pair with, which
        # leaves them both to the cross-country pass: balanced pairs them up,
        # strict refuses and leaves both unmatched.
        self.local = _create_student(
            australia, "Australia/Sydney", first_name="Member", interests=("Genomics",)
        )
        # Shares the local student's interest: formation enforces mandatory
        # interest matching, which would otherwise keep this student out in
        # every mode and hide the country gate the strict assertion checks.
        self.candidate = _create_student(
            canada, "America/Toronto", first_name="Candidate", interests=("Genomics",)
        )

        self.url = reverse("admin_api:match-student")

    def _get(self, mode=None):
        query = {} if mode is None else {"mode": mode}
        response = self.client.get(self.url, query)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    @staticmethod
    def _recommended_student_ids(payload):
        return {
            str(entry["student"]["id"])
            for group in payload["data"]["recommendations"]
            for entry in group["recommendStudents"]
        }

    @staticmethod
    def _unmatched_student_ids(payload):
        return {
            str(entry["student"]["id"])
            for entry in payload["data"]["unmatched_students"]
        }

    @staticmethod
    def _latest_student_run_snapshot():
        run = MatchRun.objects.filter(run_type="student-match").order_by("-id").first()
        return run.rules_snapshot

    def test_every_documented_mode_returns_ok_with_the_expected_shape(self):
        for mode in MATCHING_MODES:
            with self.subTest(mode=mode):
                payload = self._get(mode)
                self.assertEqual(
                    payload["msg"], "Match retrieved successfully"
                )
                self.assertEqual(
                    set(payload["data"]),
                    {"recommendations", "unmatched_students", "not_full_groups"},
                )

    def test_balanced_recommends_across_the_border(self):
        payload = self._get("balanced")

        self.assertIn(str(self.candidate.id), self._recommended_student_ids(payload))
        self.assertNotIn(str(self.candidate.id), self._unmatched_student_ids(payload))

    def test_strict_leaves_the_cross_country_candidate_unmatched(self):
        payload = self._get("strict")

        self.assertIn(str(self.candidate.id), self._unmatched_student_ids(payload))
        self.assertNotIn(str(self.candidate.id), self._recommended_student_ids(payload))

    def test_unknown_mode_returns_exactly_the_balanced_payload(self):
        balanced = self._get("balanced")

        self.assertEqual(self._get("not-a-real-mode"), balanced)

    def test_missing_mode_defaults_to_the_balanced_payload(self):
        balanced = self._get("balanced")

        self.assertEqual(self._get(), balanced)

    def test_snapshot_records_the_resolved_mode_not_the_raw_query_value(self):
        self._get("not-a-real-mode")
        self.assertEqual(self._latest_student_run_snapshot()["mode"], "balanced")

        self._get("strict")
        self.assertEqual(self._latest_student_run_snapshot()["mode"], "strict")


class MentorMatchEndpointModeTests(TestCase):
    """GET /mentor-match/recommend/?mode= - mentor side of the shared contract."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = get_user_model().objects.create_user(
            email="admin@mentor-modes.test",
            password="pass1234",
            is_staff=True,
        )
        AdminScope.objects.create(user=self.admin_user)
        self.client.force_authenticate(user=self.admin_user)

        australia = Countries.objects.create(country_name="Australia")
        Countries.objects.create(country_name="India")

        # Group shares its country with home_mentor but its interests with
        # far_mentor, so balanced picks far while strict and coverage pick
        # home - the divergence the unknown-mode assertions rely on.
        self.group = Groups.objects.create(group_name="NSW Bio")
        member = _create_student(
            australia, "Australia/Sydney", first_name="Member", interests=("Genomics",)
        )
        GroupMembership.objects.create(
            group=self.group, user=member, membership_role="student"
        )

        self.home_mentor = self._create_mentor(
            email="home@mentor-modes.test",
            first_name="Home",
            country=australia,
            timezone_name="Australia/Sydney",
        )
        self.far_mentor = self._create_mentor(
            email="far@mentor-modes.test",
            first_name="Far",
            country=Countries.objects.get(country_name="India"),
            timezone_name="Asia/Kolkata",
            interests=("Genomics",),
        )

        self.url = reverse("admin_api:mentor-match-recommend")

    @staticmethod
    def _create_mentor(*, email, first_name, country, timezone_name, interests=()):
        user = get_user_model().objects.create_user(
            email=email,
            password="pass1234",
            first_name=first_name,
            last_name="Mode",
            country=country,
            timezone=timezone_name,
        )
        MentorProfile.objects.create(
            user=user,
            institution="Uni",
            mentor_reason="Support",
            max_group_count=1,
        )
        for interest_name in interests:
            interest = AreasOfInterest.objects.get_or_create(interest_desc=interest_name)[0]
            UserInterest.objects.create(user=user, interest=interest)
        return user

    def _get(self, mode=None):
        query = {} if mode is None else {"mode": mode}
        response = self.client.get(self.url, query)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    @staticmethod
    def _recommended_mentor_ids(payload):
        return [
            entry["recommendedMentor"]["mentorId"]
            if entry["recommendedMentor"]
            else None
            for entry in payload["data"]
        ]

    @staticmethod
    def _latest_mentor_run():
        return MatchRun.objects.filter(run_type="mentor-match").order_by("-id").first()

    def test_every_documented_mode_returns_ok_with_the_expected_shape(self):
        for mode in MATCHING_MODES:
            with self.subTest(mode=mode):
                payload = self._get(mode)
                self.assertEqual(
                    payload["msg"],
                    "Mentor recommendations retrieved successfully",
                )
                self.assertIsInstance(payload["data"], list)
                for entry in payload["data"]:
                    self.assertEqual(
                        set(entry),
                        {"group", "recommendedMentor", "reason", "score", "scoreBreakdown"},
                    )

    def test_fixture_diverges_across_the_three_modes(self):
        self.assertEqual(
            self._recommended_mentor_ids(self._get("balanced")), [self.far_mentor.id]
        )
        self.assertEqual(
            self._recommended_mentor_ids(self._get("strict")), [self.home_mentor.id]
        )
        self.assertEqual(
            self._recommended_mentor_ids(self._get("coverage")), [self.home_mentor.id]
        )

    def test_unknown_mode_returns_exactly_the_balanced_payload(self):
        balanced = self._get("balanced")

        self.assertEqual(self._get("not-a-real-mode"), balanced)
        self.assertNotEqual(self._get("not-a-real-mode"), self._get("coverage"))

    def test_missing_mode_defaults_to_the_balanced_payload(self):
        balanced = self._get("balanced")

        self.assertEqual(self._get(), balanced)

    def test_a_mentor_run_is_recorded(self):
        self._get("balanced")

        run = self._latest_mentor_run()
        self.assertIsNotNone(run)
        self.assertEqual(run.initiated_by_user_id, self.admin_user.id)
