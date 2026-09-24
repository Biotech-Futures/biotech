"""SAQ → XLSX export.

Client explicitly said spreadsheet is easier than PDF for SAQ marking off-
platform, so this is the primary text-export path. Shape:

    | group_id | group_name | type ("SAQs") | text
    | product_category | category_of_solution
    | r1_mark | r1_comment
    | r2_mark | r2_comment | ...
    | overall_comment

One row per group; SAQ text goes in a single wrapped cell. Per-criterion
pairs (existing mark + existing comment) plus the overall comment are
appended, pre-filled, so the sheet doubles as a fillable marking template —
the bulk-upload parser accepts this exact shape back.
"""
from __future__ import annotations

import io
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from ..models import Grade, GroupMarkingCategories, RubricCriterion
from .content import ComponentEntry


BASE_HEADERS = ["group_id", "group_name", "type", "text", "product_category", "category_of_solution"]


def _format_product_category(cats: GroupMarkingCategories | None) -> str:
    if cats is None:
        return ""
    labels = [
        f"Other: {cats.product_category_other}"
        if label == "Other" and cats.product_category_other
        else label
        for label in (cats.product_categories or [])
    ]
    return ", ".join(labels)


def _format_solution_category(cats: GroupMarkingCategories | None) -> str:
    if cats is None:
        return ""
    label = cats.solution_category or ""
    if label == "Other" and cats.solution_category_other:
        return f"Other: {cats.solution_category_other}"
    return label


def build_saq_xlsx(
    entries: Iterable[ComponentEntry],
    criteria: Iterable[RubricCriterion] = (),
    grades_by_pair: dict[tuple[int, int], Grade] | None = None,
    feedback_by_group: dict[int, str] | None = None,
    categories_by_group: dict[int, GroupMarkingCategories] | None = None,
) -> bytes:
    """Return XLSX bytes for the given SAQ component entries.

    ``criteria`` is the ordered list of rubric criteria for the component;
    each becomes a (criterion_N_id, criterion_N_mark, criterion_N_comment)
    triplet appended to the row. ``grades_by_pair`` maps ``(submission_id,
    criterion_id) -> Grade`` for pre-filling existing marks/comments. Both
    are pushed from the caller so the export layer stays ORM-free.
    """
    criteria_list = list(criteria)
    grades_by_pair = grades_by_pair or {}
    feedback_by_group = feedback_by_group or {}
    categories_by_group = categories_by_group or {}

    wb = Workbook()
    ws = wb.active
    ws.title = "SAQ"

    headers = list(BASE_HEADERS)
    for i, _ in enumerate(criteria_list, start=1):
        headers.extend([f"r{i}_mark", f"r{i}_comment"])
    headers.append("overall_comment")

    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for entry in entries:
        cats = categories_by_group.get(entry.group_id)
        row = [
            entry.group_id,
            entry.group_name,
            "SAQs",
            entry.text or "",
            _format_product_category(cats),
            _format_solution_category(cats),
        ]
        for criterion in criteria_list:
            existing = grades_by_pair.get((entry.submission_id, criterion.id))
            row.extend([
                float(existing.mark) if existing and existing.mark is not None else None,
                existing.comment if existing else "",
            ])
        row.append(feedback_by_group.get(entry.group_id, ""))
        ws.append(row)

    # Wrap the text column so long SAQ answers don't just spill off-screen.
    for row in ws.iter_rows(min_row=2, min_col=4, max_col=4):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws.column_dimensions["D"].width = 80
    ws.column_dimensions["E"].width = 28
    ws.column_dimensions["F"].width = 28

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
