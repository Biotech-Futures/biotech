"""Add names from a CSV file to the list of known universities, which the
registration school check consults (apps.users.models.KnownUniversity).

The file needs a header row. Names are read from its ``name`` column, or the
one given with --column. Blank names, names already listed (ignoring case and
spacing) and repeats within the file are skipped, so a rerun adds nothing
twice. Nothing is ever removed: do that in Django admin.

No dataset ships with the code. Check a list's licence before loading it.

Usage:
  python manage.py load_known_universities universities.csv
  python manage.py load_known_universities universities.csv --column institution
  python manage.py load_known_universities universities.csv --dry-run
"""
import csv

from django.core.management.base import BaseCommand, CommandError

from apps.users.models import KnownUniversity


class Command(BaseCommand):
    help = "Add names from a CSV file to the list of known universities."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="CSV file with a header row.")
        parser.add_argument("--column", default="name", help="Column holding the names (default: name).")
        parser.add_argument("--dry-run", action="store_true", help="Report what would be added; add nothing.")

    def handle(self, *args, **options):
        column = options["column"]
        try:
            with open(options["csv_path"], newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                if column not in (reader.fieldnames or []):
                    raise CommandError(f'No "{column}" column in {options["csv_path"]}.')
                names = [KnownUniversity.normalise(row.get(column)) for row in reader]
        except OSError as exc:
            raise CommandError(f"Could not read {options['csv_path']}: {exc}")

        listed = {name.lower() for name in KnownUniversity.objects.values_list("name", flat=True)}
        new, skipped = [], 0
        for name in names:
            if not name or len(name) > 255 or name.lower() in listed:
                skipped += 1
                continue
            listed.add(name.lower())
            new.append(KnownUniversity(name=name))

        if not options["dry_run"]:
            KnownUniversity.objects.bulk_create(new)
        verb = "Would add" if options["dry_run"] else "Added"
        self.stdout.write(f"{verb} {len(new)} universities, skipped {skipped}.")
