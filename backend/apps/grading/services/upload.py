"""Bulk-mark upload parser + committer.

Accepts an XLSX or CSV in the SAME shape the component export writes, so
admins can download the sheet, fill it in off-platform, and upload it
back. Every component uses one shape, one row per group:

    group_id | group_name | type | [q1 | q2 | …]
             | r1_mark | r1_comment | r2_mark | r2_comment | …
             | overall_comment | [product_category | category_of_solution]

``type`` must match the component's label ("SAQs", "Poster", …) so a sheet
can't land in the wrong component tab. ``rN`` maps to the component's
active-rubric criteria in (order, id) order, the same ordering the export
writes. The SAQ export's ``qN`` answer columns are informational, accepted
but never parsed. ``product_category`` / ``category_of_solution`` (written
by the SAQ export) update the group's marking key selections, parsed back
from the export's own formatting: known options by name, anything else as
the Other text ("Health and Medicine, Wearables" / "App").

Rules:
    * Missing required headers fail the file: ``group_id``, ``type`` and
      every ``rN_mark``/``rN_comment`` of the rubric. Unrecognised extra
      columns are simply ignored.
    * ``overall_comment`` and the two category columns are optional —
      omitting one leaves what it would set alone.
    * A PRESENT but blank mark+comment pair where no Grade exists is
      skipped — sparsely-filled sheets never create empty grades.
    * A present-but-blank cell where a Grade DOES exist clears it: the
      sheet is the truth for every cell it carries.
    * ``overall_comment`` updates the group's :class:`ComponentFeedback`
      for this component under the same rules.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Iterable

from django.db import transaction
from openpyxl import load_workbook

from ..models import (
    ComponentFeedback,
    Grade,
    GroupMarkingCategories,
    RubricCriterion,
    SubmissionComponent,
)
from .content import submission_entries


WIDE_REQUIRED_COLUMNS = ("group_id", "type")

# Friendly ``type`` labels, matching what the export writes.
TYPE_LABELS = {"SAQ": "SAQs", "POSTER": "Poster", "REPORT": "Report", "PROTOTYPE": "Prototype"}


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


# The marking key's fixed options — mirrors PRODUCT_OPTIONS /
# SOLUTION_OPTIONS in frontend MarkingCategories.vue. Sheet values are
# matched case-insensitively to these; anything unrecognised lands in
# "Other" so no value the sheet carries can become invisible in the UI.
PRODUCT_CATEGORY_OPTIONS = [
    "Health and Medicine",
    "Sustainable Environment",
    "Emerging Technologies",
    "Regulation Ethics",
]
SOLUTION_CATEGORY_OPTIONS = ["Product/Device", "Technique/Method", "Treatment"]
_PRODUCT_BY_LOWER = {o.lower(): o for o in PRODUCT_CATEGORY_OPTIONS}
_SOLUTION_BY_LOWER = {o.lower(): o for o in SOLUTION_CATEGORY_OPTIONS}


def _parse_product_category(value: str) -> tuple[list[str], str]:
    """Inverse of the export's formatting: "Health and Medicine, Wearables"
    -> (["Health and Medicine", "Other"], "Wearables"). Known options match
    by name, a bare "Other" ticks Other alone, and anything else becomes the
    Other text."""
    labels: list[str] = []
    others: list[str] = []
    for part in (p.strip() for p in str(value or "").split(",")):
        if not part:
            continue
        if part.lower() == "other":
            if "Other" not in labels:
                labels.append("Other")
        elif part.lower() in _PRODUCT_BY_LOWER:
            canonical = _PRODUCT_BY_LOWER[part.lower()]
            if canonical not in labels:
                labels.append(canonical)
        else:
            others.append(part)
    other = ", ".join(o for o in others if o)
    if other and "Other" not in labels:
        labels.append("Other")
    return labels, other


def _parse_solution_category(value: str) -> tuple[str, str]:
    """Inverse of the export's formatting: "App" -> ("Other", "App"). A known
    option matches by name, a bare "Other" picks Other alone, and anything
    else becomes the Other text."""
    s = str(value or "").strip()
    if not s:
        return "", ""
    if s.lower() == "other":
        return "Other", ""
    if s.lower() in _SOLUTION_BY_LOWER:
        return _SOLUTION_BY_LOWER[s.lower()], ""
    return "Other", s


@dataclass
class UploadDiff:
    creates: list[dict] = field(default_factory=list)
    updates: list[dict] = field(default_factory=list)
    unchanged: list[dict] = field(default_factory=list)
    overall_comments: list[dict] = field(default_factory=list)
    marking_categories: list[dict] = field(default_factory=list)
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
            "marking_categories": len(self.marking_categories),
            "errors": len(self.errors),
        }

    def as_dict(self) -> dict:
        return {
            "creates": self.creates,
            "updates": self.updates,
            "unchanged": self.unchanged,
            "overall_comments": self.overall_comments,
            "marking_categories": self.marking_categories,
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
    transaction via :func:`commit_marks_upload`. Every component uses the
    one-row-per-group shape described in the module docstring.
    """
    return _parse_wide_upload(file, filename, component_code)


