import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.users.models import KnownUniversity


def csv_file(test, text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    handle.write(text)
    handle.close()
    test.addCleanup(os.unlink, handle.name)
    return handle.name


class LoadKnownUniversitiesTests(TestCase):
    def _run(self, text, *args):
        out = StringIO()
        call_command("load_known_universities", csv_file(self, text), *args, stdout=out)
        return out.getvalue()

    def _names(self):
        return list(KnownUniversity.objects.values_list("full_name", flat=True))

    def _rows(self):
        return list(KnownUniversity.objects.values_list("full_name", "acronym", "country"))

    def test_adds_each_name_in_an_older_name_file(self):
        output = self._run("name,country\nUSYD,Australia\nMonash  Uni ,Australia\n")

        self.assertEqual(self._names(), ["Monash Uni", "USYD"])
        self.assertIn("Added 2 universities, filled in 0, conflicts 0, skipped 0.", output)

    def test_adds_full_names_acronyms_and_countries(self):
        output = self._run(
            "full_name,acronym,country\n"
            "The University of Sydney,USYD,Australia\n"
            '"Bonaire University, Kralendijk", ,"Bonaire, Sint Eustatius, and Saba"\n'
            "Sydney Uni,,Australia\n"
        )

        self.assertEqual(self._rows(), [
            ("Bonaire University, Kralendijk", "", "Bonaire, Sint Eustatius, and Saba"),
            ("Sydney Uni", "", "Australia"),
            ("The University of Sydney", "USYD", "Australia"),
        ])
        self.assertIn("Added 3 universities", output)

    def test_skips_blank_listed_repeated_and_over_long_rows(self):
        KnownUniversity.objects.create(full_name="USYD")

        output = self._run(
            "full_name,acronym,country\nusyd,,\nUNSW,,\nunsw,,\n   ,X,\n"
            f"Too Long Acronym University,{'A' * 65},\nToo Long Country University,,{'C' * 101}\n"
        )

        self.assertEqual(self._names(), ["UNSW", "USYD"])
        self.assertIn("Added 1 universities, filled in 0, conflicts 0, skipped 5.", output)

    def test_fills_in_a_blank_acronym_or_country_but_never_overwrites_one(self):
        KnownUniversity.objects.create(full_name="Macquarie University")
        KnownUniversity.objects.create(full_name="Monash University", acronym="MU", country="Australia")

        output = self._run(
            "full_name,acronym,country\n"
            "macquarie university,MQ,Australia\n"
            "Monash University,MONASH,australia\n"
        )

        self.assertEqual(self._rows(), [
            ("Macquarie University", "MQ", "Australia"),
            ("Monash University", "MU", "Australia"),
        ])
        self.assertIn("Conflict, left as it is: Monash University: acronym is 'MU', the file says 'MONASH'", output)
        self.assertNotIn("country is", output)
        self.assertIn("Added 0 universities, filled in 1, conflicts 1, skipped 1.", output)

    def test_a_rerun_changes_nothing(self):
        text = "full_name,acronym,country\nThe University of Sydney,USYD,Australia\nAalto University,,Finland\n"
        self._run(text)
        before = self._rows()

        output = self._run(text)

        self.assertEqual(self._rows(), before)
        self.assertIn("Added 0 universities, filled in 0, conflicts 0, skipped 2.", output)

    def test_reads_another_column_when_asked(self):
        self._run("institution,name\nUSYD,ignored\n", "--column", "institution")

        self.assertEqual(self._names(), ["USYD"])

    def test_dry_run_changes_nothing(self):
        KnownUniversity.objects.create(full_name="Macquarie University")

        output = self._run("full_name,acronym,country\nUSYD,,\nMacquarie University,MQ,\n", "--dry-run")

        self.assertEqual(self._rows(), [("Macquarie University", "", "")])
        self.assertIn("Would add 1 universities, would fill in 1, conflicts 0, skipped 0.", output)

    def test_a_file_without_a_name_column_is_refused(self):
        with self.assertRaisesMessage(CommandError, 'No "name" column'):
            self._run("institution\nUSYD\n")
        with self.assertRaisesMessage(CommandError, 'No "institution" column'):
            self._run("full_name\nUSYD\n", "--column", "institution")

    def test_a_missing_file_is_refused(self):
        with self.assertRaisesMessage(CommandError, "Could not read"):
            call_command("load_known_universities", "/nonexistent/universities.csv")
