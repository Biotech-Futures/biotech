"""Format checks for an uploaded poster.

The programme asks for an A2 portrait poster carrying the team's code and the
supervisor's contact details. These checks report how far a file meets that,
split into two kinds:

* **Structural** checks read the PDF's page geometry. They are arithmetic on
  numbers the file states about itself, so they are certain, and a failure is
  refused outright.
* **Content** checks look for text in the poster. They are good evidence but
  not proof, so a failure is only ever a warning recorded against the entry.

The split matters because the cost of being wrong is not symmetric: a false
structural failure would stop a team submitting, while a false content warning
only tells them to double-check something.

Deliberately *not* checked: the school logo in the top left, and whether a
title, team member list or school name is present. Detecting those means
deciding that one image is a logo and another is not, or that one line of text
is a title and another is not. Neither can be done reliably, and a check that
cries wolf teaches students to ignore every warning next to it — including the
ones that are right.

## On the page size

A2 portrait is enforced literally. The programme's own PowerPoint file is a
different size — around 227mm x 323mm — but that file is an instruction deck
with an example layout on its second slide, not a canvas teams build in, so
posters are not expected to inherit its dimensions.

Worth knowing what this rules out: a poster designed correctly but exported at
A4 is the same shape and would print identically, yet is refused here. That is
a deliberate consequence of enforcing the stated size rather than the stated
proportions.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# A2 portrait, in PDF points (72 to the inch): 420mm x 594mm.
PT_PER_MM = 72.0 / 25.4
A2_WIDTH_PT = 420 * PT_PER_MM
A2_HEIGHT_PT = 594 * PT_PER_MM

# Exporters round, and a page nudged by a millimetre is not a different size.
# 2% of A2's width is about 8mm — far too tight to admit A3 or A1, and far too
# loose to be tripped by rounding.
SIZE_TOLERANCE = 0.02

# Codes are stored on the submission and read back by the page, so they are a
# stable contract rather than display text.
SINGLE_PAGE = "single_page"
PORTRAIT = "portrait"
PAGE_SIZE = "page_size"
TEAM_CODE = "team_code"
SUPERVISOR_EMAIL = "supervisor_email"

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")

# Said instead of naming a finding the student cannot check for themselves.
GENERIC_REFUSAL = (
    "This poster does not match the required format. Please check it against "
    "the programme's poster template and export it again."
)


@dataclass(frozen=True)
class PosterCheck:
    """One check and how the file fared against it.

    ``message`` is written for whoever reviews the entry, not for the student.
    What a student is told is decided separately by ``student_facing_problems``
    below — see the note there on why the two differ.
    """

    code: str
    passed: bool
    message: str = ""
    # Whether this finding is plain enough to repeat to a student word for
    # word. Only findings that are self-evident from looking at their own file
    # qualify; see `student_facing_problems`.
    explicit: bool = False

    def as_dict(self) -> dict:
        return {"code": self.code, "passed": self.passed, "message": self.message}


def student_facing_problems(checks: list[PosterCheck]) -> list[str]:
    """What to tell the student about a refused poster.

    Only findings a student can verify by looking at their own file are named:
    a landscape page is landscape, a three-page file has three pages, and a page
    size is written in the export dialog they just used.

    Anything else is collapsed into one general instruction, because a finding a
    student cannot check for themselves reads as an argument rather than a fix.
    """
    named = [check.message for check in checks if check.explicit and check.message]
    if any(not check.explicit for check in checks):
        named.append(GENERIC_REFUSAL)
    return named or [GENERIC_REFUSAL]


@dataclass(frozen=True)
class PosterCheckResult:
    structural: list[PosterCheck] = field(default_factory=list)
    content: list[PosterCheck] = field(default_factory=list)
    # False when the poster carries no extractable text at all, which is what a
    # poster flattened to an image looks like. The text checks are skipped
    # entirely in that case rather than all reported as failures.
    has_text: bool = True
    # True when the file could not be parsed. Everything is skipped, and the
    # upload is allowed through: see `inspect_poster`.
    unreadable: bool = False

    @property
    def blocking(self) -> list[PosterCheck]:
        return [check for check in self.structural if not check.passed]

    @property
    def warnings(self) -> list[PosterCheck]:
        return [check for check in self.content if not check.passed]

    def as_flag(self) -> dict:
        """The shape stored on the submission and shown to markers."""
        return {
            "has_text": self.has_text,
            "unreadable": self.unreadable,
            "warnings": [check.as_dict() for check in self.warnings],
        }


# --------------------------------------------------------------- geometry


def _page_size(page) -> tuple[float, float]:
    """Width and height as the page is actually displayed.

    A page can carry a rotation that swaps the two: a landscape box rotated 90
    degrees displays as portrait, and reading the box alone would call it
    landscape. Judging the file by what a reader would not see is exactly the
    kind of wrongness a blocking check cannot afford.
    """
    box = page.mediabox
    width = float(box.width)
    height = float(box.height)
    if _page_rotation(page) in (90, 270):
        width, height = height, width
    return width, height


def _page_rotation(page) -> int:
    try:
        return int(page.rotation or 0) % 360
    except Exception:
        return 0


def _close(value: float, target: float) -> bool:
    return abs(value - target) <= target * SIZE_TOLERANCE


def _structural_checks(reader) -> list[PosterCheck]:
    pages = len(reader.pages)
    checks = [
        PosterCheck(
            SINGLE_PAGE,
            pages == 1,
            "" if pages == 1
            else f"The poster should be a single page. This file has {pages}.",
            # Countable from the file itself, so repeating it is reporting a
            # fact rather than making a judgement.
            explicit=True,
        )
    ]
    if pages == 0:
        return checks

    width, height = _page_size(reader.pages[0])
    if width <= 0 or height <= 0:
        return checks

    portrait = height > width
    checks.append(
        PosterCheck(
            PORTRAIT,
            portrait,
            "" if portrait else "The poster should be portrait, not landscape.",
            # Obvious on sight, and unarguable.
            explicit=True,
        )
    )

    right_size = _close(width, A2_WIDTH_PT) and _close(height, A2_HEIGHT_PT)
    checks.append(
        PosterCheck(
            PAGE_SIZE,
            portrait and right_size,
            "" if (portrait and right_size) else (
                "The poster should be A2 (420 x 594 mm). This file is "
                f"{width / PT_PER_MM:.0f} x {height / PT_PER_MM:.0f} mm."
            ),
            # A page size is a number in the export dialog the student just
            # used, so naming it tells them exactly what to change.
            explicit=True,
        )
    )
    return checks


# ---------------------------------------------------------------- content


def _extract_text(reader) -> str:
    try:
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        # Text extraction is far more fragile than reading page geometry, and
        # nothing here is worth failing an upload over.
        logger.warning("poster_checks.text_extraction_failed", exc_info=True)
        return ""


def _content_checks(text: str, *, team_code: str) -> list[PosterCheck]:
    # Word boundaries so BTF1 is not found inside BTF12; case-insensitive
    # because a team writing "btf1" has still put their code on the poster.
    code_present = bool(
        team_code
        and re.search(rf"\b{re.escape(team_code)}\b", text, re.IGNORECASE)
    )
    checks = [
        PosterCheck(
            TEAM_CODE,
            code_present,
            "" if code_present
            else f"We could not find your team code ({team_code}) on the poster.",
        )
    ]

    checks.append(
        PosterCheck(
            SUPERVISOR_EMAIL,
            bool(_EMAIL.search(text)),
            "" if _EMAIL.search(text)
            else "We could not find a supervisor email address on the poster.",
        )
    )
    return checks


def inspect_poster(uploaded_file, *, team_code: str) -> PosterCheckResult:
    """Check one uploaded poster. Never raises.

    A file this cannot parse is reported as unreadable and allowed through
    rather than refused. The upload has already been confirmed as a real PDF by
    its magic bytes, so failing here means our reader could not cope with a file
    that is probably fine — and refusing a team's poster on the strength of our
    own parser giving up, at the deadline, is far worse than accepting a file a
    marker may have to open by hand.
    """
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - dependency is declared
        logger.error("poster_checks.pypdf_missing")
        return PosterCheckResult(unreadable=True)

    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)
        structural = _structural_checks(reader)
        text = _extract_text(reader)
    except Exception:
        logger.warning("poster_checks.unreadable", exc_info=True)
        return PosterCheckResult(unreadable=True)
    finally:
        # Whatever happens, the caller still has to store this file.
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    has_text = bool(text.strip())
    return PosterCheckResult(
        structural=structural,
        content=_content_checks(text, team_code=team_code) if has_text else [],
        has_text=has_text,
    )
