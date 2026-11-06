"""PostgreSQL reset regressions, enabled only on an explicitly named test DB."""
import os
import unittest
from unittest.mock import patch

from dataset import DatasetConfig


@unittest.skipUnless(os.environ.get('LOCAL_DB_FULL_RESET_TEST_DB'), 'requires a disposable reset test database')
class FullDatabaseResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from operations import setup_django
        setup_django()
        from safety import assert_safe_database
        target = assert_safe_database()
        if target.name != os.environ['LOCAL_DB_FULL_RESET_TEST_DB'] or '_reset_test_' not in target.name:
            raise RuntimeError('Full reset regression tests require their own explicitly named test database')
        cls.config = DatasetConfig(
            admins=1, supervisors=0, mentors=0, students=2,
            groups=0, messages=0, login_events=0, tasks=0,
            resources=0, resource_accesses=0, announcements=0, deliveries=0,
            events=0, rsvps=0, as_of='2026-11-06T03:31:00Z',
        ).validate()

    def setUp(self):
        from operations import bootstrap_dataset
        _, self.before = bootstrap_dataset(self.config, migration_verbosity=0)
        from django.db import connection
        from django.utils import timezone
        from apps.services.models import EmailDeliveryMetric
        from apps.users.models import User
        User.objects.create_user(email='unmanaged-reset-test@example.test', password='test-only-password')
        EmailDeliveryMetric.objects.create(
            email_type='login_code', source_mailbox='test@example.test',
            attempted_count=1, delivered_count=1, failed_count=0,
            status='success', started_at=timezone.now(), completed_at=timezone.now(),
        )
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE reset_test_sentinel (value text)')
            cursor.execute("INSERT INTO reset_test_sentinel VALUES ('preserve on failure')")
            cursor.execute('CREATE SCHEMA reset_test_extra')
            cursor.execute('CREATE TABLE reset_test_extra.unknown_data (value integer)')
            cursor.execute('INSERT INTO reset_test_extra.unknown_data VALUES (42)')

    def test_all_existing_data_and_extra_schemas_are_rebuilt(self):
        from operations import bootstrap_dataset
        from django.db import connection
        from apps.services.models import EmailDeliveryMetric
        from apps.users.models import User
        from verification import unmanaged_business_counts
        _, result = bootstrap_dataset(self.config, migration_verbosity=0)
        self.assertEqual(result['fingerprint'], self.before['fingerprint'])
        self.assertEqual(result['counts'], self.before['counts'])
        self.assertFalse(User.objects.filter(email='unmanaged-reset-test@example.test').exists())
        self.assertEqual(EmailDeliveryMetric.objects.count(), 0)
        self.assertEqual(unmanaged_business_counts(), {})
        self.assertTrue(User.objects.get(email='synthetic.admin.0001@team4-synthetic.biotech.test').check_password('admin123'))
        self.assertTrue(User.objects.get(email='synthetic.student.0001@team4-synthetic.biotech.test').check_password('student123'))
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.reset_test_sentinel')")
            self.assertIsNone(cursor.fetchone()[0])
            cursor.execute("SELECT count(*) FROM pg_namespace WHERE nspname='reset_test_extra'")
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_failure_after_migrations_restores_the_entire_previous_database(self):
        from operations import bootstrap_dataset
        from django.db import connection
        from apps.services.models import EmailDeliveryMetric
        from apps.users.models import User
        from verification import verify_dataset
        with patch('generator.generate_dataset', side_effect=RuntimeError('intentional reset regression failure')):
            with self.assertRaisesRegex(RuntimeError, 'intentional reset regression failure'):
                bootstrap_dataset(self.config, migration_verbosity=0)
        self.assertTrue(User.objects.filter(email='unmanaged-reset-test@example.test').exists())
        self.assertEqual(EmailDeliveryMetric.objects.count(), 1)
        result = verify_dataset()
        self.assertEqual(result['fingerprint'], self.before['fingerprint'])
        self.assertEqual(result['counts'], self.before['counts'])
        with connection.cursor() as cursor:
            cursor.execute('SELECT value FROM reset_test_sentinel')
            self.assertEqual(cursor.fetchone()[0], 'preserve on failure')
            cursor.execute('SELECT value FROM reset_test_extra.unknown_data')
            self.assertEqual(cursor.fetchone()[0], 42)


if __name__ == '__main__':
    unittest.main()
