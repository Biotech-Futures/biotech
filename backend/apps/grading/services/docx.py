"""DOCX renderers for marks summaries and participation certificates.

Templates live in two tiers:

  1. ``GradingSettings.marks_summary_template`` / ``certificate_template`` —
     client-provided, uploaded via the settings API. Takes precedence when
     present.
  2. Bundled fallbacks under ``apps/grading/templates/docx/*.docx`` — so the
     endpoint works on day one, before the client has sent real templates.

``docxtpl`` uses Jinja-style ``{{ variable }}`` markers inside a normal Word
document. Consumers of these render functions pass a fully-materialised
context dict; the shape is documented on each function.
"""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from django.core.files.storage import default_storage
from docxtpl import DocxTemplate

from ..models import GradingSettings


FALLBACK_DIR = Path(__file__).resolve().parent.parent / "templates" / "docx"


def _open_template(setting_field, fallback_filename: str):
    """Prefer the admin-uploaded docx; fall back to the in-repo template.

    Uploaded files live in ``default_storage`` (Azure Blob in prod, local
    filesystem in dev via the M4 refactor). The fallback keeps the endpoint
    functional before the client sends real docx files.
    """
    if setting_field:
        return default_storage.open(setting_field.name, "rb")
    fallback = FALLBACK_DIR / fallback_filename
    if not fallback.exists():
        raise FileNotFoundError(f"no template configured and fallback {fallback} missing")
    return fallback.open("rb")


def render_marks_summary(context: dict) -> bytes:
    """Materialise a marks summary docx.

    Expected context:
        {
          "group_name": str,
          "year": int,
          "components": [
            {"name": str, "criteria": [{"name": str, "mark": str, "max_mark": str, "comment": str}]}
          ],
          "director_1_name": str, "director_2_name": str,
          "generated_at": str,
        }
    """
    settings = GradingSettings.load()
    with _open_template(settings.marks_summary_template, "marks_summary.docx") as fh:
        doc = DocxTemplate(fh)
        doc.render(context)
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()


def render_participation_certificate(context: dict) -> bytes:
    """Materialise a participation certificate docx.

    Expected context:
        {
          "student_full_name": str,
          "group_name": str,
          "year": int,
          "director_1_name": str, "director_2_name": str,
          "issued_on": str,
        }
    """
    settings = GradingSettings.load()
    with _open_template(settings.certificate_template, "certificate.docx") as fh:
        doc = DocxTemplate(fh)
        doc.render(context)
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()


def marks_summary_context(group, year: int, components: list[dict]) -> dict:
    settings = GradingSettings.load()
    return {
        "group_name": group.group_name,
        "year": year,
        "components": components,
        "director_1_name": settings.director_1_name or "",
        "director_2_name": settings.director_2_name or "",
        "generated_at": date.today().isoformat(),
    }


def certificate_context(student_full_name: str, group_name: str, year: int) -> dict:
    settings = GradingSettings.load()
    return {
        "student_full_name": student_full_name,
        "group_name": group_name,
        "year": year,
        "director_1_name": settings.director_1_name or "",
        "director_2_name": settings.director_2_name or "",
        "issued_on": date.today().isoformat(),
    }
