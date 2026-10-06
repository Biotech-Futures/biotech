"""SAQ → XLSX export.

Client explicitly said spreadsheet is easier than PDF for SAQ marking off-
platform, so this is the primary text-export path. Shape — one row per
group:

    | year | group_name | type ("SAQs") | project_title   (year: the team's challenge year)
    | q1 | q2 | …            (each answer under its question, in bold)
    | product_category | category_of_solution
    | r1_mark | r1_comment | r2_mark | r2_comment | …   (one pair per criterion)
    | overall_comment

Teams come in natural order, as the rest of the app lists them: BTF2
before BTF10. ``qN`` columns line up by question across groups (a group that skipped an
optional question gets a blank cell), in the questions' form order. Marks
and comments are pre-filled from existing grades. The bulk upload identifies
teams by a ``group_id`` column, which this sheet no longer carries.
"""
from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation
from typing import Iterable

from openpyxl import Workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from ..models import Grade, GroupMarkingCategories, RubricCriterion
from .content import ComponentEntry
from .text import natural_key, xml_safe
from .upload import TYPE_LABELS


def format_product_category(cats: GroupMarkingCategories | None) -> str:
    """The ticked options, with Other's text written in its place as plain
    text ("Health and Medicine, Wearables"); a bare "Other" when it has none."""
    if cats is None:
        return ""
    labels = [
        cats.product_category_other
        if label == "Other" and cats.product_category_other
        else label
        for label in (cats.product_categories or [])
    ]
    return ", ".join(labels)


def format_solution_category(cats: GroupMarkingCategories | None) -> str:
    """The picked option, or Other's text as plain text ("App")."""
    if cats is None:
        return ""
    label = cats.solution_category or ""
    if label == "Other" and cats.solution_category_other:
        return cats.solution_category_other
    return label


QUESTION_COLUMN_WIDTH = 43
COMMENT_COLUMN_WIDTH = 30


def _text(value):
    """A cell's text with the characters a spreadsheet can't hold cleaned out
    (see ``text.xml_safe``); anything else as it is."""
    return xml_safe(value) if isinstance(value, str) else value


def _answer_cell(prompt: str, answer: str) -> CellRichText:
    """The question in bold, the team's answer on the line below it. Uploads
    read the cell back as plain text (and never parse it)."""
    return CellRichText(TextBlock(InlineFont(b=True), xml_safe(prompt)), f"\n{xml_safe(answer)}")


def _question_columns(entries: list[ComponentEntry], questions: Iterable[str]) -> list[str]:
    """Prompts that get a ``qN`` column, in order.

    Known questions come first in form order (``questions``), keeping only
    those some group answered; answers under a retired question (labelled by
    their raw key) follow in first-seen order, so nothing is dropped.
    """
    answered = [prompt for entry in entries for prompt, _ in entry.answers]
    answered_set = set(answered)
    columns = [prompt for prompt in dict.fromkeys(questions) if prompt in answered_set]
    known = set(columns)
    columns += [prompt for prompt in dict.fromkeys(answered) if prompt not in known]
    return columns


