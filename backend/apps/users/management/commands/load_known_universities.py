"""Add universities from a CSV file to the list the registration school check
consults (apps.users.models.KnownUniversity).

The file needs a header row: "full_name", with optional "acronym" and
"country" columns, or the older single "name" column (or the one given with
--column), read as full names. Values are tidied as the list stores them.
Blank or over-long values and repeats within the file are skipped.

A full name already listed (ignoring case and spacing) gets the file's
acronym and country where its own are blank; one that differs is left as it
is and reported as a conflict, so an admin's edit is never overwritten.
Nothing is ever removed (see prune_known_universities), so a rerun changes
nothing.

Check a list's licence before loading it.

Usage:
  python manage.py load_known_universities universities.csv
  python manage.py load_known_universities names.csv --column institution
  python manage.py load_known_universities universities.csv --dry-run
"""
import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.users.models import KnownUniversity

FIELD_LIMITS = {
    field: KnownUniversity._meta.get_field(field).max_length for field in ("full_name", "acronym", "country")
}


def read_rows(path, column=None) -> list[dict]:
    """The file's rows as {full_name, acronym, country}, tidied."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            name_column = column or ("full_name" if "full_name" in headers else "name")
            if name_column not in headers:
                raise CommandError(f'No "{name_column}" column in {path}.')
            return [
                {
                    "full_name": KnownUniversity.normalise(row.get(name_column)),
                    "acronym": KnownUniversity.normalise(row.get("acronym")),
                    "country": KnownUniversity.normalise(row.get("country")),
                }
                for row in reader
            ]
    except OSError as exc:
        raise CommandError(f"Could not read {path}: {exc}")


class Command(BaseCommand):
    help = "Add universities from a CSV file to the list of known universities."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="CSV file with a header row.")
        parser.add_argument("--column", default=None, help="Column holding full names (default: full_name, else name).")
        parser.add_argument("--dry-run", action="store_true", help="Report what would change; change nothing.")

    def handle(self, *args, **options):
        rows = read_rows(options["csv_path"], options["column"])
        listed = {university.full_name.lower(): university for university in KnownUniversity.objects.all()}
        new, updated, conflicts, skipped, seen = [], [], [], 0, set()
        for row in rows:
            key = row["full_name"].lower()
            if not key or key in seen or any(len(row[field]) > limit for field, limit in FIELD_LIMITS.items()):
                skipped += 1
                continue
            seen.add(key)
            existing = listed.get(key)
            if existing is None:
                new.append(KnownUniversity(**row))
                continue
            changed = False
            for field in ("acronym", "country"):
                ours, theirs = getattr(existing, field), row[field]
                if theirs and not ours:
                    setattr(existing, field, theirs)
                    changed = True
                elif theirs and ours.lower() != theirs.lower():
                    conflicts.append(f"{existing.full_name}: {field} is {ours!r}, the file says {theirs!r}")
            if changed:
                updated.append(existing)
            else:
                skipped += 1

        if not options["dry_run"]:
            with transaction.atomic():
                KnownUniversity.objects.bulk_create(new, batch_size=1000)
                KnownUniversity.objects.bulk_update(updated, ["acronym", "country"], batch_size=1000)
        for conflict in conflicts:
            self.stdout.write(f"Conflict, left as it is: {conflict}")
        add, fill = ("Would add", "would fill in") if options["dry_run"] else ("Added", "filled in")
        self.stdout.write(
            f"{add} {len(new)} universities, {fill} {len(updated)}, conflicts {len(conflicts)}, skipped {skipped}."
        )
