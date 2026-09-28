"""SAQ → XLSX export.

Client explicitly said spreadsheet is easier than PDF for SAQ marking off-
platform, so this is the primary text-export path. Shape — one row per
group:

    | year | group_name | type ("SAQs")      (year: the team's challenge year)
    | q1 | q2 | …            (each answer under its question, in bold)
    | r1_mark | r1_comment | r2_mark | r2_comment | …   (one pair per criterion)
    | overall_comment | product_category | category_of_solution

``qN`` columns line up by question across groups (a group that skipped an
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
from .upload import TYPE_LABELS


def _format_product_category(cats: GroupMarkingCategories | None) -> str:
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


def _format_solution_category(cats: GroupMarkingCategories | None) -> str:
    """The picked option, or Other's text as plain text ("App")."""
    if cats is None:
        return ""
    label = cats.solution_category or ""
    if label == "Other" and cats.solution_category_other:
        return cats.solution_category_other
    return label


QUESTION_COLUMN_WIDTH = 43
COMMENT_COLUMN_WIDTH = 30


def _answer_cell(prompt: str, answer: str) -> CellRichText:
    """The question in bold, the team's answer on the line below it. Uploads
    read the cell back as plain text (and never parse it)."""
    return CellRichText(TextBlock(InlineFont(b=True), prompt), f"\n{answer}")


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
    entries = list(entries)
    criteria_list = list(criteria)
    grades_by_pair = grades_by_pair or {}
    feedback_by_group = feedback_by_group or {}
    categories_by_group = categories_by_group or {}
    years_by_group = years_by_group or {}
    prompts = _question_columns(entries, questions)

    headers = ["year", "group_name", "type"]
    headers += [f"q{i}" for i in range(1, len(prompts) + 1)]
    for i in range(1, len(criteria_list) + 1):
        headers += [f"r{i}_mark", f"r{i}_comment"]
    headers += ["overall_comment", "product_category", "category_of_solution"]

    wb = Workbook()
    ws = wb.active
    ws.title = "SAQ"

    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for entry in entries:
        cats = categories_by_group.get(entry.group_id)
        answers = dict(entry.answers)
        row = [years_by_group.get(entry.group_id), entry.group_name, TYPE_LABELS["SAQ"]]
        row += [
            _answer_cell(prompt, answers[prompt]) if prompt in answers else ""
            for prompt in prompts
        ]
        for criterion in criteria_list:
            existing = grades_by_pair.get((entry.submission_id, criterion.id))
            row += [
                float(existing.mark) if existing and existing.mark is not None else None,
                existing.comment if existing else "",
            ]
        row += [
            feedback_by_group.get(entry.group_id, ""),
            _format_product_category(cats),
            _format_solution_category(cats),
        ]
        ws.append(row)

    # Answers, comments and the category columns wrap in fixed-width columns
    # (the categories treated like comments); year, group names, type and marks
    # keep the default width.
    widths = {}
    wrapped: set[int] = set()
    for index, header in enumerate(headers, start=1):
        if header.startswith("q"):
            widths[header] = QUESTION_COLUMN_WIDTH
            wrapped.add(index)
        elif header.endswith("comment") or header in ("product_category", "category_of_solution"):
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


def _out_of(value) -> str:
    """A maximum as a header shows it: "10", "2.5"."""
    return format(Decimal(str(value or 0)).normalize(), "f")


def _number(value):
    """A mark as a number for the sheet; blank when not marked."""
    if value in (None, ""):
        return None
    try:
        return float(Decimal(str(value)))
    except InvalidOperation:
        return None


def build_marks_xlsx(rows: Iterable[tuple[str, str, list[dict]]]) -> bytes:
    """The marks spreadsheet a supervisor's results email carries: one row
    per student, with each criterion's mark, each component's total and the
    overall total.

    ``rows`` are (student name, team name, components), the components
    shaped as the student marks endpoint gives them. Columns follow the
    components and their rubric criteria in order; a component without a
    rubric has no marks, so no columns.
    """
    rows = list(rows)

    # (component code, criterion name) -> column, in first-seen order.
    components: dict[str, dict] = {}
    for _, _, payload in rows:
        for component in payload:
            if not component.get("criteria"):
                continue
            entry = components.setdefault(
                component["code"], {"name": component["name"], "criteria": {}}
            )
            for criterion in component["criteria"]:
                entry["criteria"].setdefault(criterion["name"], criterion["max_mark"])

    headers = ["Student", "Team"]
    grand_max = Decimal("0")
    for entry in components.values():
        component_max = Decimal("0")
        for name, max_mark in entry["criteria"].items():
            headers.append(f"{entry['name']}: {name} (/{_out_of(max_mark)})")
            component_max += Decimal(str(max_mark or 0))
        headers.append(f"{entry['name']} Total (/{_out_of(component_max)})")
        grand_max += component_max
    headers.append(f"Total (/{_out_of(grand_max)})")

    wb = Workbook()
    ws = wb.active
    ws.title = "Marks"
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True, vertical="top")

    for student, team, payload in rows:
        by_code = {c["code"]: c for c in payload}
        row: list = [student, team]
        grand_total, any_mark = 0.0, False
        for code, entry in components.items():
            marks = {
                c["name"]: _number(c.get("mark"))
                for c in (by_code.get(code) or {}).get("criteria", [])
            }
            values = [marks.get(name) for name in entry["criteria"]]
            row += values
            given = [v for v in values if v is not None]
            row.append(sum(given) if given else None)
            grand_total += sum(given)
            any_mark = any_mark or bool(given)
        row.append(grand_total if any_mark else None)
        ws.append(row)

    ws.freeze_panes = "C2"
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 20
    for index in range(3, len(headers) + 1):
        ws.column_dimensions[get_column_letter(index)].width = 16

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
