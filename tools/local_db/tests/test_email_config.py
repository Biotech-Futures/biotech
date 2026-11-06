from dataclasses import replace
from datetime import timedelta
import unittest

from cli import _config_from_args, _parser
from dataset import DatasetConfig, EMAIL_TYPES
from email_samples import custom_batch_plan
from gui_server import config_from_payload, RequestValidationError


class EmailConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.config = DatasetConfig(email_mode='custom', as_of='2026-11-06T12:00:00Z')

    def test_exact_batch_count_and_time_endpoints(self):
        config = replace(self.config, email_batches=17).validate()
        plan = list(custom_batch_plan(config))
        self.assertEqual(len(plan), 17)
        self.assertEqual(plan[0][2], config.email_start_datetime)
        self.assertEqual(plan[-1][2], config.email_end_datetime)
        self.assertEqual(sum(row[0] == 'announcement' for row in plan), config.announcement_delivery_count)
        self.assertEqual(config.email_metric_count, 17)

    def test_gui_and_cli_round_trip_custom_settings(self):
        config = replace(self.config, email_batches=6, email_type='announcement',
                         email_status='partial', email_recipients=7,
                         email_start='2026-11-06T18:00:00+11:00', email_end='2026-11-06T20:00:00+11:00')
        submitted = config.to_manifest()
        parsed = config_from_payload({'config': submitted, 'confirm_replace': True})
        self.assertEqual(parsed.to_manifest(), submitted)
        flags = [item for key, value in submitted.items() for item in ('--' + key.replace('_', '-'), str(value))]
        self.assertEqual(_config_from_args(_parser().parse_args(['bootstrap', *flags])).to_manifest(), submitted)

    def test_system_only_batches_do_not_require_announcements(self):
        config = replace(self.config, announcements=0, email_type='login_code').validate()
        self.assertEqual(config.announcement_delivery_count, 0)
        with self.assertRaisesRegex(ValueError, 'announcement'):
            replace(config, email_type='mixed').validate()

    def test_invalid_status_recipients_and_times_are_rejected(self):
        invalid = (
            {'email_status': 'unknown'}, {'email_type': 'unknown'}, {'email_batches': True},
            {'email_recipients': self.config.active_users + 1}, {'email_recipients': 0},
            {'email_status': 'partial', 'email_recipients': 1},
            {'email_batches': 2_000_000, 'email_recipients': 2},
            {'email_start': '2026-11-06T12:00:00Z'},
            {'email_end': '2026-11-06T12:00:00Z'},
            {'email_end': '2026-11-05T13:00:01Z'},
            {'email_start': '2026-11-06T10:00:00'},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.config, **changes).validate()

    def test_gui_refuses_malformed_new_fields_before_generation(self):
        for name, value in [('email_batches', '5'), ('email_recipients', True), ('email_status', []), ('email_end', {})]:
            payload = {**self.config.to_manifest(), name: value}
            with self.subTest(name=name), self.assertRaises(RequestValidationError):
                config_from_payload({'config': payload, 'confirm_replace': True})

    def test_mixed_covers_types_results_and_single_recipient(self):
        plan = list(custom_batch_plan(self.config))
        self.assertEqual({row[0] for row in plan}, set(EMAIL_TYPES))
        for kind in EMAIL_TYPES:
            self.assertEqual({row[1] for row in plan if row[0] == kind}, {'success', 'partial', 'failed'})
        single = replace(self.config, email_type='login_code', email_recipients=1)
        self.assertEqual({row[1] for row in custom_batch_plan(single)}, {'success', 'failed'})
        for kind, status, started_at, failures in custom_batch_plan(single):
            self.assertEqual(failures, int(status == 'failed'))

    def test_zero_batches_are_valid_and_preset_keeps_previous_counts(self):
        self.assertEqual(list(custom_batch_plan(replace(self.config, email_batches=0))), [])
        self.assertEqual(DatasetConfig(deliveries=24).email_metric_count, 48)
        self.assertEqual(DatasetConfig(deliveries=24).announcement_delivery_count, 24)

    def test_active_recipient_capacity_matches_user_status_cycle(self):
        for count in range(18):
            config = replace(self.config, admins=1, students=count, mentors=0, supervisors=0)
            expected = 1 + sum(index % 8 in (0, 1, 2, 4) for index in range(count))
            self.assertEqual(config.active_users, expected)
