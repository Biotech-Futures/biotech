from collections import Counter
from datetime import datetime, timedelta, timezone
import os
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from cli import _config_from_args, _parser
from dataset import (
    DATASET_VERSION,
    SCENARIO_ANALYTICS_COVERAGE,
    SCENARIO_UNIFORM,
    DatasetConfig,
    parse_as_of,
)
from generator import (
    ANALYTICS_EMAIL_ALERT_BURST_RANGE,
    _analytics_group_plan,
    _audience_role_name,
    _create_announcements,
    _create_deliveries,
    _delivery_started_at,
    _resource_index_for_access,
    _student_has_missing_guardian,
    _student_group_slots,
    _student_is_unassigned,
)
from safety import SAFETY_TOKEN, UnsafeDatabaseError, validate_config_values, validate_reset_database_name
from verification import LOGIN_ENTITY


class DatasetConfigTests(unittest.TestCase):
    def test_defaults_are_valid_and_deterministic(self):
        config = DatasetConfig().validate()
        self.assertEqual(DATASET_VERSION, 7)
        self.assertEqual(config.total_users, 158)
        self.assertEqual(config.resource_accesses, 1200)
        self.assertEqual(config.scenario, SCENARIO_ANALYTICS_COVERAGE)
        self.assertEqual(config.to_manifest()["scenario"], SCENARIO_ANALYTICS_COVERAGE)
        self.assertLess(abs((datetime.now(timezone.utc) - config.as_of_datetime).total_seconds()), 61)
        self.assertEqual(DatasetConfig.from_manifest(config.to_manifest()), config)

    def test_as_of_must_be_timezone_aware(self):
        with self.assertRaisesRegex(ValueError, "UTC offset"):
            parse_as_of("2026-09-01T00:00:00")

    def test_relational_count_dependencies_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "messages require"):
            DatasetConfig(groups=0, messages=1).validate()
        with self.assertRaisesRegex(ValueError, "deliveries require"):
            DatasetConfig(announcements=0, deliveries=1).validate()
        with self.assertRaisesRegex(ValueError, "unique event/user pairs"):
            DatasetConfig(events=1, rsvps=159).validate()
        with self.assertRaisesRegex(ValueError, "resource accesses require"):
            DatasetConfig(resources=0, resource_accesses=1).validate()

    def test_unknown_scenario_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "analytics_coverage, uniform"):
            DatasetConfig(scenario="unsupported").validate()

    def test_cli_accepts_the_versioned_scenario_option(self):
        args = _parser().parse_args(
            ["bootstrap", "--scenario", SCENARIO_UNIFORM, "--dry-run"]
        )
        self.assertEqual(_config_from_args(args).scenario, SCENARIO_UNIFORM)


