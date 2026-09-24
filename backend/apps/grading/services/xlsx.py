"""SAQ → XLSX export.

Client explicitly said spreadsheet is easier than PDF for SAQ marking off-
platform, so this is the primary text-export path. Shape — one row per
question:

    | group_id | group_name     (first row of the group only)
    | answer ("prompt\\nanswer") | criteria_no (blank past the rubric)
    | mark | comment            (the criterion at that position)
    | overall_comment | product_category | category_of_solution
                                (group-level, first row of the group only)

Rows cover max(questions, criteria) positions so neither an unmarked answer
nor an unanswered criterion is dropped. Marks/comments are pre-filled from
existing grades, so the sheet doubles as a fillable marking template — the
bulk-upload parser accepts this exact shape back.
"""
from __future__ import annotations

import io
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side

from ..models import Grade, GroupMarkingCategories, RubricCriterion
from .content import ComponentEntry


HEADERS = [
    "group_id",
    "group_name",
    "answer",
    "criteria_no",
    "mark",
    "comment",
    "overall_comment",
    "product_category",
    "category_of_solution",
]

# Borders on the cells a marker is expected to touch: mark/comment
# beside each criterion, and the group-level cells on the group's first
# row. Answer-only rows carry none — nothing there accepts input.
# Excel's "All Borders" (thin, black); no fill.
_THIN = Side(style="thin", color="000000")
_FILL_IN_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

_MARK_COLS = (5, 6)  # mark, comment
_GROUP_COLS = (7, 8, 9)  # overall_comment, product_category, category_of_solution


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
    the criterion at position N supplies question N's mark/comment cells.
    ``grades_by_pair`` maps ``(submission_id, criterion_id) -> Grade`` for
    pre-filling existing marks/comments. All data is pushed from the caller
    so the export layer stays ORM-free.
    """
    criteria_list = list(criteria)
    grades_by_pair = grades_by_pair or {}
    feedback_by_group = feedback_by_group or {}
    categories_by_group = categories_by_group or {}

    wb = Workbook()
    ws = wb.active
    ws.title = "SAQ"

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for entry in entries:
        cats = categories_by_group.get(entry.group_id)
        blocks = list(entry.answers)
        for i in range(1, max(len(blocks), len(criteria_list)) + 1):
            answer_cell = ""
            if i <= len(blocks):
                prompt, value = blocks[i - 1]
                answer_cell = f"{prompt}\n{value}"
            existing = None
            if i <= len(criteria_list):
                existing = grades_by_pair.get(
                    (entry.submission_id, criteria_list[i - 1].id)
                )
            first = i == 1
            ws.append([
                entry.group_id if first else "",
                entry.group_name if first else "",
                answer_cell,
                # Blank on answer-only rows past the rubric — a number here
                # would claim a criterion that does not exist.
                i if i <= len(criteria_list) else "",
                float(existing.mark) if existing and existing.mark is not None else None,
                existing.comment if existing else "",
                feedback_by_group.get(entry.group_id, "") if first else "",
                _format_product_category(cats) if first else "",
                _format_solution_category(cats) if first else "",
            ])
            row_idx = ws.max_row
            fill_cols = list(_MARK_COLS) if i <= len(criteria_list) else []
            if first:
                fill_cols += _GROUP_COLS
            for col in fill_cols:
                ws.cell(row=row_idx, column=col).border = _FILL_IN_BORDER

    # Wrap the answer column so long answers don't just spill off-screen.
    for row in ws.iter_rows(min_row=2, min_col=3, max_col=3):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws.column_dimensions["C"].width = 80
    ws.column_dimensions["F"].width = 40
    ws.column_dimensions["G"].width = 40
    ws.column_dimensions["H"].width = 28
    ws.column_dimensions["I"].width = 28

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
