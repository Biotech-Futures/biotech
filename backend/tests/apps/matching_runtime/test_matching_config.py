"""Tests for MA1: the admin-tunable matching weights and their API."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.admin.algorithms.student import ScoringWeights, build_groups
from apps.common.matching_weights import (
    DEFAULT_WEIGHT_VALUES,
    REQUIRED_WEIGHT_TOTAL,
)
from apps.matching_runtime.models import MatchingConfig
from apps.matching_runtime.serializers import MatchingConfigSerializer
from apps.matching_runtime.services import (
    build_scoring_rules_snapshot,
    matching_config_defaults,
    resolve_scoring_rules,
    resolve_scoring_weights,
)

VALID_WEIGHTS = {
    "year_weight": "30.00",
    "timezone_weight": "20.00",
    "timezone_max_weight": "20.00",
    "size_bonus_weight": "30.00",
}


def create_config(**overrides):
    return MatchingConfig.objects.create(
        **{**VALID_WEIGHTS, **overrides}
    )


class MatchingConfigModelTests(TestCase):
    def test_config_is_named_in_its_admin_list(self):
        self.assertEqual(str(create_config(name="Student v2")), "Student v2")

    def test_weights_must_total_exactly_one_hundred_percent(self):
        config = MatchingConfig(name="Too low", **{**VALID_WEIGHTS, "year_weight": "20.00"})

        with self.assertRaises(ValidationError) as raised:
            config.full_clean()

        self.assertIn("weight_total", raised.exception.message_dict)

    def test_weight_total_error_reports_the_shortfall(self):
        config = MatchingConfig(name="Over", **{**VALID_WEIGHTS, "year_weight": "40.00"})

        error = config.weight_total_error()

        self.assertIn(REQUIRED_WEIGHT_TOTAL, error)
        self.assertIn("10.00% over", error)

    def test_valid_weights_pass_clean_and_report_no_error(self):
        config = MatchingConfig(name="Valid", **VALID_WEIGHTS)

        config.full_clean()

        self.assertIsNone(config.weight_total_error())
        self.assertEqual(config.total_weight, Decimal("100.00"))

    def test_config_converts_to_scoring_weights(self):
        config = create_config()

        weights = config.to_scoring_weights()

        self.assertEqual(
            weights,
            ScoringWeights(
                year_weight=30.0,
                timezone_weight=20.0,
                timezone_max_penalty=20.0,
                size_bonus_weight=30.0,
            ),
        )

    def test_activating_a_config_retires_the_previous_one(self):
        first = create_config(name="First")
        second = create_config(name="Second")

        second.activate()

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)
        self.assertEqual(MatchingConfig.get_active(), second)

    def test_resolve_scoring_rules_falls_back_to_defaults_without_a_config(self):
        rules = resolve_scoring_rules()

        self.assertIsNone(rules.config)
        self.assertEqual(rules.weights, ScoringWeights())
        self.assertEqual(rules.weights.total(), 34.0)

    def test_resolve_scoring_rules_reads_the_active_config(self):
        config = create_config()

        rules = resolve_scoring_rules()

        self.assertEqual(rules.config, config)
        self.assertEqual(rules.weights.year_weight, 30.0)
        self.assertEqual(resolve_scoring_weights().size_bonus_weight, 30.0)

    def test_snapshot_records_the_weights_actually_applied(self):
        config = create_config()
        rules = resolve_scoring_rules()

        snapshot = build_scoring_rules_snapshot("coverage", rules)

        self.assertEqual(snapshot["mode"], "coverage")
        self.assertEqual(snapshot["configId"], config.id)
        self.assertEqual(snapshot["configName"], config.name)
        self.assertEqual(snapshot["totalWeight"], "100.0")
        self.assertEqual(snapshot["weights"]["yearWeight"], 30.0)
        self.assertEqual(snapshot["weights"]["timezoneWeight"], 20.0)
        self.assertEqual(snapshot["weights"]["sizeBonusWeight"], 30.0)

    def test_snapshot_is_json_serialisable_for_match_run(self):
        import json

        rules = resolve_scoring_rules()

        json.dumps(build_scoring_rules_snapshot("balanced", rules))

    def test_shipped_defaults_are_a_valid_split(self):
        defaults = matching_config_defaults()

        self.assertEqual(defaults["requiredTotal"], REQUIRED_WEIGHT_TOTAL)
        self.assertEqual(sum(defaults["defaults"].values()), 100.0)
        self.assertEqual(defaults["defaults"], DEFAULT_WEIGHT_VALUES)

    def test_shipped_defaults_can_be_saved_as_a_config(self):
        defaults = matching_config_defaults()["defaults"]

        config = MatchingConfig(name="Shipped", **{key: str(value) for key, value in defaults.items()})
        config.full_clean()

        config.save()
        self.assertEqual(config.total_weight, Decimal("100.00"))


class MatchingConfigSerializerTests(TestCase):
    def test_serializer_rejects_weights_that_do_not_total_one_hundred(self):
        serializer = MatchingConfigSerializer(
            data={"name": "Bad", **{**VALID_WEIGHTS, "size_bonus_weight": "40.00"}}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("weight_total", serializer.errors)

    def test_patch_is_validated_against_the_stored_weights(self):
        config = create_config()
        serializer = MatchingConfigSerializer(
            config,
            data={"year_weight": "50.00"},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("weight_total", serializer.errors)

    def test_patch_that_keeps_the_total_valid_is_accepted(self):
        config = create_config()
        serializer = MatchingConfigSerializer(
            config,
            data={"year_weight": "40.00", "timezone_weight": "10.00"},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        config.refresh_from_db()
        self.assertEqual(config.total_weight, Decimal("100.00"))

    def test_total_weight_is_exposed_for_the_admin_panel(self):
        serializer = MatchingConfigSerializer(create_config())

        self.assertEqual(str(serializer.data["total_weight"]), "100.00")


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
            {"name": "Student v2", **VALID_WEIGHTS},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        config = MatchingConfig.objects.get(name="Student v2")
        self.assertTrue(config.is_active)
        self.assertEqual(config.updated_by, self.admin)

    def test_non_staff_cannot_manage_configs(self):
        self.client.force_authenticate(
            get_user_model().objects.create_user(email="student@matching.test", password="pass")
        )

        response = self.client.post(
            "/matching/configs/",
            {"name": "Nope", **VALID_WEIGHTS},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_total_is_rejected_with_the_field_error(self):
        response = self.client.post(
            "/matching/configs/",
            {"name": "Bad", **{**VALID_WEIGHTS, "year_weight": "10.00"}},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("weight_total", response.json()["fields"])
        self.assertEqual(MatchingConfig.objects.count(), 0)

    def test_patch_updates_the_config_and_keeps_the_total_valid(self):
        create_config(name="Current")

        response = self.client.patch(
            "/matching/configs/1/",
            {"year_weight": "40.00", "timezone_weight": "10.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        config = MatchingConfig.objects.get(name="Current")
        self.assertEqual(config.year_weight, Decimal("40.00"))
        self.assertEqual(config.total_weight, Decimal("100.00"))

    def test_patch_that_breaks_the_total_is_rejected(self):
        create_config(name="Current")

        response = self.client.patch(
            "/matching/configs/1/",
            {"year_weight": "50.00"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("weight_total", response.json()["fields"])
        self.assertEqual(MatchingConfig.objects.get(name="Current").year_weight, Decimal("30.00"))

    def test_delete_removes_the_config(self):
        create_config(name="Doomed")

        response = self.client.delete("/matching/configs/1/")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(MatchingConfig.objects.count(), 0)

    def test_creating_a_config_retires_the_previous_active_one(self):
        create_config(name="First")

        self.client.post(
            "/matching/configs/",
            {"name": "Second", **VALID_WEIGHTS},
            format="json",
        )

        self.assertFalse(MatchingConfig.objects.get(name="First").is_active)
        self.assertTrue(MatchingConfig.objects.get(name="Second").is_active)

    def test_active_endpoint_returns_the_config_actually_in_use(self):
        config = create_config(name="Current")

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

    def test_defaults_endpoint_returns_a_valid_split(self):
        response = self.client.get("/matching/configs/defaults/")

        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertEqual(body["requiredTotal"], REQUIRED_WEIGHT_TOTAL)
        self.assertEqual(sum(body["defaults"].values()), 100.0)

    def test_stored_weights_reach_the_algorithm(self):
        self.client.post(
            "/matching/configs/",
            {
                "name": "Heavy year",
                "year_weight": "40.00",
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