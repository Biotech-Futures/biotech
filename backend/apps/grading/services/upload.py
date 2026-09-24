"""Bulk-mark upload parser + committer.

Accepts an XLSX or CSV in the SAME wide shape the component export writes,
so admins can download the sheet, fill it in off-platform, and upload it
back. One row per group:

    group_id | group_name | r1_mark | r1_comment | r2_mark | ... | overall_comment
             | (context,  |  rN maps to the component's active-rubric      |
             |  ignored)  |  criteria in (order, id) order — the same      |
             |            |  ordering the export writes                    |

Rules:
    * The header is validated strictly: only the export's own columns are
      accepted (``group_id``, ``group_name``, ``type``, ``text``,
      ``rN_mark``/``rN_comment`` within the rubric, ``overall_comment``).
      Anything else fails the whole file — a typo like ``r1_marks`` must
      not silently drop marks.
    * ``group_id`` and ``type`` are required on every row; ``type`` must
      match the component being uploaded to ("SAQs" for SAQ, or the
      component code), so a sheet can't land in the wrong component tab.
    * Columns that are ABSENT from the sheet leave their data untouched —
      a sheet with only r1 columns never touches r2 grades, and omitting
      ``overall_comment`` leaves overall comments alone.
    * A PRESENT but blank mark+comment pair where no Grade exists is
      skipped — sparsely-filled sheets never create empty grades.
    * A present-but-blank cell where a Grade DOES exist clears it: the
      sheet is the truth for every column it carries.
    * ``overall_comment`` updates the group's :class:`ComponentFeedback`
      for this component under the same rules.
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


REQUIRED_COLUMNS = ("group_id", "type")

# Friendly ``type`` labels, matching what the export writes.
TYPE_LABELS = {"SAQ": "SAQs", "POSTER": "Poster", "REPORT": "Report", "PROTOTYPE": "Prototype"}

_RN_COLUMN = re.compile(r"^r(\d+)_(?:mark|comment)$")


def _fmt_mark(value: Decimal) -> str:
    """'5.00' -> '5', '7.50' -> '7.5' — for human-readable range hints."""
    s = str(value)
    return s.rstrip("0").rstrip(".") if "." in s else s


def _accepted_types(component_code: str) -> set[str]:
    """Lower-cased ``type`` values accepted for a component's sheet.

    Only the exact label the export writes ("SAQs", "Poster", …), compared
    case-insensitively — a bare "SAQ" is rejected as a wrong type.
    """
    return {TYPE_LABELS.get(component_code, component_code).lower()}


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
    transaction via :func:`commit_marks_upload`.
    """
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
    # typo'd header (r1_marks, Type, …) fails loudly instead of silently
    # being skipped and dropping the marks it carried. Also covers rN
    # positions beyond the rubric's size.
    # product_category / category_of_solution are informational columns the
    # export writes; accepted so the export round-trips, never parsed.
    recognized = {
        "group_id",
        "group_name",
        "type",
        "text",
        "product_category",
        "category_of_solution",
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
            problems = [c for c in REQUIRED_COLUMNS if c not in row]
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
