from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.admin.services.known_university import add_known_university
from apps.audit.models import AuditLog
from apps.users.models import KnownUniversity
from tests.apps.users.test_load_known_universities import csv_file

OLD = "name\nUSYD\nUNSW\nSydney Uni\nAbadan Institute of Technology\nHand Added\nRenamed Since\n"
NEW = "full_name,acronym,country\nThe University of Sydney,USYD,Australia\nAbadan Institute of Technology,,Iran\n"
DOOMED = ["Sydney Uni", "UNSW", "USYD"]
DRY_RUN_END = "Dry run: nothing deleted. Re-run with --apply to delete."


class PruneKnownUniversitiesTests(TestCase):
    def setUp(self):
        for name in ("USYD", "UNSW", "Sydney Uni", "Abadan Institute of Technology", "Not In The Old File"):
            KnownUniversity.objects.create(full_name=name)
        KnownUniversity.objects.create(full_name="Renamed Since", acronym="RS")
        add_known_university("Hand Added", actor=get_user_model().objects.create_user(email="admin@example.com"))
        KnownUniversity.objects.create(full_name="The University of Sydney", acronym="USYD", country="Australia")

    def prune(self, *args, old=OLD, new=NEW):
        out = StringIO()
        call_command(
            "prune_known_universities", csv_file(self, old), "--keep", csv_file(self, new), *args, stdout=out,
        )
        return out.getvalue()

    def names(self):
        return list(KnownUniversity.objects.values_list("full_name", flat=True))

    @staticmethod
    def listed(output):
        return sorted(line[2:] for line in output.splitlines() if line.startswith("  ") and not line[2].isdigit())

    def deletions(self):
        return AuditLog.objects.filter(entity_type="known_university", action="delete")

    def test_a_plain_run_lists_the_right_rows_and_deletes_nothing(self):
        before = self.names()

        output = self.prune()

        self.assertEqual(self.names(), before)
        self.assertEqual(self.listed(output), DOOMED)
        self.assertIn(
            "Kept from the older file:\n  1 in the newer file\n  1 has an acronym or country\n"
            "  1 added on the admin page\nWould delete 3 universities.\n",
            output,
        )
        self.assertEqual(output.rstrip("\n").splitlines()[-1], DRY_RUN_END)
        self.assertFalse(self.deletions().exists())

    def test_a_plain_run_lists_every_name(self):
        old = "name\n" + "".join(f"Old {i}\n" for i in range(25))
        for i in range(25):
            KnownUniversity.objects.create(full_name=f"Old {i}")

        output = self.prune(old=old)

        self.assertEqual(self.listed(output), sorted(f"Old {i}" for i in range(25)))
        self.assertNotIn("more", output)

    def test_apply_deletes_only_the_older_files_rows_and_records_them(self):
        output = self.prune("--apply")

        self.assertEqual(self.names(), [
            "Abadan Institute of Technology", "Hand Added", "Not In The Old File", "Renamed Since",
            "The University of Sydney",
        ])
        self.assertIn("Deleted 3 universities", output)
        self.assertNotIn(DRY_RUN_END, output)
        log = self.deletions().get()
        self.assertEqual(log.before_state["count"], 3)
        self.assertEqual(sorted(log.before_state["names"]), DOOMED)
        self.assertTrue(log.before_state["pruned_with"].endswith(".csv"))

    def test_apply_twice_deletes_nothing_the_second_time(self):
        self.prune("--apply")
        remaining = self.names()

        output = self.prune("--apply")

        self.assertIn("Deleted 0 universities", output)
        self.assertEqual(self.names(), remaining)
        self.assertEqual(self.deletions().count(), 1)

    def test_a_dry_run_and_apply_agree_on_what_goes(self):
        would_go = self.listed(self.prune())
        before = set(self.names())

        self.prune("--apply")

        self.assertEqual(sorted(before - set(self.names())), would_go)
        self.assertEqual(sorted(self.deletions().get().before_state["names"]), would_go)

    def test_matches_ignore_case_and_spacing(self):
        self.prune("--apply", old="name\n  usyd \nsydney   UNI\n")

        self.assertNotIn("USYD", self.names())
        self.assertNotIn("Sydney Uni", self.names())

    def test_apply_shows_the_first_names_unless_asked_for_all(self):
        old = "name\n" + "".join(f"Old {i}\n" for i in range(25))
        for i in range(25):
            KnownUniversity.objects.create(full_name=f"Old {i}")

        self.assertIn("and 5 more", self.prune("--apply", old=old))

    def test_the_newer_file_is_required(self):
        with self.assertRaises(CommandError):
            call_command("prune_known_universities", csv_file(self, OLD), stdout=StringIO())

    def test_dry_run_is_no_longer_an_option(self):
        with self.assertRaises(CommandError):
            self.prune("--dry-run")
        self.assertEqual(len(self.names()), 8)