class ScenarioDistributionTests(unittest.TestCase):
    def test_analytics_coverage_reserves_default_group_edge_states(self):
        self.assertEqual(
            _analytics_group_plan(DatasetConfig()),
            {"empty": 0, "mentorless": 1, "zero_messages": 2},
        )
        self.assertEqual(
            _analytics_group_plan(DatasetConfig(scenario=SCENARIO_UNIFORM)),
            {"empty": None, "mentorless": None, "zero_messages": None},
        )

    def test_group_plan_safely_degrades_for_small_counts(self):
        one_group = DatasetConfig(groups=1, messages=1)
        self.assertEqual(
            _analytics_group_plan(one_group),
            {"empty": None, "mentorless": 0, "zero_messages": None},
        )
        two_groups = DatasetConfig(groups=2, messages=1)
        self.assertEqual(
            _analytics_group_plan(two_groups),
            {"empty": 0, "mentorless": 1, "zero_messages": None},
        )
        no_messages = DatasetConfig(groups=1, messages=0)
        self.assertEqual(
            _analytics_group_plan(no_messages),
            {"empty": 0, "mentorless": None, "zero_messages": None},
        )
        one_student = DatasetConfig(
            admins=0,
            supervisors=0,
            mentors=0,
            students=1,
            groups=3,
            messages=1,
            login_events=0,
            tasks=0,
            resources=0,
            resource_accesses=0,
            announcements=0,
            deliveries=0,
            events=0,
            rsvps=0,
        ).validate()
        self.assertEqual(
            _analytics_group_plan(one_student),
            {"empty": 0, "mentorless": 1, "zero_messages": None},
        )
        mentor_and_student = DatasetConfig(
            admins=0,
            supervisors=0,
            mentors=1,
            students=1,
            groups=3,
            messages=1,
            login_events=0,
            tasks=0,
            resources=0,
            resource_accesses=0,
            announcements=0,
            deliveries=0,
            events=0,
            rsvps=0,
        ).validate()
        self.assertEqual(
            _analytics_group_plan(mentor_and_student),
            {"empty": 0, "mentorless": 1, "zero_messages": 2},
        )
        self.assertEqual(_student_group_slots(mentor_and_student), [1, 2])

    def test_resource_coverage_has_one_hotspot_and_a_zero_access_resource(self):
        config = DatasetConfig(resources=30, resource_accesses=1200)
        counts = Counter(
            _resource_index_for_access(config, sequence)
            for sequence in range(1, config.resource_accesses + 1)
        )
        self.assertEqual(counts[0], 600)
        self.assertEqual(counts[29], 0)
        self.assertEqual(sum(counts.values()), 1200)

        uniform = DatasetConfig(
            resources=30,
            resource_accesses=1200,
            scenario=SCENARIO_UNIFORM,
        )
        uniform_counts = Counter(
            _resource_index_for_access(uniform, sequence)
            for sequence in range(1, uniform.resource_accesses + 1)
        )
        self.assertEqual(set(uniform_counts.values()), {40})

    def test_attention_coverage_reserves_registration_and_group_follow_up_rows(self):
        coverage = DatasetConfig()
        uniform = DatasetConfig(scenario=SCENARIO_UNIFORM)

        self.assertFalse(_student_has_missing_guardian(coverage, 9))
        self.assertTrue(_student_has_missing_guardian(coverage, 10))
        self.assertFalse(_student_is_unassigned(coverage, 11))
        self.assertTrue(_student_is_unassigned(coverage, 12))
        self.assertFalse(_student_has_missing_guardian(uniform, 10))
        self.assertFalse(_student_is_unassigned(uniform, 12))

    def test_resource_coverage_safely_degrades_for_one_or_two_resources(self):
        one = DatasetConfig(resources=1, resource_accesses=5)
        two = DatasetConfig(resources=2, resource_accesses=5)
        self.assertEqual(
            {_resource_index_for_access(one, sequence) for sequence in range(1, 6)},
            {0},
        )
        self.assertEqual(
            {_resource_index_for_access(two, sequence) for sequence in range(1, 6)},
            {0},
        )

    def test_delivery_boundary_rows_and_role_audiences_are_deterministic(self):
        config = DatasetConfig()
        published_at = config.as_of_datetime - timedelta(days=10)
        starts = {
            index: _delivery_started_at(config, index, published_at)
            for index in range(1, config.deliveries + 1)
        }
        self.assertEqual(
            {index: starts[index] for index in (1, 2, 3, 5, 8)},
            {
                1: config.as_of_datetime - timedelta(hours=1),
                2: config.as_of_datetime - timedelta(hours=2),
                3: config.as_of_datetime - timedelta(hours=3),
                5: config.as_of_datetime - timedelta(hours=5),
                8: config.as_of_datetime - timedelta(hours=8),
            },
        )
        latest = config.as_of_datetime
        window_start = latest - timedelta(hours=24)
        self.assertEqual(
            {
                index
                for index, started_at in starts.items()
                if window_start < started_at <= latest
            },
            {1, 2, 3, 5, 8, 13},
        )
        self.assertEqual(starts[14], window_start)
        self.assertLess(starts[15], window_start)
        self.assertEqual(
            [_audience_role_name(index) for index in range(4)],
            ["student", "mentor", "supervisor", "student"],
        )
        self.assertEqual(
            {
                _audience_role_name((announcement_index - 2) // 3)
                for announcement_index in (2, 5, 8)
            },
            {"student", "mentor", "supervisor"},
        )

    def test_custom_high_delivery_count_adds_recent_mailbox_alert_burst(self):
        config = DatasetConfig(deliveries=90)
        published_at = config.as_of_datetime - timedelta(days=200)
        starts = {
            index: _delivery_started_at(config, index, published_at)
            for index in range(1, config.deliveries + 1)
        }
        self.assertEqual(
            {
                index
                for index, started_at in starts.items()
                if config.as_of_datetime - timedelta(hours=24)
                < started_at
                <= config.as_of_datetime
            },
            (set(ANALYTICS_EMAIL_ALERT_BURST_RANGE) - {14, 15}) | {1, 2, 3, 5, 8},
        )
        self.assertLessEqual(
            max(
                started_at
                for index, started_at in starts.items()
                if index not in ANALYTICS_EMAIL_ALERT_BURST_RANGE
                and index not in {1, 2, 3, 5, 8, 13, 14, 15}
            ),
            config.as_of_datetime - timedelta(hours=48),
        )

    def test_missing_role_and_group_audiences_degrade_to_sendable_global(self):
        config = DatasetConfig(
            admins=1,
            supervisors=0,
            mentors=0,
            students=1,
            groups=0,
            messages=0,
            login_events=0,
            tasks=0,
            resources=0,
            resource_accesses=0,
            announcements=8,
            deliveries=8,
            events=0,
            rsvps=0,
        ).validate()
        created_announcements = []
        created_audiences = []

        class AnnouncementManager:
            @staticmethod
            def create(**values):
                row = SimpleNamespace(
                    pk=len(created_announcements) + 1,
                    **values,
                )
                created_announcements.append(row)
                return row

        class AudienceManager:
            @staticmethod
            def create(**values):
                created_audiences.append(values)
                return SimpleNamespace(**values)

        class FakeAnnouncement:
            class VisibilityScope:
                GLOBAL = "global"
                ROLE_BASED = "role_based"

            objects = AnnouncementManager()

        class FakeAnnouncementAudience:
            objects = AudienceManager()

        models = ModuleType("apps.announcements.models")
        models.Announcement = FakeAnnouncement
        models.AnnouncementAudience = FakeAnnouncementAudience
        active_user = SimpleNamespace(is_active=True)
        buckets = {
            "admin": [active_user],
            "supervisor": [],
            "mentor": [],
            "student": [active_user],
        }
        roles = {
            "student": "student-role",
            "mentor": "mentor-role",
            "supervisor": "supervisor-role",
        }

        with patch.dict(sys.modules, {"apps.announcements.models": models}):
            rows = _create_announcements(config, roles, buckets, [], {})

        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0].visibility_scope, "global")
        self.assertEqual(rows[1].visibility_scope, "role_based")
        self.assertEqual(rows[4].visibility_scope, "global")
        self.assertEqual(rows[7].visibility_scope, "global")
        self.assertIsNone(rows[4].archived_at)
        self.assertEqual(
            created_audiences,
            [{"announcement": rows[1], "role": "student-role"}],
        )

    def test_delivery_counts_use_resolved_audiences_and_cache_each_audience(self):
        config = DatasetConfig(announcements=3, deliveries=5)
        resolver_calls = []
        created_deliveries = []

        def resolve(announcement_id, visibility_scope):
            resolver_calls.append((announcement_id, visibility_scope))
            if announcement_id == 1:
                return ["second@example.test", "first@example.test", "first@example.test"]
            if announcement_id == 2:
                return ["student@example.test"]
            raise AssertionError("shared global audience should reuse the first resolution")

        class DeliveryManager:
            @staticmethod
            def bulk_create(rows, batch_size):
                created_deliveries.extend(rows)

        class FakeAnnouncementDelivery:
            class Status:
                SUCCESS = "success"
                PARTIAL = "partial"
                FAILED = "failed"

            objects = DeliveryManager()

            def __init__(self, **values):
                self.__dict__.update(values)

        service = ModuleType("apps.admin.services.announcement")
        service.resolve_announcement_recipient_emails = resolve
        models = ModuleType("apps.announcements.models")
        models.AnnouncementDelivery = FakeAnnouncementDelivery
        announcements = [
            SimpleNamespace(
                pk=1,
                visibility_scope="global",
                published_at=config.as_of_datetime - timedelta(days=10),
                _synthetic_audience_key=("global",),
            ),
            SimpleNamespace(
                pk=2,
                visibility_scope="role_based",
                published_at=config.as_of_datetime - timedelta(days=10),
                _synthetic_audience_key=("role", "Student"),
            ),
            SimpleNamespace(
                pk=3,
                visibility_scope="global",
                published_at=config.as_of_datetime - timedelta(days=10),
                _synthetic_audience_key=("global",),
            ),
        ]

        with patch.dict(
            sys.modules,
            {
                "apps.admin.services.announcement": service,
                "apps.announcements.models": models,
            },
        ):
            _create_deliveries(
                config,
                announcements,
                {"admin": ["admin-user"]},
            )

        self.assertEqual(
            resolver_calls,
            [(1, "global"), (2, "role_based")],
        )
        self.assertEqual(len(created_deliveries), 5)
        self.assertEqual(created_deliveries[0].recipient_count, 2)
        self.assertEqual(created_deliveries[0].success_count, 2)
        self.assertEqual(created_deliveries[1].status, "success")
        self.assertEqual(created_deliveries[1].recipient_count, 1)
        self.assertEqual(created_deliveries[2].failure_count, 2)
        self.assertEqual(
            [item["email"] for item in created_deliveries[2].failed_recipients],
            ["first@example.test", "second@example.test"],
        )
        self.assertEqual(
            created_deliveries[4].success_count + created_deliveries[4].failure_count,
            created_deliveries[4].recipient_count,
        )

    def test_zero_deliveries_do_not_require_an_admin_bucket(self):
        config = DatasetConfig(
            admins=0,
            resources=0,
            resource_accesses=0,
            announcements=0,
            deliveries=0,
        ).validate()
        self.assertIsNone(_create_deliveries(config, [], {"admin": []}))

    def test_synthetic_login_uses_the_production_entity_contract(self):
        self.assertEqual(LOGIN_ENTITY, "user")


