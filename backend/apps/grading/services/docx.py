"""DOCX renderers for marks summaries and participation certificates.

Templates live in two tiers:

  1. ``GradingSettings.marks_summary_template`` / ``certificate_template`` —
     client-provided, uploaded via the settings API. Takes precedence when
     present.
  2. Bundled fallbacks under ``apps/grading/templates/docx/*.docx`` — the
     client's real 2025 templates, so the endpoints produce the real
     documents out of the box.

Two template dialects are auto-detected per file:

  * ``<<[FieldName]>>`` text tokens — the client's marks release template
    (BTF 2025). Replaced run-aware so formatting and line breaks survive.
  * Word content controls with an alias (``firstName``/``lastName``/
    ``projectTitle``) — the client's merit certificate template.

A file with neither is returned unchanged.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.files.storage import default_storage
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Inches
from docx.text.run import Run

from ..models import GradingSettings


logger = logging.getLogger(__name__)

# Signatures are scanned artwork of wildly varying pixel size; pinning the
# width keeps every document's signature block the same on the page.
SIGNATURE_WIDTH = Inches(1.6)


FALLBACK_DIR = Path(__file__).resolve().parent.parent / "templates" / "docx"

_TOKEN_RE = re.compile(r"<<\[(\w+)\]>>")


def _open_template(setting_field, fallback_filename: str):
    """Prefer the admin-uploaded docx; fall back to the in-repo template."""
    if setting_field:
        return default_storage.open(setting_field.name, "rb")
    fallback = FALLBACK_DIR / fallback_filename
    if not fallback.exists():
        raise FileNotFoundError(f"no template configured and fallback {fallback} missing")
    return fallback.open("rb")


def _document_xml(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read("word/document.xml").decode("utf8", errors="ignore")


def _has_angle_tokens(xml: str) -> bool:
    # Angle brackets inside text nodes are entity-escaped in the raw XML.
    return "&lt;&lt;[" in xml or "<<[" in xml


# ---------------------------------------------------------------------------
# <<[Field]>> token replacement


def _iter_paragraphs(container):
    """Yield every paragraph in the document body, descending into tables."""
    for p in container.paragraphs:
        yield p
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_paragraphs(cell)


def _replace_tokens_in_paragraph(paragraph, fields: dict, *, only_known: bool = False) -> None:
    """Replace ``<<[Name]>>`` tokens even when Word split them across runs.

    Works on the ``w:t`` text nodes directly: line breaks (``w:br``) and run
    formatting outside the token span are untouched. Unknown field names are
    blanked rather than left as visible template markers, unless ``only_known``
    is set — the image pass needs to clear its own tokens without wiping the
    text tokens that have not been substituted yet.
    """
    ts = paragraph._element.findall(f".//{qn('w:t')}")
    if not ts:
        return
    texts = [t.text or "" for t in ts]
    combined = "".join(texts)
    matches = list(_TOKEN_RE.finditer(combined))
    if not matches:
        return

    bounds = []
    pos = 0
    for txt in texts:
        bounds.append((pos, pos + len(txt)))
        pos += len(txt)

    # Right-to-left so earlier match offsets stay valid after each splice.
    for m in reversed(matches):
        if only_known and m.group(1) not in fields:
            continue
        value = str(fields.get(m.group(1), ""))
        s, e = m.span()
        start_i = end_i = None
        start_off = end_off = 0
        for i, (b0, b1) in enumerate(bounds):
            if b0 <= s < b1:
                start_i, start_off = i, s - b0
            if b0 < e <= b1:
                end_i, end_off = i, e - b0
        if start_i is None or end_i is None:
            continue
        if start_i == end_i:
            t = texts[start_i]
            texts[start_i] = t[:start_off] + value + t[end_off:]
        else:
            texts[start_i] = texts[start_i][:start_off] + value
            for j in range(start_i + 1, end_i):
                texts[j] = ""
            texts[end_i] = texts[end_i][end_off:]

    for t_el, new in zip(ts, texts):
        t_el.text = new


class _PartOwner:
    """Minimal parent so a bare ``w:r`` element can be wrapped in a ``Run``.

    ``Run.add_picture`` reaches the document part through its parent; content
    controls give us the element but no python-docx object to hang it off.
    """

    def __init__(self, part):
        self.part = part


def _insert_images_in_paragraph(paragraph, images: dict) -> None:
    """Swap ``<<[Name]>>`` image tokens for the picture they name.

    The token text is cleared in place and the picture appended to the same
    paragraph — signature tokens sit on their own line in practice, so the
    end of the paragraph is where the image belongs.
    """
    ts = paragraph._element.findall(f".//{qn('w:t')}")
    if not ts:
        return
    combined = "".join(t.text or "" for t in ts)
    found = [m.group(1) for m in _TOKEN_RE.finditer(combined) if m.group(1) in images]
    if not found:
        return

    _replace_tokens_in_paragraph(paragraph, {name: "" for name in found}, only_known=True)
    for name in found:
        try:
            paragraph.add_run().add_picture(io.BytesIO(images[name]), width=SIGNATURE_WIDTH)
        except Exception:
            # A corrupt or unreadable signature must not sink the whole
            # document — the name beside it still identifies the signatory.
            logger.exception("grading_docx.signature_insert_failed token=%s", name)


def _render_token_template(data: bytes, fields: dict, images: dict | None = None) -> bytes:
    doc = Document(io.BytesIO(data))
    for paragraph in _iter_paragraphs(doc):
        # Images first: the text pass blanks tokens it does not recognise,
        # which would erase the image tokens before they are seen.
        if images:
            _insert_images_in_paragraph(paragraph, images)
        _replace_tokens_in_paragraph(paragraph, fields)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Content-control (w:sdt alias) filling


def _fill_content_controls(data: bytes, fields: dict, images: dict | None = None) -> bytes:
    doc = Document(io.BytesIO(data))
    images = images or {}
    for sdt in doc.element.body.iter(qn("w:sdt")):
        pr = sdt.find(qn("w:sdtPr"))
        alias = pr.find(qn("w:alias")) if pr is not None else None
        if alias is None:
            continue
        name = alias.get(qn("w:val"))
        if name not in fields and name not in images:
            continue
        content = sdt.find(qn("w:sdtContent"))
        if content is None:
            continue
        ts = content.findall(f".//{qn('w:t')}")
        if not ts:
            continue
        if name in images:
            for t in ts:
                t.text = ""
            try:
                run = Run(ts[0].getparent(), _PartOwner(doc.part))
                run.add_picture(io.BytesIO(images[name]), width=SIGNATURE_WIDTH)
            except Exception:
                logger.exception("grading_docx.signature_insert_failed control=%s", name)
            continue
        ts[0].text = str(fields[name])
        for extra in ts[1:]:
            extra.text = ""
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Field mappings for the client's 2025 templates


def _sum_marks(criteria: list[dict]) -> Decimal:
    total = Decimal("0")
    for c in criteria:
        try:
            total += Decimal(c.get("mark") or "0")
        except InvalidOperation:
            continue
    return total


def _two_dp(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def marks_release_fields(context: dict) -> dict:
    """Flatten our context into the BTF marks release template's fields.

    Poster criteria map to P1..P10 in rubric order, SAQ to S1..S4. Fields we
    don't model (project title/category) render blank.
    """
    by_code = {c.get("code"): c for c in context.get("components", [])}

    def criteria(code: str) -> list[dict]:
        return (by_code.get(code) or {}).get("criteria", [])

    poster = criteria("POSTER")
    saq = criteria("SAQ")

    fields = {
        "TeamCode": context.get("group_name", ""),
        "ProjectTitle": context.get("project_title", ""),
        "ProjectCategoryHeading": "Project Category",
        "ProjectCategory": context.get("project_category", ""),
        "SolutionCategory": context.get("solution_category", ""),
        "Students": context.get("students", ""),
        "Mentor": context.get("mentors", ""),
        "SupervisorHeading": "Supervisor(s)",
        "Supervisors": context.get("supervisors", ""),
        "SchoolHeading": "School(s)",
        "Schools": context.get("schools", ""),
        "PosterComment": (by_code.get("POSTER") or {}).get("overall_comment", "")
        or context.get("poster_comment", ""),
        # Configurable per the spec; blank until an admin sets them.
        "Director1Name": context.get("director_1_name", ""),
        "Director2Name": context.get("director_2_name", ""),
    }
    for i in range(10):
        c = poster[i] if i < len(poster) else None
        fields[f"P{i + 1}"] = (c.get("mark") or "") if c else ""
        fields[f"P{i + 1}Comment"] = (c.get("comment") or "") if c else ""
    for i in range(4):
        c = saq[i] if i < len(saq) else None
        fields[f"S{i + 1}"] = (c.get("mark") or "") if c else ""
        fields[f"S{i + 1}Comment"] = (c.get("comment") or "") if c else ""

    poster_total = _sum_marks(poster)
    saq_total = _sum_marks(saq)
    fields["PosterTotal"] = _two_dp(poster_total)
    fields["SAQTotal"] = _two_dp(saq_total)
    fields["CombinedTotal"] = _two_dp(poster_total + saq_total)
    return fields


def certificate_fields(context: dict) -> dict:
    """Map our context onto the merit certificate's content-control aliases."""
    return {
        "firstName": context.get("first_name", ""),
        "lastName": context.get("last_name", ""),
        # No project-title field in the data model yet; the group name is the
        # closest identity we hold for the team's project.
        "projectTitle": context.get("project_title") or context.get("group_name", ""),
        "director1Name": context.get("director_1_name", ""),
        "director2Name": context.get("director_2_name", ""),
    }


