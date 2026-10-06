"""MA1 end-to-end check: a student match run records the rules it was scored under."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.admin.services.match import match_student
from apps.groups.models import Countries
from apps.matching_runtime.models import MatchingConfig, MatchRun
from apps.users.models import AreasOfInterest, StudentProfile, UserInterest

WEIGHTS = {
    "year_weight": "30.00",
    "country_mismatch_weight": "20.00",
    "timezone_weight": "20.00",
    "timezone_max_weight": "10.00",
    "size_bonus_weight": "20.00",
}


class StudentMatchRunSnapshotTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            email="run-admin@matching.test",
            password="adminpass",
            is_staff=True,
        )
        self.country = Countries.objects.create(country_name="Australia")
        interest = AreasOfInterest.objects.create(interest_desc="Genomics")
        for index in range(3):
            user = get_user_model().objects.create_user(
                email=f"student{index}@matching.test",
                password="studentpass",
                first_name=f"Student{index}",
                last_name="Test",
                country=self.country,
                timezone="+10:00",
            )
            StudentProfile.objects.create(
                user=user,
                pg_first_name=f"Parent{index}",
                pg_last_name="Test",
                school_name="School",
                year_lvl="10",
            )
            UserInterest.objects.create(user=user, interest=interest)

    def test_snapshot_names_the_active_config_and_mode(self):
        config = MatchingConfig.objects.create(name="Student v2", **WEIGHTS)

        match_student(str(self.admin.id), mode="coverage")

        snapshot = MatchRun.objects.get(run_type="student-match").rules_snapshot
        self.assertEqual(snapshot["mode"], "coverage")
        self.assertEqual(snapshot["configId"], config.id)
        self.assertEqual(snapshot["configName"], "Student v2")
        self.assertEqual(snapshot["totalWeight"], "100.0")
        self.assertEqual(snapshot["weights"]["yearWeight"], 30.0)
        # The existing payload is preserved alongside the rules block.
        self.assertEqual(snapshot["strategy"], "hybrid-join-or-form")

    def test_snapshot_falls_back_to_the_builtin_weights(self):
        match_student(str(self.admin.id))

        snapshot = MatchRun.objects.get(run_type="student-match").rules_snapshot
        self.assertEqual(snapshot["mode"], "balanced")
        self.assertIsNone(snapshot["configId"])
        self.assertEqual(snapshot["weights"]["yearWeight"], 8.0)

    def _isolate_student_pair(self):
        """Leave one student out so the run must group the other two together."""
        UserInterest.objects.filter(user__email="student2@matching.test").delete()
        other_interest = AreasOfInterest.objects.create(interest_desc="Physics")
        student2 = get_user_model().objects.get(email="student2@matching.test")
        UserInterest.objects.create(user=student2, interest=other_interest)
        # Leave the remaining pair two year levels apart.
        StudentProfile.objects.filter(
            user__email="student1@matching.test"
        ).update(year_lvl="12")

    def test_configured_weights_change_the_scores_the_run_proposes(self):
        # A two-year gap at 60 points per year eats the whole 100-point base,
        # where the legacy constant would only have cost 16 points.
        self._isolate_student_pair()
        MatchingConfig.objects.create(
            name="Heavy year",
            year_weight="60.00",
            country_mismatch_weight="10.00",
            timezone_weight="10.00",
            timezone_max_weight="10.00",
            size_bonus_weight="10.00",
        )

        match_student(str(self.admin.id))
        snapshot = MatchRun.objects.get(run_type="student-match").rules_snapshot

        group = snapshot["finalForm"]["groups"][0]
        self.assertEqual(snapshot["weights"]["yearWeight"], 60.0)
        self.assertEqual(group["scoreBreakdown"]["yearPenalty"], 120.0)
        self.assertEqual(group["groupScore"], 0.0)

    def test_legacy_weights_are_used_when_no_config_exists(self):
        self._isolate_student_pair()

        match_student(str(self.admin.id))
        snapshot = MatchRun.objects.get(run_type="student-match").rules_snapshot

        group = snapshot["finalForm"]["groups"][0]
        self.assertEqual(snapshot["weights"]["yearWeight"], 8.0)
        self.assertEqual(group["scoreBreakdown"]["yearPenalty"], 16.0)
        self.assertEqual(group["groupScore"], 84.0)