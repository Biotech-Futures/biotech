"""Bulk-mark upload parser + committer.

Accepts an XLSX or CSV in the SAME shape the component export writes, so
admins can download the sheet, fill it in off-platform, and upload it
back. Two shapes, dispatched by component:

* SAQ — the export's per-criterion shape described below.
* POSTER / REPORT / PROTOTYPE — the legacy wide shape, one row per group:
  ``group_id | group_name | type | r1_mark | r1_comment | … |
  overall_comment``, where ``type`` must match the component's label
  ("Poster", …) so a sheet can't land in the wrong component tab.

The SAQ shape is one row per criterion position:

    group_id | group_name | answer | criteria_no | mark | comment
             | overall_comment | product_category | category_of_solution

``criteria_no`` maps to the component's active-rubric criteria in
(order, id) order — the same ordering the export writes. ``answer``,
``product_category`` and ``category_of_solution`` are informational
export columns, accepted but never parsed.

Rules:
    * The header is validated strictly: only the export's own columns are
      accepted. Anything else fails the whole file — a typo like
      ``commet`` must not silently drop marks.
    * ``criteria_no`` is required on every row. The export writes
      ``group_id``/``group_name`` on each group's FIRST row only, so a
      blank ``group_id`` continues the group from the row above.
    * Columns that are ABSENT from the sheet leave their data untouched —
      a sheet without mark/comment columns never touches grades, and
      omitting ``overall_comment`` leaves overall comments alone.
    * A PRESENT but blank mark+comment pair where no Grade exists is
      skipped — sparsely-filled sheets never create empty grades.
    * A present-but-blank cell where a Grade DOES exist clears it: the
      sheet is the truth for every cell it carries.
    * An answer-only row (the export leaves ``criteria_no`` blank past
      the rubric) is skipped while its mark/comment stay blank, an error
      if not — likewise an explicit ``criteria_no`` beyond the rubric.
    * ``overall_comment`` is group-level: it is read from each group's
      FIRST row only (where the export writes it) and updates the group's
      :class:`ComponentFeedback` for this component under the same rules.
"""
from __future__ import annotations

import csv
import difflib
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Iterable

from django.db import transaction
from openpyxl import load_workbook

from ..models import ComponentFeedback, Grade, RubricCriterion, SubmissionComponent
from .content import submission_entries


CRITERIA_REQUIRED_COLUMNS = ("group_id", "criteria_no")
WIDE_REQUIRED_COLUMNS = ("group_id", "type")

# Friendly ``type`` labels for the wide shape, matching what the old
# export wrote.
TYPE_LABELS = {"SAQ": "SAQs", "POSTER": "Poster", "REPORT": "Report", "PROTOTYPE": "Prototype"}

_RN_COLUMN = re.compile(r"^r(\d+)_(?:mark|comment)$")


def _accepted_types(component_code: str) -> set[str]:
    """Lower-cased ``type`` values accepted for a wide-shape sheet.

    Only the exact label the export writes ("Poster", …), compared
    case-insensitively — a bare "POSTER" is rejected as a wrong type.
    """
    return {TYPE_LABELS.get(component_code, component_code).lower()}


def _fmt_mark(value: Decimal) -> str:
    """'5.00' -> '5', '7.50' -> '7.5' — for human-readable range hints."""
    s = str(value)
    return s.rstrip("0").rstrip(".") if "." in s else s


@dataclass
class UploadDiff:
    creates: list[dict] = field(default_factory=list)
    updates: list[dict] = field(default_factory=list)
    unchanged: list[dict] = field(default_factory=list)
    overall_comments: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    # Categorised validation report for the preview dialog: header problems,
    # sheet type, bad group rows, bad mark cells. See parse_marks_upload.
    checks: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "creates": len(self.creates),
            "updates": len(self.updates),
            "unchanged": len(self.unchanged),
            "overall_comments": len(self.overall_comments),
            "errors": len(self.errors),
        }

    def as_dict(self) -> dict:
        return {
            "creates": self.creates,
            "updates": self.updates,
            "unchanged": self.unchanged,
            "overall_comments": self.overall_comments,
            "errors": self.errors,
            "checks": self.checks,
            "summary": self.summary(),
        }