def _signature_bytes(field) -> bytes | None:
    """Read one signature image, or None if unset/unreadable.

    Best-effort: a missing blob must not sink a certificate run, so failures
    are logged and the document renders without that image.
    """
    if not field:
        return None
    try:
        with default_storage.open(field.name, "rb") as fh:
            return fh.read()
    except Exception:
        logger.exception("grading_docx.signature_unreadable name=%s", getattr(field, "name", ""))
        return None


def signature_images(settings, prefix: str) -> dict:
    """``{token_name: image_bytes}`` for whichever signatures are uploaded.

    ``prefix`` selects the naming convention of the calling dialect —
    ``Director`` for ``<<[Director1Signature]>>`` tokens, ``director`` for
    ``director1Signature`` content controls.
    """
    images = {}
    for index, field in (
        (1, settings.director_1_signature),
        (2, settings.director_2_signature),
    ):
        data = _signature_bytes(field)
        if data:
            images[f"{prefix}{index}Signature"] = data
    return images


# ---------------------------------------------------------------------------
# Public renderers


def render_marks_summary_data(data: bytes, context: dict) -> bytes:
    """Render marks-summary docx bytes — the saved template or a candidate
    upload being previewed before it replaces anything."""
    settings = GradingSettings.load()
    if _has_angle_tokens(_document_xml(data)):
        return _render_token_template(
            data,
            marks_release_fields(context),
            signature_images(settings, "Director"),
        )
    # No recognised placeholders: hand back the document as uploaded rather
    # than failing. A static summary with nothing to substitute is valid.
    return data


