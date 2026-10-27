"""Tests for MA1: the admin-tunable matching weights and their API."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.admin.algorithms.student import ScoringWeights, build_groups
from apps.common.matching_weights import (
    BASE_SCORE,
    DEFAULT_WEIGHT_VALUES,
    MAX_TOTAL_PENALTY,
)
from apps.matching_runtime.models import MatchingConfig
from apps.matching_runtime.serializers import MatchingConfigSerializer
from apps.matching_runtime.services import (
    build_scoring_rules_snapshot,
    matching_config_defaults,
    resolve_scoring_rules,
    resolve_scoring_weights,
)

# Raw points. The total (130) is deliberately not 100: nothing requires the
# weights to add up to anything. The two caps add up to 50, inside the ceiling.
VALID_WEIGHTS = {
    "year_weight": "30.00",
    "year_max_weight": "30.00",
    "timezone_weight": "20.00",
    "timezone_max_weight": "20.00",
    "size_bonus_weight": "30.00",
}


def create_config(**overrides):
    return MatchingConfig.objects.create(
        **{**VALID_WEIGHTS, **overrides}
    )


class MatchingConfigModelTests(TestCase):
    def test_config_identifies_itself_by_id_in_the_admin_list(self):
        config = create_config()
        self.assertEqual(str(config), f"Scoring config #{config.id}")

    def test_penalty_caps_may_not_exceed_the_base_score(self):
        # 90 + 20 = 110, so the worst pairing would lose more than the whole
        # base score and every bad match would score 0 alike.
        config = MatchingConfig(**{**VALID_WEIGHTS, "year_max_weight": "90.00"})

        with self.assertRaises(ValidationError) as raised:
            config.full_clean()

        self.assertIn("penalty_ceiling", raised.exception.message_dict)

    def test_penalty_ceiling_error_reports_the_overshoot(self):
        config = MatchingConfig(**{**VALID_WEIGHTS, "year_max_weight": "90.00"})

        error = config.penalty_ceiling_error()

        self.assertIn("lower a cap by at least 10.00", error)
        self.assertIn("110", error)
        self.assertIn("fall below 0", error)

    def test_weights_need_not_total_anything(self):
        # The old rule demanded exactly 100 across the weights. These total 397
        # and are perfectly valid: only the caps are bounded.
        config = MatchingConfig(
            year_weight="99.00",
            year_max_weight="80.00",
            timezone_weight="99.00",
            timezone_max_weight="20.00",
            size_bonus_weight="99.00",
        )

        config.full_clean()

        self.assertIsNone(config.penalty_ceiling_error())
        self.assertEqual(config.total_weight, Decimal("397.00"))

    def test_caps_exactly_at_the_ceiling_are_allowed(self):
        # At the ceiling the worst pairing scores exactly 0, which is still a
        # single well-defined floor rather than a flattened range.
        config = MatchingConfig(
            **{**VALID_WEIGHTS, "year_max_weight": "80.00", "timezone_max_weight": "20.00"}
        )

        config.full_clean()

        self.assertIsNone(config.penalty_ceiling_error())
        self.assertEqual(config.max_total_penalty, Decimal("100.00"))

    def test_valid_weights_pass_clean_and_report_no_error(self):
        config = MatchingConfig(**VALID_WEIGHTS)

        config.full_clean()

        self.assertIsNone(config.penalty_ceiling_error())
        self.assertEqual(config.total_weight, Decimal("130.00"))
        self.assertEqual(config.max_total_penalty, Decimal("50.00"))

    def test_config_converts_to_scoring_weights(self):
        config = create_config()

        weights = config.to_scoring_weights()

        self.assertEqual(
            weights,
            ScoringWeights(
                year_weight=30.0,
                year_max_penalty=30.0,
                timezone_weight=20.0,
                timezone_max_penalty=20.0,
                size_bonus_weight=30.0,
            ),
        )

    def test_saving_a_second_config_replaces_the_stored_one(self):
        first = create_config()
        second = create_config()

        self.assertEqual(MatchingConfig.objects.count(), 1)
        self.assertEqual(MatchingConfig.get_singleton(), second)
        self.assertNotEqual(first.pk, second.pk)

    def test_resolve_scoring_rules_falls_back_to_defaults_without_a_config(self):
        rules = resolve_scoring_rules()

        self.assertIsNone(rules.config)
        self.assertEqual(rules.weights, ScoringWeights())
        self.assertEqual(rules.weights.total(), 58.0)

    def test_resolve_scoring_rules_reads_the_stored_config(self):
        config = create_config()

        rules = resolve_scoring_rules()

        self.assertEqual(rules.config, config)
        self.assertEqual(rules.weights.year_weight, 30.0)
        self.assertEqual(resolve_scoring_weights().size_bonus_weight, 30.0)

    def test_snapshot_records_the_weights_actually_applied(self):
        create_config()
        rules = resolve_scoring_rules()

        snapshot = build_scoring_rules_snapshot("coverage", rules)

        self.assertEqual(snapshot["mode"], "coverage")
        self.assertNotIn("configId", snapshot)
        self.assertNotIn("configName", snapshot)
        self.assertEqual(snapshot["totalWeight"], "130.0")
        self.assertEqual(snapshot["maxTotalPenalty"], "50.0")
        self.assertEqual(snapshot["weights"]["yearWeight"], 30.0)
        self.assertEqual(snapshot["weights"]["yearMaxPenalty"], 30.0)
        self.assertEqual(snapshot["weights"]["timezoneWeight"], 20.0)
        self.assertEqual(snapshot["weights"]["sizeBonusWeight"], 30.0)

    def test_snapshot_is_json_serialisable_for_match_run(self):
        import json

        rules = resolve_scoring_rules()

        json.dumps(build_scoring_rules_snapshot("balanced", rules))

    def test_shipped_defaults_describe_the_limits_for_the_panel(self):
        defaults = matching_config_defaults()

        self.assertEqual(defaults["baseScore"], BASE_SCORE)
        self.assertEqual(defaults["maxTotalPenalty"], MAX_TOTAL_PENALTY)
        self.assertEqual(defaults["defaults"], DEFAULT_WEIGHT_VALUES)

    def test_shipped_defaults_can_be_saved_as_a_config(self):
        defaults = matching_config_defaults()["defaults"]

        config = MatchingConfig(**{key: str(value) for key, value in defaults.items()})
        config.full_clean()

        config.save()
        self.assertEqual(config.total_weight, Decimal("58.00"))
        self.assertEqual(config.max_total_penalty, Decimal("42.00"))


class MatchingConfigSerializerTests(TestCase):
    def test_serializer_rejects_caps_over_the_ceiling(self):
        serializer = MatchingConfigSerializer(
            data={**VALID_WEIGHTS, "timezone_max_weight": "80.00"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("penalty_ceiling", serializer.errors)

    def test_serializer_accepts_a_total_that_is_not_one_hundred(self):
        serializer = MatchingConfigSerializer(data=VALID_WEIGHTS)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.save().total_weight, Decimal("130.00"))

    def test_patch_is_validated_against_the_stored_caps(self):
        # Only the year cap is sent; it is judged against the stored timezone
        # cap of 20, which 90 pushes over the ceiling.
        config = create_config()
        serializer = MatchingConfigSerializer(
            config,
            data={"year_max_weight": "90.00"},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("penalty_ceiling", serializer.errors)

    def test_patch_within_the_ceiling_is_accepted(self):
        config = create_config()
        serializer = MatchingConfigSerializer(
            config,
            data={"year_weight": "40.00", "timezone_weight": "10.00"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        config.refresh_from_db()
        self.assertEqual(config.total_weight, Decimal("130.00"))

    def test_totals_are_exposed_for_the_admin_panel(self):
        serializer = MatchingConfigSerializer(create_config())

        self.assertEqual(str(serializer.data["total_weight"]), "130.00")
        self.assertEqual(str(serializer.data["max_total_penalty"]), "50.00")


class MatchingConfigApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = get_user_model().objects.create_user(
            email="config-admin@matching.test",
            password="adminpass",
            is_staff=True,
        )
        self.client.force_authenticate(self.admin)

    def test_admin_can_create_a_config(self):
        response = self.client.post(
            "/matching/configs/",
            VALID_WEIGHTS,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        config = MatchingConfig.objects.get()
        self.assertEqual(config.updated_by, self.admin)

    def test_non_staff_cannot_manage_configs(self):
        self.client.force_authenticate(
            get_user_model().objects.create_user(email="student@matching.test", password="pass")
        )

        response = self.client.post(
            "/matching/configs/",
            VALID_WEIGHTS,
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_caps_over_the_ceiling_are_rejected_with_the_field_error(self):
        response = self.client.post(
            "/matching/configs/",
            {**VALID_WEIGHTS, "year_max_weight": "90.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("penalty_ceiling", response.json()["fields"])
        self.assertEqual(MatchingConfig.objects.count(), 0)

    def test_patch_updates_the_config_without_touching_any_total(self):
        config = create_config()

        response = self.client.patch(
            f"/matching/configs/{config.id}/",
            {"year_weight": "40.00", "timezone_weight": "10.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        config.refresh_from_db()
        self.assertEqual(config.year_weight, Decimal("40.00"))
        self.assertEqual(config.total_weight, Decimal("130.00"))

    def test_patch_that_breaks_the_ceiling_is_rejected(self):
        config = create_config()

        response = self.client.patch(
            f"/matching/configs/{config.id}/",
            {"year_max_weight": "90.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("penalty_ceiling", response.json()["fields"])
        config.refresh_from_db()
        self.assertEqual(
            config.year_max_weight, Decimal("30.00")
        )

    def test_delete_removes_the_config(self):
        config = create_config()

        response = self.client.delete(f"/matching/configs/{config.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(MatchingConfig.objects.count(), 0)

    def test_creating_another_config_replaces_the_stored_one(self):
        create_config()

        self.client.post(
            "/matching/configs/",
            VALID_WEIGHTS,
            format="json",
        )

        self.assertEqual(MatchingConfig.objects.count(), 1)

    def test_active_endpoint_returns_the_config_actually_in_use(self):
        config = create_config()

        response = self.client.get("/matching/configs/active/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["id"], config.id)
        self.assertEqual(body["weights"]["yearWeight"], 30.0)

    def test_active_endpoint_falls_back_to_the_builtin_weights(self):
        response = self.client.get("/matching/configs/active/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["data"])
        self.assertEqual(body["weights"]["yearWeight"], 8.0)

    def test_defaults_endpoint_returns_the_limits_and_the_defaults(self):
        response = self.client.get("/matching/configs/defaults/")

        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertEqual(body["baseScore"], BASE_SCORE)
        self.assertEqual(body["maxTotalPenalty"], MAX_TOTAL_PENALTY)
        self.assertEqual(body["defaults"], DEFAULT_WEIGHT_VALUES)

    def test_stored_weights_reach_the_algorithm(self):
        self.client.post(
            "/matching/configs/",
            {
                "year_weight": "40.00",
                # Two years at 40 is 80, which this cap lets through in full.
                "year_max_weight": "80.00",
                "timezone_weight": "20.00",
                "timezone_max_weight": "15.00",
                "size_bonus_weight": "25.00",
            },
            format="json",
        )

        weights = resolve_scoring_weights()
        result = build_groups(
            [
                {"id": 1, "country": "Australia", "timezoneOffsetHours": 10, "yearLevel": 10, "interests": ["Genomics"]},
                {"id": 2, "country": "Australia", "timezoneOffsetHours": 10, "yearLevel": 12, "interests": ["Genomics"]},
            ],
            weights=weights,
        )

        self.assertEqual(result["groups"][0]["groupScore"], 20.0)