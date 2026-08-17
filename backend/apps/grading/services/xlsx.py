"""SAQ → XLSX export.

Client explicitly said spreadsheet is easier than PDF for SAQ marking off-
platform, so this is the primary text-export path. Shape:

    | group_id | group_name | submitted_at | is_late | text |

One row per group; SAQ text goes in a single wrapped cell. If SAQ questions
are later split into multiple fields (spec allows for it), extend by adding
one column per question — this shape stays the base.
"""
from __future__ import annotations

import io
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from apps.submissions.models import Submission


HEADERS = ["group_id", "group_name", "submitted_at", "is_late", "text"]


def build_saq_xlsx(submissions: Iterable[Submission]) -> bytes:
    """Return XLSX bytes for the given SAQ submissions.

    Caller passes an already-filtered iterable — the service doesn't reach
    back into the ORM. Keeps it easy to test and easy to reuse for slices
    (e.g. one group's SAQ, or a subset of groups) without leaking filtering
    logic into the export layer.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "SAQ"

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for submission in submissions:
        ws.append([
            submission.group_id,
            submission.group.group_name,
            submission.submitted_at.isoformat() if submission.submitted_at else "",
            "yes" if submission.is_late else "",
            submission.text or "",
        ])

    # Wrap the text column so long SAQ answers don't just spill off-screen.
    for row in ws.iter_rows(min_row=2, min_col=5, max_col=5):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["E"].width = 80

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