def render_marks_summary(context: dict) -> bytes:
    """Materialise a marks summary docx (see ``marks_summary_context``)."""
    settings = GradingSettings.load()
    with _open_template(settings.marks_summary_template, "marks_release.docx") as fh:
        data = fh.read()
    return render_marks_summary_data(data, context)


def render_certificate_data(data: bytes, context: dict) -> bytes:
    """Render certificate docx bytes — saved template or previewed candidate."""
    settings = GradingSettings.load()
    xml = _document_xml(data)
    fields = certificate_fields(context)
    if _has_angle_tokens(xml):
        return _render_token_template(data, fields, signature_images(settings, "Director"))
    if "<w:sdt>" in xml or "w:alias" in xml:
        return _fill_content_controls(data, fields, signature_images(settings, "director"))
    # As above — a certificate with no placeholders is returned unchanged.
    return data


def render_participation_certificate(context: dict) -> bytes:
    """Materialise a certificate docx (see ``certificate_context``)."""
    settings = GradingSettings.load()
    with _open_template(settings.certificate_template, "merit_certificate.docx") as fh:
        data = fh.read()
    return render_certificate_data(data, context)


# ---------------------------------------------------------------------------
# Context builders


def sample_marks_summary_context() -> dict:
    """Synthetic marks-summary data for the Document Setup test render.

    Every field the templates can reference is filled with an obviously fake
    value, so an admin opening the result can spot any placeholder that did
    NOT get replaced.
    """
    settings = GradingSettings.load()

    def _criteria(prefix: str, count: int) -> list[dict]:
        return [
            {
                "name": f"Sample {prefix} criterion {i}",
                "max_mark": "5",
                "mark": f"{3 + (i % 3)}.00",
                "comment": f"Sample comment for {prefix} criterion {i}.",
            }
            for i in range(1, count + 1)
        ]

    return {
        "group_name": "SAMPLE-TEAM-01",
        "project_title": "Sample Project Title",
        "project_category": "Sample Project Category",
        "solution_category": "Sample Solution Category",
        "year": date.today().year,
        "components": [
            {
                "code": "POSTER",
                "name": "Poster",
                "submitted": True,
                "overall_comment": "Sample overall poster comment.",
                "criteria": _criteria("poster", 10),
            },
            {
                "code": "SAQ",
                "name": "Short Answer Questions",
                "submitted": True,
                "overall_comment": "",
                "criteria": _criteria("SAQ", 4),
            },
        ],
        "director_1_name": settings.director_1_name or "Sample Director One",
        "director_2_name": settings.director_2_name or "Sample Director Two",
        "generated_at": date.today().isoformat(),
        "students": "Jane Doe, John Roe",
        "mentors": "Dr. Sample Mentor",
        "supervisors": "Ms. Sample Supervisor",
        "schools": "Sample High School",
    }