class SafetyConfigTests(unittest.TestCase):
    def test_full_reset_accepts_only_disposable_demo_database_names(self):
        validate_reset_database_name("biotech_llm_demo_20261105_170429")
        for name in ("biotech_dev", "biotech_llm_preview", "postgres", "biotech_llm_demo_", "biotech_llm_demo_x;DROP"):
            with self.subTest(name=name), self.assertRaises(UnsafeDatabaseError):
                validate_reset_database_name(name)

    def _valid_values(self):
        return {
            "debug": True,
            "engine": "django.db.backends.postgresql",
            "name": "biotech_dev",
            "host": "postgres",
        }

    @patch.dict(
        os.environ,
        {
            "LOCAL_DB_TOOL_GUARD": SAFETY_TOKEN,
            "LOCAL_DB_EXPECTED_NAME": "biotech_dev",
            "LOCAL_DB_EXPECTED_HOST": "postgres",
        },
        clear=False,
    )
    def test_expected_compose_target_is_accepted(self):
        validate_config_values(**self._valid_values())

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_guard_is_rejected(self):
        with self.assertRaisesRegex(UnsafeDatabaseError, "GUARD"):
            validate_config_values(**self._valid_values())

    @patch.dict(
        os.environ,
        {
            "LOCAL_DB_TOOL_GUARD": SAFETY_TOKEN,
            "LOCAL_DB_EXPECTED_NAME": "biotech_dev",
            "LOCAL_DB_EXPECTED_HOST": "postgres",
        },
        clear=False,
    )
    def test_remote_or_production_like_targets_are_rejected(self):
        values = self._valid_values()
        values["host"] = "customer.postgres.database.azure.com"
        with self.assertRaises(UnsafeDatabaseError):
            validate_config_values(**values)

    @patch.dict(
        os.environ,
        {
            "LOCAL_DB_TOOL_GUARD": SAFETY_TOKEN,
            "LOCAL_DB_EXPECTED_NAME": "biotech_production",
            "LOCAL_DB_EXPECTED_HOST": "postgres",
        },
        clear=False,
    )
    def test_production_like_database_name_is_rejected(self):
        values = self._valid_values()
        values["name"] = "biotech_production"
        with self.assertRaisesRegex(UnsafeDatabaseError, "production-like"):
            validate_config_values(**values)


if __name__ == "__main__":
    unittest.main()
