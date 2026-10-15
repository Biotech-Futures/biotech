from datetime import timedelta
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.system_logs.models import SystemLogEntry
from apps.system_logs.services import prune

from ._factory import make_entry


class PruneTests(TestCase):
    @override_settings(SYSTEM_LOG_RETENTION_DAYS=30)
    def test_deletes_only_rows_older_than_the_retention_setting(self):
        old = make_entry(age=timedelta(days=31))
        recent = make_entry(age=timedelta(days=29))

        self.assertEqual(prune(), 1)

        self.assertFalse(SystemLogEntry.objects.filter(pk=old.pk).exists())
        self.assertTrue(SystemLogEntry.objects.filter(pk=recent.pk).exists())

    def test_days_argument_overrides_the_setting(self):
        make_entry(age=timedelta(days=8))
        make_entry(age=timedelta(days=6))

        self.assertEqual(prune(7), 1)
        self.assertEqual(SystemLogEntry.objects.count(), 1)

    def test_deletes_in_batches_until_none_are_left(self):
        for _ in range(5):
            make_entry(age=timedelta(days=40))

        self.assertEqual(prune(30, batch_size=2), 5)
        self.assertEqual(SystemLogEntry.objects.count(), 0)

    def test_refuses_less_than_one_day(self):
        make_entry(age=timedelta(days=2))

        with self.assertRaises(ValueError):
            prune(0)
        self.assertEqual(SystemLogEntry.objects.count(), 1)


class PruneCommandTests(TestCase):
    def test_command_reports_how_many_were_deleted(self):
        make_entry(age=timedelta(days=10))
        out = StringIO()

        call_command("prune_system_logs", "--days", "5", stdout=out)

        self.assertIn("Deleted 1 system log entries.", out.getvalue())
        self.assertEqual(SystemLogEntry.objects.count(), 0)

    def test_command_rejects_zero_days(self):
        with self.assertRaises(CommandError):
            call_command("prune_system_logs", "--days", "0", stdout=StringIO())