def sample_certificate_context() -> dict:
    """Synthetic certificate data for the Document Setup test render."""
    context = certificate_context(
        "Jane Doe",
        "SAMPLE-TEAM-01",
        date.today().year,
        first_name="Jane",
        last_name="Doe",
    )
    context["project_title"] = "Sample Project Title"
    return context


_ALIAS_RE = re.compile(r'<w:alias[^>]*w:val="([^"]+)"')
_TAG_RE = re.compile(r"<[^>]+>")
_TEXT_PART_RE = re.compile(r"word/(document|header\d*|footer\d*)\.xml")

# Signature placeholders are images rather than context keys, so they are not
# in the field maps and have to be named explicitly when listing what we fill.
_TOKEN_SIGNATURES = {"Director1Signature", "Director2Signature"}
_CONTROL_SIGNATURES = {"director1Signature", "director2Signature"}


def _visible_text(xml: str) -> str:
    """Document text with markup removed, so run-split tokens read whole.

    Word happily splits ``<<[TeamCode]>>`` across several ``w:t`` nodes;
    dropping the tags first is what makes those tokens findable.
    """
    from html import unescape

    return unescape(_TAG_RE.sub("", xml))


def _known_placeholders(kind: str) -> set[str]:
    if kind == "marks-summary":
        return set(marks_release_fields(sample_marks_summary_context())) | _TOKEN_SIGNATURES
    if kind == "certificate":
        return (
            set(certificate_fields(sample_certificate_context()))
            | _TOKEN_SIGNATURES
            | _CONTROL_SIGNATURES
        )
    raise ValueError(f"unknown template kind {kind!r}")


def scan_template_data(kind: str, data: bytes) -> dict:
    """Placeholder report for docx bytes — shared by the scan endpoint and the
    upload-time check, so both judge a template by exactly the same rules."""
    known = _known_placeholders(kind)
    tokens: set[str] = set()
    controls: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if not _TEXT_PART_RE.fullmatch(name):
                continue
            xml = z.read(name).decode("utf8", errors="ignore")
            tokens.update(m.group(1) for m in _TOKEN_RE.finditer(_visible_text(xml)))
            controls.update(_ALIAS_RE.findall(xml))

    found = tokens | controls
    return {
        "dialect": "tokens" if tokens else ("controls" if controls else "none"),
        "present": sorted(found & known),
        "unknown": sorted(found - known),
    }


