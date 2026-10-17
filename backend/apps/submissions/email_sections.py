"""Sections of the finalist confirmation as ready-made HTML, styled as the rest of the email, so the
editor on System Emails and an admin's edited wording show them exactly as the default email does.
Every value is escaped."""
from django.utils.html import format_html, format_html_join

GREEN = "#307054"
RED = "#a8342a"

_HEADING = (
    '<p style="margin:26px 0 0 0; color:#6d7a72; font-size:12px; line-height:1.4; font-weight:700; '
    'letter-spacing:0.6px; text-transform:uppercase;">{}</p>'
)
_TABLE = (
    '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
    'style="background:#f4f7f5; border:1px solid #d8e1dc; border-radius:8px; border-collapse:separate; margin-top:8px;">'
    '<tr><td style="padding:6px 20px;">'
    '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;">'
    "{}</table></td></tr></table>"
)
_ROW = (
    '<tr><td style="padding:12px 0; vertical-align:top;{}">'
    '<p style="margin:0; color:#1a2e23; font-size:15px; line-height:1.4; font-weight:600;">{}</p>{}</td>'
    '<td align="right" style="padding:12px 0; vertical-align:top; white-space:nowrap;{}">'
    '<span style="color:{}; font-size:14px; line-height:1.4; font-weight:700;">{}</span></td></tr>'
)
_DETAIL = '<p style="margin:3px 0 0 0; color:#6d7a72; font-size:12.5px; line-height:1.5; word-break:break-word;">{}</p>'
_NOTE = '<p style="margin:10px 0 0 0; color:#6d7a72; font-size:13px; line-height:1.6;">{}</p>'
_DIVIDER = " border-bottom:1px solid #e3eae6;"


def section_html(heading: str, rows: list[dict], note: str = "") -> str:
    """A heading, then a row per item ("label", optional "detail", "status", "colour"), then a note."""
    if not rows:
        return ""
    last = len(rows) - 1
    body = format_html_join(
        "",
        _ROW,
        (
            (
                _DIVIDER if index < last else "",
                row["label"],
                format_html(_DETAIL, row["detail"]) if row.get("detail") else "",
                _DIVIDER if index < last else "",
                row["colour"],
                row["status"],
            )
            for index, row in enumerate(rows)
        ),
    )
    return format_html(
        "{}{}{}",
        format_html(_HEADING, heading),
        format_html(_TABLE, body),
        format_html(_NOTE, note) if note else "",
    )


def presentation_section(components: list[dict]) -> str:
    rows = [
        {**item, "colour": GREEN if item["submitted"] else RED}
        for item in components
    ]
    return section_html("Presentation", rows)


def times_section(times: list[str], day: str) -> str:
    """The times the team selected, or nothing before it has selected any."""
    rows = [{"label": label, "status": "Available", "colour": GREEN} for label in times]
    on = f" on {day}" if day else ""
    return section_html("Times you selected", rows, f"The times your team said it can present{on}, Sydney time.")
