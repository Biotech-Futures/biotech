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
nothing. Management > Known Universities' Upload Universities loads a file
the same way (apps.users.known_university_load).

Check a list's licence before loading it.

Usage:
  python manage.py load_known_universities universities.csv
  python manage.py load_known_universities names.csv --column institution
  python manage.py load_known_universities universities.csv --dry-run
"""
from django.core.management.base import BaseCommand, CommandError

from apps.users.known_university_load import NoNameColumn, load_universities, read_university_rows


def read_rows(path, column=None) -> list[dict]:
    """The file's rows as {full_name, acronym, country}, tidied."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            return read_university_rows(handle, column)
    except NoNameColumn as exc:
        raise CommandError(f'No "{exc}" column in {path}.')
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
        result = load_universities(rows, dry_run=options["dry_run"])
        for conflict in result["conflicts"]:
            self.stdout.write(f"Conflict, left as it is: {conflict}")
        add, fill = ("Would add", "would fill in") if options["dry_run"] else ("Added", "filled in")
        self.stdout.write(
            f"{add} {result['added']} universities, {fill} {result['filled']}, "
            f"conflicts {len(result['conflicts'])}, skipped {result['skipped']}."
        )