def _parse_wide_upload(file, filename: str, component_code: str) -> UploadDiff:
    """One row per group: ``type`` column, ``rN_mark``/``rN_comment`` per
    criterion, then the optional group-level columns."""
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
    categories_by_group = {
        c.group_id: c
        for c in GroupMarkingCategories.objects.filter(group_id__in=submissions_by_group)
    }

    seen_groups: set[int] = set()
    header_checked = False

    for row_num, row in _iter_rows(file, filename):
        if not header_checked:
            header_checked = True
            # Missing means MISSING: only required headers the sheet lacks
            # are reported. Unrecognised extra columns are ignored. Every
            # rubric position's mark/comment pair is required.
            required = list(WIDE_REQUIRED_COLUMNS)
            for i in range(1, len(ordered_criteria) + 1):
                required += [f"r{i}_mark", f"r{i}_comment"]
            problems = [c for c in required if c not in row]
            if "type" in row:
                diff.checks["found_type"] = (row.get("type") or "").strip() or None
            if problems:
                diff.checks["missing_headers"] = problems
                diff.errors.append({
                    "row": 1,
                    "message": f"missing column header(s): {', '.join(problems)}",
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
                    "group_name": names_by_group.get(group_id),
                    "component_id": component.id,
                    "comment": new_comment,
                    "old_comment": feedback_by_group.get(group_id) or "",
                })

        # Marking key selections, only when their columns exist. A
        # column-absent half keeps its stored value.
        if "product_category" in row or "category_of_solution" in row:
            stored = categories_by_group.get(group_id)
            old = (
                list(stored.product_categories or []) if stored else [],
                (stored.product_category_other or "") if stored else "",
                (stored.solution_category or "") if stored else "",
                (stored.solution_category_other or "") if stored else "",
            )
            new_products, new_product_other, new_solution, new_solution_other = old
            if "product_category" in row:
                new_products, new_product_other = _parse_product_category(
                    row.get("product_category", "")
                )
            if "category_of_solution" in row:
                new_solution, new_solution_other = _parse_solution_category(
                    row.get("category_of_solution", "")
                )
            # Product categories are a set: the same boxes in another order
            # are no change.
            columns = []
            if (sorted(new_products), new_product_other) != (sorted(old[0]), old[1]):
                columns.append("product_category")
            if (new_solution, new_solution_other) != (old[2], old[3]):
                columns.append("category_of_solution")
            if columns:
                # A column whose stored value was not blank is overwritten
                # (replaced or cleared); otherwise it is written for the first time.
                had_value = {
                    "product_category": bool(old[0] or old[1]),
                    "category_of_solution": bool(old[2] or old[3]),
                }
                diff.marking_categories.append({
                    "row": row_num,
                    "group_id": group_id,
                    "group_name": names_by_group.get(group_id),
                    "columns": columns,
                    "overwritten_columns": [c for c in columns if had_value[c]],
                    "product_categories": new_products,
                    "product_category_other": new_product_other,
                    "solution_category": new_solution,
                    "solution_category_other": new_solution_other,
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
    for entry in diff.marking_categories:
        GroupMarkingCategories.objects.update_or_create(
            group_id=entry["group_id"],
            defaults={
                "product_categories": entry["product_categories"],
                "product_category_other": entry["product_category_other"],
                "solution_category": entry["solution_category"],
                "solution_category_other": entry["solution_category_other"],
                "updated_by": user,
            },
        )
        written += 1
    return {"written": written, **diff.summary()}