def scan_template(kind: str) -> dict:
    """Which placeholders the active template actually contains.

    Returns the ones this app knows how to fill (``present``) and the ones it
    would silently leave blank (``unknown``) — the latter are almost always a
    typo in the template, so the settings page can surface them before real
    documents go out.
    """
    settings = GradingSettings.load()
    if kind == "marks-summary":
        field, fallback = settings.marks_summary_template, "marks_release.docx"
    elif kind == "certificate":
        field, fallback = settings.certificate_template, "merit_certificate.docx"
    else:
        raise ValueError(f"unknown template kind {kind!r}")

    with _open_template(field, fallback) as fh:
        data = fh.read()
    return {"uploaded": bool(field), **scan_template_data(kind, data)}


def check_template_upload(kind: str, data: bytes) -> dict:
    """Gate an incoming template before it replaces the active one.

    Opens the bytes exactly the way the renderers will, so a file that would
    break document generation — an old binary .doc, a renamed PDF, a
    truncated upload — is rejected while the working template is still in
    place. Raises ``ValueError`` with an admin-facing message; returns the
    placeholder scan on success.
    """
    try:
        Document(io.BytesIO(data))
    except Exception as exc:
        raise ValueError(
            "This file could not be opened as a .docx document, so the "
            "current template was left unchanged. Save it from Word as "
            ".docx and upload it again."
        ) from exc
    return scan_template_data(kind, data)


def check_signature_upload(data: bytes) -> None:
    """Gate an incoming signature image before it replaces the active one.

    Uses the same format sniffing ``add_picture`` relies on, so any accepted
    file is guaranteed to embed at render time instead of being skipped with
    only a log line. Raises ``ValueError`` with an admin-facing message.
    """
    from docx.image.image import Image as DocxImage

    try:
        DocxImage.from_blob(data)
    except Exception as exc:
        raise ValueError(
            "This file is not an image Word can embed (PNG or JPEG work "
            "best), so the current signature was left unchanged."
        ) from exc


def _team_details(group) -> dict:
    """Names of the group's active members, grouped by role, plus schools."""
    from apps.groups.models.group_members import GroupMembership

    memberships = (
        GroupMembership.objects.filter(group=group, left_at__isnull=True)
        .select_related("user")
        .order_by("joined_at")
    )
    students, mentors, supervisors, schools = [], [], [], []
    student_users = []
    for m in memberships:
        name = (m.user.get_full_name() or m.user.email).strip()
        role = m.membership_role
        if role == GroupMembership.MembershipRoleChoices.STUDENT:
            students.append(name)
            student_users.append(m.user_id)
        elif role == GroupMembership.MembershipRoleChoices.MENTOR:
            mentors.append(name)
        elif role == GroupMembership.MembershipRoleChoices.SUPERVISOR:
            supervisors.append(name)

    if student_users:
        from apps.users.models import StudentProfile

        for school in (
            StudentProfile.objects.filter(user_id__in=student_users)
            .exclude(school_name="")
            .exclude(school_name__isnull=True)
            .values_list("school_name", flat=True)
        ):
            if school not in schools:
                schools.append(school)

    return {
        "students": ", ".join(students),
        "mentors": ", ".join(mentors),
        "supervisors": ", ".join(supervisors),
        "schools": ", ".join(schools),
    }


def marks_summary_context(group, year: int, components: list[dict]) -> dict:
    settings = GradingSettings.load()
    return {
        "group_name": group.group_name,
        "year": year,
        "components": components,
        "director_1_name": settings.director_1_name or "",
        "director_2_name": settings.director_2_name or "",
        "generated_at": date.today().isoformat(),
        **_team_details(group),
    }


def certificate_context(
    student_full_name: str,
    group_name: str,
    year: int,
    first_name: str = "",
    last_name: str = "",
) -> dict:
    settings = GradingSettings.load()
    if not first_name and student_full_name:
        parts = student_full_name.split()
        first_name = parts[0]
        last_name = last_name or " ".join(parts[1:])
    return {
        "student_full_name": student_full_name,
        "first_name": first_name,
        "last_name": last_name,
        "group_name": group_name,
        "year": year,
        "director_1_name": settings.director_1_name or "",
        "director_2_name": settings.director_2_name or "",
        "issued_on": date.today().isoformat(),
    }
