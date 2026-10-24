"""Loading universities into the list the registration school check consults
(KnownUniversity) from a spreadsheet: the load_known_universities command and
Management > Known Universities' Upload Universities both.

The command reads a file's full names from its full_name column, or the
older name column, with optional acronym and country columns, whatever their
case. Upload Universities takes name, acronym and country exactly, in that
order, as Upload guardian details takes its own (parse_university_upload).
Values are tidied as the list stores them. Blank or over-long values and
repeats within the file are skipped.

A full name already listed (ignoring case and spacing) gets the file's
acronym and country where its own are blank; one that differs is left as it
is and reported as a conflict, so an admin's edit is never overwritten.
Nothing is ever removed, so loading a file again changes nothing.
"""
from __future__ import annotations

import csv

from django.db import transaction
from django.utils import timezone

from apps.users.models import KnownUniversity

FIELD_LIMITS = {
    field: KnownUniversity._meta.get_field(field).max_length for field in ("full_name", "acronym", "country")
}


class NoNameColumn(ValueError):
    """The file has no column of full names."""


def _column_key(header) -> str:
    """A header compared loosely: "Full Name", "full name" and "full_name" alike."""
    return " ".join(str(header or "").replace("_", " ").lower().split())


def read_university_rows(handle, column=None) -> list[dict]:
    """A CSV's rows (from the open text ``handle``) as {full_name, acronym,
    country}, tidied. Full names from ``column``, else its Full Name column,
    else its Name column; raises NoNameColumn when there's none."""
    reader = csv.DictReader(handle)
    headers = {_column_key(header): header for header in reader.fieldnames or []}
    name = headers.get(_column_key(column)) if column else headers.get("full name") or headers.get("name")
    if name is None:
        raise NoNameColumn(column or "name")
    acronym, country = headers.get("acronym"), headers.get("country")
    return [
        {
            "full_name": KnownUniversity.normalise(row.get(name)),
            "acronym": KnownUniversity.normalise(row.get(acronym)) if acronym else "",
            "country": KnownUniversity.normalise(row.get(country)) if country else "",
        }
        for row in reader
    ]


# Upload Universities' columns, exactly and in this order, as My Students'
# Upload guardian details has its own (apps.users.guardian_upload).
HEADERS = ["name", "acronym", "country"]


def parse_university_upload(file, filename: str) -> dict:
    """Upload Universities' check of a sheet, as Upload guardian details
    checks one: its headers exactly and in order, then what loading it would
    do (load_universities, changing nothing), row by row as the spreadsheet
    numbers them (the header is row 1). ``rows`` is what Apply loads."""
    from apps.users.guardian_upload import _read_sheet  # read as that upload reads one

    result = {
        "checks": {"missing_headers": [], "header_order": "", "conflicts": []},
        "summary": {"added": 0, "filled": 0, "skipped": 0, "errors": 0},
        "filled_rows": [],
        "listed_rows": [],
        "repeated_rows": [],
        "invalid_rows": [],
        "rows": [],
    }
    checks = result["checks"]
    header, sheet_rows = _read_sheet(file, filename)
    checks["missing_headers"] = [name for name in HEADERS if name not in header]
    if not checks["missing_headers"] and header[: len(HEADERS)] != HEADERS:
        checks["header_order"] = f"Out of order (should be {', '.join(HEADERS)})"
    if checks["missing_headers"] or checks["header_order"]:
        result["summary"]["errors"] = len(checks["missing_headers"]) + bool(checks["header_order"])
        return result

    rows = result["rows"] = [
        {
            "full_name": KnownUniversity.normalise(values.get("name")),
            "acronym": KnownUniversity.normalise(values.get("acronym")),
            "country": KnownUniversity.normalise(values.get("country")),
        }
        for _, values in sheet_rows
    ]
    numbers = [number for number, _ in sheet_rows]
    preview = load_universities(rows, dry_run=True)
    checks["conflicts"] = preview["conflicts"]
    # Each as {row, name}: its row in the spreadsheet, and its name.
    result["filled_rows"] = [{"row": numbers[i], "name": rows[i]["full_name"]} for i in preview["filled_rows"]]
    result["listed_rows"] = [{"row": numbers[i], "name": rows[i]["full_name"]} for i in preview["listed_rows"]]
    # Each name given more than once: every row it's on (the first one used).
    result["repeated_rows"] = [
        {"rows": [numbers[i] for i in group], "name": rows[group[0]]["full_name"]} for group in preview["repeated"]
    ]
    result["invalid_rows"] = [numbers[i] for i in preview["invalid_rows"]]
    result["summary"].update(added=preview["added"], filled=preview["filled"], skipped=preview["skipped"])
    return result


def load_universities(rows, *, dry_run: bool = False) -> dict:
    """Add the rows' universities that aren't listed, and fill in a listed
    one's blank acronym or country. Returns the counts (``added``,
    ``filled``, ``skipped``), each ``conflicts`` line, and which rows
    (indexes into ``rows``) went which way: ``filled_rows``, ``listed_rows``
    (listed already, nothing to fill in), ``repeated`` (each name given more
    than once: all its rows, the first one used) and ``invalid_rows`` (a
    blank name, or a value too long). ``dry_run`` changes nothing."""
    listed = {university.full_name.lower(): university for university in KnownUniversity.objects.all()}
    now = timezone.now()
    new, updated, conflicts = [], [], []
    filled_rows, listed_rows, invalid_rows = [], [], []
    first_row, repeats = {}, {}
    for index, row in enumerate(rows):
        key = row["full_name"].lower()
        if not key or any(len(row[field]) > limit for field, limit in FIELD_LIMITS.items()):
            invalid_rows.append(index)
            continue
        if key in first_row:
            repeats.setdefault(key, [first_row[key]]).append(index)
            continue
        first_row[key] = index
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
            existing.updated_at = now
            updated.append(existing)
            filled_rows.append(index)
        else:
            listed_rows.append(index)

    if not dry_run:
        with transaction.atomic():
            KnownUniversity.objects.bulk_create(new, batch_size=1000)
            KnownUniversity.objects.bulk_update(updated, ["acronym", "country", "updated_at"], batch_size=1000)
    repeated_later = sum(len(group) - 1 for group in repeats.values())
    return {
        "added": len(new),
        "filled": len(updated),
        "skipped": len(listed_rows) + repeated_later + len(invalid_rows),
        "conflicts": conflicts,
        "filled_rows": filled_rows,
        "listed_rows": listed_rows,
        "repeated": list(repeats.values()),
        "invalid_rows": invalid_rows,
    }
