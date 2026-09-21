"""SAQ → XLSX export.

Client explicitly said spreadsheet is easier than PDF for SAQ marking off-
platform, so this is the primary text-export path. Shape:

    | group_id | group_name | text
    | r1_mark | r1_comment
    | r2_mark | r2_comment | ...

One row per group; SAQ text goes in a single wrapped cell. Per-criterion
pairs (existing mark + existing comment) are appended so the sheet doubles
as a fillable marking template. Note the bulk-upload parser uses its own
long format (group_id | criterion_id | mark | comment), not this sheet.
"""
from __future__ import annotations

import io
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from ..models import Grade, RubricCriterion
from .content import ComponentEntry


BASE_HEADERS = ["group_id", "group_name", "text"]


def build_saq_xlsx(
    entries: Iterable[ComponentEntry],
    criteria: Iterable[RubricCriterion] = (),
    grades_by_pair: dict[tuple[int, int], Grade] | None = None,
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

    wb = Workbook()
    ws = wb.active
    ws.title = "SAQ"

    headers = list(BASE_HEADERS)
    for i, _ in enumerate(criteria_list, start=1):
        headers.extend([f"r{i}_mark", f"r{i}_comment"])

    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for entry in entries:
        row = [
            entry.group_id,
            entry.group_name,
            entry.text or "",
        ]
        for criterion in criteria_list:
            existing = grades_by_pair.get((entry.submission_id, criterion.id))
            row.extend([
                float(existing.mark) if existing and existing.mark is not None else None,
                existing.comment if existing else "",
            ])
        ws.append(row)

    # Wrap the text column so long SAQ answers don't just spill off-screen.
    for row in ws.iter_rows(min_row=2, min_col=3, max_col=3):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws.column_dimensions["C"].width = 80

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
