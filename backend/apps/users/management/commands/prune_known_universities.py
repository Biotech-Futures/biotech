"""Take off the known-university list the rows an older file loaded, once a
newer file has been loaded in their place.

A row is deleted only when all of these hold:
- its full name is in OLD.csv ("name" or "full_name" column, ignoring case
  and spacing);
- it is not a full name in the --keep file (the newer list);
- its acronym and country are blank, as the older file left them;
- it was not added on the admin page (no "create" audit entry for it).

Load the newer file first, so no university is ever missing from the list.
A plain run is a dry run: it lists every row that would go and why the rest
are kept, and deletes nothing. Only --apply deletes, in one transaction, and
records one audit entry naming them.

Usage:
  python manage.py prune_known_universities known_universities.csv --keep universities_three_column.csv
  python manage.py prune_known_universities known_universities.csv --keep universities_three_column.csv --apply
"""
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services import log_audit_event
from apps.users.management.commands.load_known_universities import read_rows
from apps.users.models import KnownUniversity

SHOWN = 20


class Command(BaseCommand):
    help = (
        "List the known universities an older file loaded (keeping a newer file's and any added by hand); "
        "delete them only with --apply."
    )

    def add_arguments(self, parser):
        parser.add_argument("old_csv", help="The older file whose rows go.")
        parser.add_argument("--keep", required=True, help="The newer file, whose full names always stay.")
        parser.add_argument("--apply", action="store_true", help="Delete them. Without it, nothing is deleted.")

    def handle(self, *args, **options):
        old = {row["full_name"].lower() for row in read_rows(options["old_csv"])} - {""}
        keep = {row["full_name"].lower() for row in read_rows(options["keep"])} - {""}
        added_by_hand = set(
            AuditLog.objects.filter(entity_type="known_university", action=AuditLog.ActionChoices.CREATE)
            .values_list("entity_id", flat=True)
        )

        doomed, kept = [], {"in the newer file": 0, "has an acronym or country": 0, "added on the admin page": 0}
        for university in KnownUniversity.objects.all():
            key = university.full_name.lower()
            if key not in old:
                continue
            if key in keep:
                kept["in the newer file"] += 1
            elif university.acronym or university.country:
                kept["has an acronym or country"] += 1
            elif university.pk in added_by_hand:
                kept["added on the admin page"] += 1
            else:
                doomed.append(university)

        names = [university.full_name for university in doomed]
        kept_text = ", ".join(f"{count} {reason}" for reason, count in kept.items())

        if not options["apply"]:
            for name in names:
                self.stdout.write(f"  {name}")
            self.stdout.write("Kept from the older file:")
            for reason, count in kept.items():
                self.stdout.write(f"  {count} {reason}")
            self.stdout.write(f"Would delete {len(doomed)} universities.")
            self.stdout.write("Dry run: nothing deleted. Re-run with --apply to delete.")
            return

        shown = names if options["verbosity"] > 1 else names[:SHOWN]
        for name in shown:
            self.stdout.write(f"  {name}")
        if len(shown) < len(names):
            self.stdout.write(f"  … and {len(names) - len(shown)} more (-v 2 lists them all)")
        if doomed:
            with transaction.atomic():
                KnownUniversity.objects.filter(pk__in=[university.pk for university in doomed]).delete()
                log_audit_event(
                    entity_type="known_university", entity_id=0, action=AuditLog.ActionChoices.DELETE,
                    before_state={"pruned_with": os.path.basename(options["old_csv"]), "count": len(names), "names": names},
                )
        self.stdout.write(f"Deleted {len(doomed)} universities; kept from the older file: {kept_text}.")
