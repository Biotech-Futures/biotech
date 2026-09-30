"""Tests for the import_project_titles command."""
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook

from apps.groups.models import Groups
from apps.submissions.models import Submission


class ImportProjectTitlesTests(TestCase):
    def setUp(self):
        self.submitted_at = timezone.now()
        self.btf1 = Groups.objects.create(group_name="BTF1", year=2026)
        self.entry = Submission.objects.create(group=self.btf1, submitted_at=self.submitted_at)

    def _sheet(self, rows, headers=("Team code", "Project title")):
        book = Workbook()
        book.active.append(headers)
        for row in rows:
            book.active.append(row)
        handle, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(handle)
        book.save(path)
        self.addCleanup(os.remove, path)
        return path

    def _run(self, rows, *extra):
        out = StringIO()
        call_command("import_project_titles", self._sheet(rows), "--year", "2026", *extra, stdout=out)
        self.entry.refresh_from_db()
        return out.getvalue()

    def test_sets_both_titles_and_leaves_the_entry_submitted(self):
        output = self._run([("btf1", "  Plant   Sensors ")])

        self.assertEqual(self.entry.project_title, "Plant Sensors")
        self.assertEqual(self.entry.submitted_project_title, "Plant Sensors")
        self.assertEqual(self.entry.submitted_at, self.submitted_at)
        self.assertIn("Updated 1.", output)

    def test_a_dry_run_saves_nothing(self):
        output = self._run([("BTF1", "Plant Sensors")], "--dry-run")

        self.assertEqual(self.entry.submitted_project_title, "")
        self.assertIn("Would update 1.", output)

    def test_a_second_run_changes_nothing(self):
        self._run([("BTF1", "Plant Sensors")])

        self.assertIn("Already up to date: 1.", self._run([("BTF1", "Plant Sensors")]))

    def test_reports_teams_without_an_entry_and_creates_none(self):
        Groups.objects.create(group_name="BTF2", year=2026)

        output = self._run([("BTF2", "AlgaeGuard")])

        self.assertIn("No entry to attach a title to: BTF2", output)
        self.assertEqual(Submission.objects.count(), 1)

    def test_only_matches_teams_from_the_given_year(self):
        old = Groups.objects.create(group_name="BTF9", year=2025)
        Submission.objects.create(group=old)

        output = self._run([("BTF9", "Old Project")])

        self.assertIn("no 2026 team named BTF9", output)
        self.assertEqual(Submission.objects.get(group=old).submitted_project_title, "")

    def test_skips_deleted_teams(self):
        self.btf1.deleted_at = timezone.now()
        self.btf1.save()

        self.assertIn("no 2026 team named BTF1", self._run([("BTF1", "Plant Sensors")]))

    def test_reports_bad_rows_and_still_imports_the_good_ones(self):
        output = self._run([
            ("BTF1", "Plant Sensors"),
            ("BTF1", "A Second Title"),
            ("BTF3", ""),
            ("BTF4", "x" * 151),
        ])

        self.assertEqual(self.entry.submitted_project_title, "Plant Sensors")
        self.assertIn("row 3: BTF1 is listed more than once", output)
        self.assertIn("row 4: missing a team code or a title", output)
        self.assertIn("row 5: BTF4's title is over 150 characters", output)

    def test_refuses_a_sheet_without_the_expected_columns(self):
        path = self._sheet([("BTF1", "Plant Sensors")], headers=("Group", "Name"))

        with self.assertRaisesMessage(CommandError, "Team code"):
            call_command("import_project_titles", path, "--year", "2026", stdout=StringIO())