def _iter_rows(file, filename: str) -> Iterable[tuple[int, dict]]:
    """Yield ``(row_number, row_dict)`` for XLSX or CSV inputs.

    Row numbers are 1-indexed and include the header, matching what admins
    see in Excel — makes error messages actionable ("row 12 has a bad mark").
    """
    name = (filename or "").lower()
    if name.endswith(".csv"):
        content = file.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        for i, row in enumerate(reader, start=2):
            yield i, {k.strip(): (v or "").strip() for k, v in row.items() if k}
        return

    # Default: XLSX (openpyxl). Handle both first-row-header and normalised keys.
    wb = load_workbook(file, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        return
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if not header:
        return
    keys = [str(h).strip() if h is not None else "" for h in header]
    for i, values in enumerate(rows_iter, start=2):
        row = {}
        for k, v in zip(keys, values):
            if not k:
                continue
            if v is None:
                row[k] = ""
            else:
                row[k] = str(v).strip() if not isinstance(v, str) else v.strip()
        # Skip fully-empty rows (Excel often pads with blank rows after data).
        if not any(row.values()):
            continue
        yield i, row


def _parse_int(value: str) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_mark(value: str) -> tuple[Decimal | None, str | None]:
    """Return (decimal_mark_or_null, error_message_or_null).

    Blank/empty value is a legitimate "clear the mark" and returns (None, None).
    """
    s = str(value or "").strip()
    if s == "":
        return None, None
    try:
        return Decimal(s), None
    except InvalidOperation:
        return None, f"mark {s!r} is not a valid number"


def parse_marks_upload(file, filename: str, component_code: str) -> UploadDiff:
    """Materialise a diff for the given upload against a component's rubric.

    Pure read — no database writes. Callers use ``dry_run`` semantics: show
    the diff to the admin, get confirmation, then re-parse + commit in one
    transaction via :func:`commit_marks_upload`. SAQ sheets use the
    per-criterion shape; every other component keeps the legacy wide shape.
    """
    if component_code == "SAQ":
        return _parse_criteria_upload(file, filename, component_code)
    return _parse_wide_upload(file, filename, component_code)


def _parse_criteria_upload(file, filename: str, component_code: str) -> UploadDiff:
    """The SAQ export's per-criterion shape (see module docstring)."""
    diff = UploadDiff()
    diff.checks = {
        "missing_headers": [],
        "bad_group_rows": [],
        "bad_marks": [],
    }

    component = SubmissionComponent.objects.filter(code=component_code).first()
    if component is None:
        diff.errors.append({"row": 0, "message": f"unknown component {component_code}"})
        return diff

    # Position -> criterion, in the same (order, id) ordering the export
    # writes its rN_mark / rN_comment columns in.
    ordered_criteria = list(
        RubricCriterion.objects.filter(
            rubric__component__code=component_code, rubric__active=True
        ).order_by("order", "id")
    )
    if not ordered_criteria:
        diff.errors.append({"row": 0, "message": f"no rubric criteria exist for component {component_code}"})
        return diff

    # Groups with submitted content for this component -> their entry's
    # submission id (the Grade anchor; one id spans the whole entry) and
    # name (validated against the sheet so a swapped/typo'd row is caught).
    entries = list(submission_entries(component_code=component_code))
    submissions_by_group = {e.group_id: e.submission_id for e in entries}
    names_by_group = {e.group_id: e.group_name for e in entries}
    grades_by_pair: dict[tuple[int, int], Grade] = {
        (g.submission.group_id, g.criterion_id): g
        for g in Grade.objects.filter(
            criterion__rubric__component__code=component_code,
        ).select_related("submission", "criterion")
    }
    feedback_by_group = {
        row["group_id"]: row["comment"]
        for row in ComponentFeedback.objects.filter(component=component).values(
            "group_id", "comment"
        )
    }

    # Strict header check: only the export's own columns are accepted, so a
    # typo'd header (commet, Mark, …) fails loudly instead of silently
    # being skipped and dropping the marks it carried.
    # answer / product_category / category_of_solution are informational
    # columns the export writes; accepted so the export round-trips, never
    # parsed.
    recognized = {
        "group_id",
        "group_name",
        "answer",
        "criteria_no",
        "mark",
        "comment",
        "overall_comment",
        "product_category",
        "category_of_solution",
    }

    seen_cells: set[tuple[int, int]] = set()
    overall_seen: set[int] = set()
    current_group_id: int | None = None
    header_checked = False

    for row_num, row in _iter_rows(file, filename):
        if not header_checked:
            header_checked = True
            # Header problems (uniform across the file). A typo'd header is
            # reported by the EXPECTED name it displaced ("commen" ->
            # "comment"), matched fuzzily against recognised headers the
            # sheet lacks; unmatchable extras are named as-is.
            problems = [c for c in CRITERIA_REQUIRED_COLUMNS if c not in row]
            absent_recognized = sorted(h for h in recognized if h not in row)
            for key in sorted(k for k in row if k not in recognized):
                match = difflib.get_close_matches(key, absent_recognized, n=1, cutoff=0.6)
                problems.append(match[0] if match else key)
            seen_problems: set[str] = set()
            problems = [p for p in problems if not (p in seen_problems or seen_problems.add(p))]
            if problems:
                diff.checks["missing_headers"] = problems
                diff.errors.append({
                    "row": 1,
                    "message": (
                        f"column header problem(s): {', '.join(problems)}. "
                        f"Accepted: group_id, group_name, answer, criteria_no, "
                        f"mark, comment, overall_comment, product_category, "
                        f"category_of_solution"
                    ),
                })
                return diff

        raw_group_id = str(row.get("group_id", "") or "").strip()
        if raw_group_id:
            group_id = _parse_int(raw_group_id)
            if group_id is None:
                diff.checks["bad_group_rows"].append({"row": row_num, "reason": "group_id is not a number"})
                diff.errors.append({"row": row_num, "message": "group_id must be an integer"})
                continue
            current_group_id = group_id
        elif current_group_id is not None:
            # The export writes group_id on each group's first row only;
            # a blank cell continues the group above.
            group_id = current_group_id
        else:
            diff.checks["bad_group_rows"].append({"row": row_num, "reason": "group_id is blank"})
            diff.errors.append({"row": row_num, "message": "group_id is blank and no earlier row names a group"})
            continue

        raw_criteria_no = str(row.get("criteria_no", "") or "").strip()
        if not raw_criteria_no:
            # An answer-only row past the rubric: the export leaves its
            # criteria_no blank. Fine while its mark/comment stay blank —
            # there is no criterion for them to land on.
            if str(row.get("mark", "") or "").strip() or (row.get("comment", "") or ""):
                diff.checks["bad_marks"].append({
                    "row": row_num,
                    "column": "mark",
                    "hint": "row has no criteria_no",
                })
                diff.errors.append({
                    "row": row_num,
                    "message": "mark/comment given on a row with no criteria_no",
                })
            continue

        criteria_no = _parse_int(raw_criteria_no)
        if criteria_no is None or criteria_no < 1:
            diff.checks["bad_group_rows"].append({"row": row_num, "reason": "criteria_no is not a positive number"})
            diff.errors.append({"row": row_num, "message": "criteria_no must be a positive integer"})
            continue

        if (group_id, criteria_no) in seen_cells:
            diff.checks["bad_group_rows"].append({
                "row": row_num,
                "reason": f"duplicate of group {group_id} criteria {criteria_no}",
            })
            diff.errors.append({
                "row": row_num,
                "message": f"duplicate row for group_id={group_id} criteria_no={criteria_no}",
            })
            continue
        seen_cells.add((group_id, criteria_no))

        submission_id = submissions_by_group.get(group_id)
        if submission_id is None:
            diff.checks["bad_group_rows"].append({"row": row_num, "reason": f"group {group_id} has no submission"})
            diff.errors.append({"row": row_num, "message": f"group {group_id} has no {component_code} submission to grade"})
            continue

        # When the sheet carries group_name, it must match the id's actual
        # group — catches a row whose id was edited onto the wrong group.
        given_name = (row.get("group_name") or "").strip()
        if "group_name" in row and given_name and given_name != names_by_group.get(group_id):
            diff.checks["bad_group_rows"].append({
                "row": row_num,
                "reason": f"name should be {names_by_group.get(group_id)!r}",
            })
            diff.errors.append({
                "row": row_num,
                "message": (
                    f"group_name {given_name!r} does not match group "
                    f"{group_id} ({names_by_group.get(group_id)!r})"
                ),
            })
            continue

        # overall_comment is group-level: read from the group's FIRST row
        # only (where the export writes it), and only when the column
        # exists — its absence means "don't touch". Later rows carry blank
        # cells that must not read as a "clear".
        if "overall_comment" in row and group_id not in overall_seen:
            overall_seen.add(group_id)
            new_comment = row.get("overall_comment", "") or ""
            if new_comment != (feedback_by_group.get(group_id) or ""):
                diff.overall_comments.append({
                    "row": row_num,
                    "group_id": group_id,
                    "component_id": component.id,
                    "comment": new_comment,
                    "old_comment": feedback_by_group.get(group_id) or "",
                })

        # Columns absent from the sheet entirely -> grades untouched. Only
        # a PRESENT but blank cell clears an existing grade.
        if "mark" not in row and "comment" not in row:
            continue

        comment = row.get("comment", "") or ""
        if criteria_no > len(ordered_criteria):
            # An answer-only row past the rubric (the export writes these
            # when there are more questions than criteria). Fine while its
            # mark/comment stay blank — there is no criterion to land on.
            if str(row.get("mark", "") or "").strip() or comment:
                diff.checks["bad_marks"].append({
                    "row": row_num,
                    "column": "mark",
                    "hint": f"rubric has only {len(ordered_criteria)} criteria",
                })
                diff.errors.append({
                    "row": row_num,
                    "message": f"criteria_no {criteria_no}: rubric has only {len(ordered_criteria)} criteria",
                })
            continue

        criterion = ordered_criteria[criteria_no - 1]
        range_hint = f"should be 0 to {_fmt_mark(criterion.max_mark)}"
        mark, err = _parse_mark(row.get("mark", ""))
        if err:
            diff.checks["bad_marks"].append({"row": row_num, "column": "mark", "hint": "not a number"})
            diff.errors.append({"row": row_num, "message": f"mark: {err}"})
            continue
        if mark is not None and (mark < Decimal("0") or mark > criterion.max_mark):
            diff.checks["bad_marks"].append({"row": row_num, "column": "mark", "hint": range_hint})
            diff.errors.append({"row": row_num, "message": f"mark {mark} {range_hint}"})
            continue

        existing = grades_by_pair.get((group_id, criterion.id))
        if existing is None and mark is None and not comment:
            # Nothing there, nothing given — not a "clear", just untouched.
            continue

        entry = {
            "row": row_num,
            "group_id": group_id,
            "criterion_id": criterion.id,
            "criteria_no": criteria_no,
            "submission_id": submission_id,
            "mark": str(mark) if mark is not None else None,
            "comment": comment,
        }
        if existing is None:
            diff.creates.append(entry)
        elif existing.mark == mark and (existing.comment or "") == comment:
            diff.unchanged.append({**entry, "grade_id": existing.id})
        else:
            # Name the sheet columns whose values actually differ, so the
            # preview can say what an overwrite touches.
            changed_columns = []
            if existing.mark != mark:
                changed_columns.append("mark")
            if (existing.comment or "") != comment:
                changed_columns.append("comment")
            diff.updates.append({
                **entry,
                "grade_id": existing.id,
                "group_name": names_by_group.get(group_id),
                "columns": changed_columns,
                "old_mark": str(existing.mark) if existing.mark is not None else None,
                "old_comment": existing.comment or "",
            })

    return diff


def _parse_wide_upload(file, filename: str, component_code: str) -> UploadDiff:
    """The legacy wide shape for POSTER/REPORT/PROTOTYPE: one row per
    group, ``type`` column, ``rN_mark``/``rN_comment`` per criterion."""
    diff = UploadDiff()
    diff.checks = {
        "missing_headers": [],
        "expected_type": TYPE_LABELS.get(component_code, component_code),
        "found_type": None,
        "type_ok": True,
        "bad_group_rows": [],
        "bad_marks": [],
    }

    component = SubmissionComponent.objects.filter(code=component_code).first()
    if component is None:
        diff.errors.append({"row": 0, "message": f"unknown component {component_code}"})
        return diff

    # Position -> criterion, in the same (order, id) ordering the export
    # writes its rN_mark / rN_comment columns in.
    ordered_criteria = list(
        RubricCriterion.objects.filter(
            rubric__component__code=component_code, rubric__active=True
        ).order_by("order", "id")
    )
    if not ordered_criteria:
        diff.errors.append({"row": 0, "message": f"no rubric criteria exist for component {component_code}"})
        return diff

    entries = list(submission_entries(component_code=component_code))
    submissions_by_group = {e.group_id: e.submission_id for e in entries}
    names_by_group = {e.group_id: e.group_name for e in entries}
    grades_by_pair: dict[tuple[int, int], Grade] = {
        (g.submission.group_id, g.criterion_id): g
        for g in Grade.objects.filter(
            criterion__rubric__component__code=component_code,
        ).select_related("submission", "criterion")
    }
    feedback_by_group = {
        row["group_id"]: row["comment"]
        for row in ComponentFeedback.objects.filter(component=component).values(
            "group_id", "comment"
        )
    }

    # Strict header check: only the wide shape's own columns are accepted.
    recognized = {
        "group_id",
        "group_name",
        "type",
        "text",
        "overall_comment",
    }
    for i in range(1, len(ordered_criteria) + 1):
        recognized.add(f"r{i}_mark")
        recognized.add(f"r{i}_comment")

    seen_groups: set[int] = set()
    header_checked = False

    for row_num, row in _iter_rows(file, filename):
        if not header_checked:
            header_checked = True
            # Header problems (uniform across the file). A typo'd header is
            # reported by the EXPECTED name it displaced ("r1_commen" ->
            # "r1_comment"), matched fuzzily against recognised headers the
            # sheet lacks; rN names beyond the rubric and unmatchable extras
            # are named as-is.
            problems = [c for c in WIDE_REQUIRED_COLUMNS if c not in row]
            absent_recognized = sorted(h for h in recognized if h not in row)
            for key in sorted(k for k in row if k not in recognized):
                if _RN_COLUMN.match(key):
                    problems.append(key)
                    continue
                match = difflib.get_close_matches(key, absent_recognized, n=1, cutoff=0.6)
                problems.append(match[0] if match else key)
            seen_problems: set[str] = set()
            problems = [p for p in problems if not (p in seen_problems or seen_problems.add(p))]
            if "type" in row:
                diff.checks["found_type"] = (row.get("type") or "").strip() or None
            if problems:
                diff.checks["missing_headers"] = problems
                diff.errors.append({
                    "row": 1,
                    "message": (
                        f"column header problem(s): {', '.join(problems)}. "
                        f"Accepted: group_id, group_name, type, text, "
                        f"r1..r{len(ordered_criteria)}_mark/_comment, overall_comment"
                    ),
                })
                return diff

        row_type = (row.get("type") or "").strip()
        if row_type.lower() not in _accepted_types(component_code):
            if diff.checks["type_ok"]:
                diff.checks["type_ok"] = False
                diff.checks["found_type"] = row_type or None
            diff.errors.append({
                "row": row_num,
                "message": f"type {row_type!r} does not match component {component_code}",
            })
            continue

        group_id = _parse_int(row["group_id"])
        if group_id is None:
            diff.checks["bad_group_rows"].append({"row": row_num, "reason": "group_id is not a number"})
            diff.errors.append({"row": row_num, "message": "group_id must be an integer"})
            continue

        if group_id in seen_groups:
            diff.checks["bad_group_rows"].append({"row": row_num, "reason": f"duplicate of group {group_id}"})
            diff.errors.append({"row": row_num, "message": f"duplicate row for group_id={group_id}"})
            continue
        seen_groups.add(group_id)

        submission_id = submissions_by_group.get(group_id)
        if submission_id is None:
            diff.checks["bad_group_rows"].append({"row": row_num, "reason": f"group {group_id} has no submission"})
            diff.errors.append({"row": row_num, "message": f"group {group_id} has no {component_code} submission to grade"})
            continue

        # When the sheet carries group_name, it must match the id's actual
        # group — catches a row whose id was edited onto the wrong group.
        given_name = (row.get("group_name") or "").strip()
        if "group_name" in row and given_name and given_name != names_by_group.get(group_id):
            diff.checks["bad_group_rows"].append({
                "row": row_num,
                "reason": f"name should be {names_by_group.get(group_id)!r}",
            })
            diff.errors.append({
                "row": row_num,
                "message": (
                    f"group_name {given_name!r} does not match group "
                    f"{group_id} ({names_by_group.get(group_id)!r})"
                ),
            })
            continue

        for i, criterion in enumerate(ordered_criteria, start=1):
            # Column absent from the sheet entirely -> this criterion is
            # untouched (same rule as overall_comment). Only a PRESENT but
            # blank cell clears an existing grade.
            if f"r{i}_mark" not in row and f"r{i}_comment" not in row:
                continue
            range_hint = f"should be 0 to {_fmt_mark(criterion.max_mark)}"
            mark, err = _parse_mark(row.get(f"r{i}_mark", ""))
            if err:
                diff.checks["bad_marks"].append({"row": row_num, "column": f"r{i}_mark", "hint": "not a number"})
                diff.errors.append({"row": row_num, "message": f"r{i}_mark: {err}"})
                continue
            if mark is not None and (mark < Decimal("0") or mark > criterion.max_mark):
                diff.checks["bad_marks"].append({"row": row_num, "column": f"r{i}_mark", "hint": range_hint})
                diff.errors.append({"row": row_num, "message": f"r{i}_mark {mark} {range_hint}"})
                continue

            comment = row.get(f"r{i}_comment", "") or ""
            existing = grades_by_pair.get((group_id, criterion.id))
            if existing is None and mark is None and not comment:
                # Nothing there, nothing given — not a "clear", just untouched.
                continue

            entry = {
                "row": row_num,
                "group_id": group_id,
                "criterion_id": criterion.id,
                "submission_id": submission_id,
                "mark": str(mark) if mark is not None else None,
                "comment": comment,
            }
            if existing is None:
                diff.creates.append(entry)
            elif existing.mark == mark and (existing.comment or "") == comment:
                diff.unchanged.append({**entry, "grade_id": existing.id})
            else:
                # Name the sheet columns whose values actually differ, so the
                # preview can say what an overwrite touches.
                changed_columns = []
                if existing.mark != mark:
                    changed_columns.append(f"r{i}_mark")
                if (existing.comment or "") != comment:
                    changed_columns.append(f"r{i}_comment")
                diff.updates.append({
                    **entry,
                    "grade_id": existing.id,
                    "group_name": names_by_group.get(group_id),
                    "columns": changed_columns,
                    "old_mark": str(existing.mark) if existing.mark is not None else None,
                    "old_comment": existing.comment or "",
                })

        # Only when the column exists — its absence means "don't touch".
        if "overall_comment" in row:
            new_comment = row.get("overall_comment", "") or ""
            if new_comment != (feedback_by_group.get(group_id) or ""):
                diff.overall_comments.append({
                    "row": row_num,
                    "group_id": group_id,
                    "component_id": component.id,
                    "comment": new_comment,
                    "old_comment": feedback_by_group.get(group_id) or "",
                })

    return diff


@transaction.atomic
def commit_marks_upload(diff: UploadDiff, *, user) -> dict:
    """Apply the ``creates``, ``updates`` and ``overall_comments`` from a
    validated diff.

    Callers must pre-check ``diff.errors`` is empty — the endpoint refuses to
    commit anything if any row failed validation, so partial imports can't
    happen. ``unchanged`` rows are skipped (no-op, no re-stamping ``graded_by``
    just to record the same value).
    """
    written = 0
    for entry in list(diff.creates) + list(diff.updates):
        Grade.objects.update_or_create(
            submission_id=entry["submission_id"],
            criterion_id=entry["criterion_id"],
            defaults={
                "mark": Decimal(entry["mark"]) if entry["mark"] is not None else None,
                "comment": entry["comment"] or "",
                "graded_by": user,
            },
        )
        written += 1
    for entry in diff.overall_comments:
        ComponentFeedback.objects.update_or_create(
            group_id=entry["group_id"],
            component_id=entry["component_id"],
            defaults={"comment": entry["comment"], "updated_by": user},
        )
        written += 1
    return {"written": written, **diff.summary()}
