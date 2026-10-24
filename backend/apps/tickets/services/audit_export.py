"""The ticket audit log as an Excel file (client item C-26).

Asked for by the client on the Audit tab, 2026-10-22: "Could you add an
export to that, if we needed to export that to, like, an Excel?", pointing
at the queue's own export (C-09). So the sheet is the Audit table: the same
five columns under the same headings, for every row the current filters
match rather than only the page on screen.

The table words its rows in the portal (components/admin/tickets/audit/
auditRows.ts, and auditActionLabel and auditActorName in
utils/ticketAgentSchema.ts). The file is written here, so the wording exists
twice. The two follow the same rules in the same order, and
tests/apps/tickets/test_audit_export.py pins the cases auditRows.spec.ts
pins; a rule changed on one side has to change on the other. Two
differences are deliberate. A missing value is a plain hyphen, because
nothing a person reads in an export may carry an em-dash (export.py). And a
new owner is named whenever the account still exists, where the table can
only name people on the assignee roster it loaded.

ORM-free, like export.py: the view decides which rows are in the file and
looks up the names they mention.
"""

from __future__ import annotations

import io
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from ..models import TicketCategory, TicketPriority, TicketStatus
from .export import _put

# The Audit table's headings, in its order (TicketAuditTable.vue).
HEADERS = ["When", "Ticket", "Action", "Who", "What changed"]

_WIDTHS = [30, 10, 26, 26, 60]

# TICKET_AUDIT_ACTIONS in utils/ticketAgentSchema.ts, word for word.
ACTION_LABELS = {
    "create": "Created",
    "assign": "Assigned",
    "status": "Status changed",
    "priority": "Priority changed",
    "category": "Category changed",
    "resolve": "Resolved",
    "reopen": "Reopened",
    "screening_approve": "Screening approved",
    "screening_delete": "Screening message deleted",
    "delete": "Deleted",
}

# The table's dash for a value a row does not have, as export.py writes it.
MISSING = "-"

_STATUS_LABELS = dict(TicketStatus.choices)
_PRIORITY_LABELS = dict(TicketPriority.choices)
_CATEGORY_LABELS = dict(TicketCategory.choices)


def action_label(action: str) -> str:
    """auditActionLabel: an unrecognised value comes back as stored."""
    return ACTION_LABELS.get(action, action)


def actor_name(actor_name_or_none, after_state) -> str:
    """auditActorName: who a row names when it names nobody.

    Screening writes its rows with no actor on purpose and marks them with a
    channel; any other row without an actor outlived the account that made
    it (AuditLog.actor_user is SET_NULL)."""
    if actor_name_or_none:
        return actor_name_or_none
    after = after_state if isinstance(after_state, dict) else {}
    return "Automated screening" if after.get("channel") == "ai_screening" else "Account removed"


def _label(value, labels) -> str:
    if not isinstance(value, str) or value == "":
        return MISSING
    return labels.get(value, value)


def _category(value) -> str:
    # categoryLabel: an empty category has words of its own.
    if not value:
        return "Not categorised"
    return _CATEGORY_LABELS.get(value, value)


def _humanise(value: str) -> str:
    words = value.replace("_", " ")
    return words[:1].upper() + words[1:]


def summarise(action: str, before_state, after_state, names_by_id) -> str:
    """What changed, in one line: summarise() in auditRows.ts.

    The rules run in a fixed order and the first that recognises the row
    answers: delete, create, status, owner, priority, category. lifecycle.py
    relies on that order (an assign row carries only the owner, a reopen row
    carries both status and owner and reads as the status change)."""
    before = before_state if isinstance(before_state, dict) else {}
    after = after_state if isinstance(after_state, dict) else {}

    if action == "delete":
        named = [part for part in (before.get("ticket_number"), before.get("subject"))
                 if isinstance(part, str) and part != ""]
        return " · ".join(named) if named else "Ticket removed from the queue"
    if action == "create":
        flagged = after.get("screening_category")
        if isinstance(flagged, str) and flagged != "":
            return f"Flagged as {_humanise(flagged)}"
        return "Ticket opened"
    if isinstance(before.get("status"), str) or isinstance(after.get("status"), str):
        return f"{_label(before.get('status'), _STATUS_LABELS)} → {_label(after.get('status'), _STATUS_LABELS)}"
    if "assignee_id" in before or "assignee_id" in after:
        owner = after.get("assignee_id")
        if owner is None:
            return "Handed back to the pool"
        name = names_by_id.get(owner)
        return f"Owner set to {name}" if name else f"Owner set to #{owner}"
    # The before side only, for this rule and the next: a screening create row
    # carries priority in its after side, and must never read as a change.
    if isinstance(before.get("priority"), str):
        return f"{_label(before.get('priority'), _PRIORITY_LABELS)} → {_label(after.get('priority'), _PRIORITY_LABELS)}"
    if isinstance(before.get("category"), str):
        upcoming = after.get("category") if isinstance(after.get("category"), str) else ""
        return f"{_category(before['category'])} → {_category(upcoming)}"
    return MISSING


def audit_workbook(rows, *, zone: ZoneInfo, names_by_id) -> bytes:
    """XLSX bytes for ``rows``, newest first as the table lists them.

    Each row is a dict with createdAt (aware datetime), ticketId, action,
    actorName (or None), beforeState and afterState. ``names_by_id`` names
    the owners the rows mention, by user id."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Ticket audit"

    for column, heading in enumerate(HEADERS, start=1):
        ws.cell(row=1, column=column, value=heading).font = Font(bold=True)

    for index, row in enumerate(rows, start=2):
        # A real date in the exporter's zone, the zone in the cell's own
        # format, as the queue's file writes its Last activity column.
        local = row["createdAt"].astimezone(zone)
        when = ws.cell(row=index, column=1, value=local.replace(tzinfo=None))
        when.number_format = f'd mmm yyyy, hh:mm AM/PM "{local.tzname()}"'
        values = [
            f"#{row['ticketId']}",
            action_label(row["action"]),
            actor_name(row["actorName"], row["afterState"]),
            summarise(row["action"], row["beforeState"], row["afterState"], names_by_id),
        ]
        for column, value in enumerate(values, start=2):
            _put(ws, index, column, value)

    for column, width in enumerate(_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(column)].width = width
    ws.freeze_panes = "A2"
    for sheet_row in ws.iter_rows(min_row=2):
        for cell in sheet_row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
