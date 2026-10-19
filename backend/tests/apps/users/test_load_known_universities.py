import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.users.models import KnownUniversity


class LoadKnownUniversitiesTests(TestCase):
    def _csv(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def _run(self, text, *args):
        out = StringIO()
        call_command("load_known_universities", self._csv(text), *args, stdout=out)
        return out.getvalue()

    def _names(self):
        return list(KnownUniversity.objects.values_list("name", flat=True))

    def test_adds_each_name_in_the_file(self):
        output = self._run("name,country\nUSYD,Australia\nMonash  Uni ,Australia\n")

        self.assertEqual(self._names(), ["Monash Uni", "USYD"])
        self.assertIn("Added 2 universities, skipped 0.", output)

    def test_skips_blank_listed_and_repeated_names(self):
        KnownUniversity.objects.create(name="USYD")

        output = self._run("name\nusyd\nUNSW\nunsw\n   \n")

        self.assertEqual(self._names(), ["UNSW", "USYD"])
        self.assertIn("Added 1 universities, skipped 3.", output)

    def test_a_rerun_adds_nothing(self):
        self._run("name\nUSYD\n")

        output = self._run("name\nUSYD\n")

        self.assertEqual(self._names(), ["USYD"])
        self.assertIn("Added 0 universities, skipped 1.", output)

    def test_reads_another_column_when_asked(self):
        self._run("institution,name\nUSYD,ignored\n", "--column", "institution")

        self.assertEqual(self._names(), ["USYD"])

    def test_dry_run_adds_nothing(self):
        output = self._run("name\nUSYD\n", "--dry-run")

        self.assertEqual(self._names(), [])
        self.assertIn("Would add 1 universities, skipped 0.", output)

    def test_a_file_without_the_column_is_refused(self):
        with self.assertRaisesMessage(CommandError, 'No "name" column'):
            self._run("institution\nUSYD\n")

    def test_a_missing_file_is_refused(self):
        with self.assertRaisesMessage(CommandError, "Could not read"):
            call_command("load_known_universities", "/nonexistent/universities.csv")