def build_saq_xlsx(
    entries: Iterable[ComponentEntry],
    criteria: Iterable[RubricCriterion] = (),
    grades_by_pair: dict[tuple[int, int], Grade] | None = None,
    feedback_by_group: dict[int, str] | None = None,
    categories_by_group: dict[int, GroupMarkingCategories] | None = None,
    questions: Iterable[str] = (),
    years_by_group: dict[int, int] | None = None,
) -> bytes:
    """Return XLSX bytes for the given SAQ component entries.

    ``criteria`` is the ordered list of rubric criteria for the component;
    criterion N fills the ``rN_mark`` / ``rN_comment`` pair. ``questions``
    is every question prompt in form order, which fixes the ``qN`` column
    order. ``grades_by_pair`` maps ``(submission_id, criterion_id) -> Grade``
    for pre-filling existing marks/comments. ``years_by_group`` maps a group
    id to its challenge year for the ``year`` column. All data is pushed from
    the caller so the export layer stays ORM-free.
    """
    entries = sorted(entries, key=lambda entry: (natural_key(entry.group_name), entry.group_id))
    criteria_list = list(criteria)
    grades_by_pair = grades_by_pair or {}
    feedback_by_group = feedback_by_group or {}
    categories_by_group = categories_by_group or {}
    years_by_group = years_by_group or {}
    prompts = _question_columns(entries, questions)

    headers = ["year", "group_name", "type", "project_title"]
    headers += [f"q{i}" for i in range(1, len(prompts) + 1)]
    headers += ["product_category", "category_of_solution"]
    for i in range(1, len(criteria_list) + 1):
        headers += [f"r{i}_mark", f"r{i}_comment"]
    headers += ["overall_comment"]

    wb = Workbook()
    ws = wb.active
    ws.title = "SAQ"

    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for entry in entries:
        cats = categories_by_group.get(entry.group_id)
        answers = dict(entry.answers)
        row = [years_by_group.get(entry.group_id), entry.group_name, TYPE_LABELS["SAQ"], entry.project_title]
        row += [
            _answer_cell(prompt, answers[prompt]) if prompt in answers else ""
            for prompt in prompts
        ]
        row += [format_product_category(cats), format_solution_category(cats)]
        for criterion in criteria_list:
            existing = grades_by_pair.get((entry.submission_id, criterion.id))
            row += [
                float(existing.mark) if existing and existing.mark is not None else None,
                existing.comment if existing else "",
            ]
        row.append(feedback_by_group.get(entry.group_id, ""))
        ws.append([_text(value) for value in row])

    # Answers, comments, the title and the category columns wrap in fixed-width
    # columns (the title and categories treated like comments); year, group
    # names, type and marks keep the default width.
    widths = {}
    wrapped: set[int] = set()
    for index, header in enumerate(headers, start=1):
        if header.startswith("q"):
            widths[header] = QUESTION_COLUMN_WIDTH
            wrapped.add(index)
        elif header.endswith("comment") or header in ("project_title", "product_category", "category_of_solution"):
            widths[header] = COMMENT_COLUMN_WIDTH
            wrapped.add(index)
        if header in widths:
            ws.column_dimensions[get_column_letter(index)].width = widths[header]

    # Every cell sits at the top of its row. Row heights are left unset on
    # purpose: Excel then sizes each row to its tallest wrapped cell (the
    # longest answer, comment or category list) when the file opens.
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=cell.column in wrapped, vertical="top")

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _number(value):
    """A mark as a number for the sheet; blank when not marked."""
    if value in (None, ""):
        return None
    try:
        return float(Decimal(str(value)))
    except InvalidOperation:
        return None


# Text columns wide enough to read; TeamCode and the marks keep the default width.
_TEAM_SHEET_WIDTHS = {
    "Students": 20,
    "Mentor": 20,
    "ProjectTitle": 30,
    "ProjectCategory": 20,
    "SolutionCategory": 20,
}


def build_team_marks_xlsx(rows: Iterable[dict], columns: list[str], numeric: set[str]) -> bytes:
    """The marks spreadsheet a supervisor's results email carries: one row
    per team, one column per name in ``columns`` (the marks summary's own
    field names, e.g. TeamCode, PM1, PosterComment1, SM4), filled from
    ``rows``: each team's marks summary fields. The ``numeric`` columns hold
    marks and are written as numbers; a mark not given stays blank. Text
    columns and comments are widened and wrap.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Marks"
    ws.append(columns)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for fields in rows:
        ws.append([
            _number(fields.get(column)) if column in numeric else _text(fields.get(column) or None)
            for column in columns
        ])

    ws.freeze_panes = "B2"
    wrapped = set()
    for index, column in enumerate(columns, start=1):
        # A mark's comment wraps in a fixed width, as on the SAQ sheet.
        width = _TEAM_SHEET_WIDTHS.get(column) or (COMMENT_COLUMN_WIDTH if "Comment" in column else None)
        if width:
            ws.column_dimensions[get_column_letter(index)].width = width
            wrapped.add(index)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=cell.column in wrapped, vertical="top")

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
