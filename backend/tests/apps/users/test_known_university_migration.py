"""users.0036: the known-university names already listed become full names,
with a blank acronym and country.

The test settings build the database without migrations, so this swaps the
table for its 0035 shape and applies 0036's own operations to it."""
from django.db import IntegrityError, connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase, override_settings

from apps.users.models import KnownUniversity

BEFORE = ("users", "0035_merge_0033_mentor_weekly_hours_0034_email_check_job")
AFTER = ("users", "0036_known_university_full_name_acronym_country")


class KnownUniversityMigrationTests(TransactionTestCase):
    def setUp(self):
        with override_settings(MIGRATION_MODULES={}):
            self.loader = MigrationLoader(None, ignore_no_migrations=True)
        self.before = self.loader.project_state(BEFORE)
        self.addCleanup(self.restore_table)

    def restore_table(self):
        with connection.schema_editor() as editor:
            editor.execute(editor.sql_delete_table % {"table": editor.quote_name(KnownUniversity._meta.db_table)})
            editor.create_model(KnownUniversity)

    def test_existing_names_become_full_names_with_blank_acronym_and_country(self):
        Old = self.before.apps.get_model("users", "KnownUniversity")
        with connection.schema_editor() as editor:
            editor.delete_model(KnownUniversity)
            editor.create_model(Old)
        Old.objects.create(name="USYD")
        Old.objects.create(name="Massachusetts Institute of Technology")

        with connection.schema_editor() as editor:
            after = self.loader.get_migration(*AFTER).apply(self.before.clone(), editor)
        New = after.apps.get_model("users", "KnownUniversity")

        self.assertEqual(
            sorted(New.objects.values_list("full_name", "acronym", "country")),
            [("Massachusetts Institute of Technology", "", ""), ("USYD", "", "")],
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            New.objects.create(full_name="usyd")
        New.objects.create(full_name="University of Technology Sydney", acronym="UTS")
        New.objects.create(full_name="University of Technology Sarawak", acronym="UTS")
        self.assertEqual(New.objects.filter(acronym="UTS").count(), 2)
