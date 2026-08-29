"""Format checks for an uploaded poster.

The programme asks for an A2 portrait poster carrying the team's code, a school
logo in the top left, and the supervisor's contact details at the foot. These
checks report how far a file meets that, split into two kinds:

* **Structural** checks read the PDF's page geometry. They are arithmetic on
  numbers the file states about itself, so they are certain, and a failure is
  refused outright.
* **Content** checks look inside the poster — its text, and where its images
  sit. They are good evidence but not proof, so a failure is only ever a
  warning recorded against the entry.

The split matters because the cost of being wrong is not symmetric: a false
structural failure would stop a team submitting, while a false content warning
only tells them to double-check something.

Deliberately *not* checked: whether a title, team member list or school name is
present, and whether the logo is the right logo. Detecting those means deciding
that one line of text is a title and another is not, or recognising a school's
branding. Neither can be done reliably, and a check that cries wolf teaches
students to ignore every warning next to it — including the ones that are right.

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

# Where a school logo is expected, as fractions of the page. Generous on
# purpose: the requirement is "top left", not a coordinate, and a warning that
# fires on a logo two centimetres further right than we imagined is a warning
# nobody should have been shown.
LOGO_MAX_LEFT = 0.40
LOGO_MIN_TOP = 0.72
LOGO_MIN_WIDTH = 0.02
LOGO_MAX_WIDTH = 0.45
LOGO_MAX_AREA = 0.20

# Supervisor details belong at the foot of the poster. A third of the page is
# what "the bottom" fairly means on something this tall.
BOTTOM_BAND = 0.33

# Codes are stored on the submission and read back by the page, so they are a
# stable contract rather than display text.
SINGLE_PAGE = "single_page"
PORTRAIT = "portrait"
PAGE_SIZE = "page_size"
TEAM_CODE = "team_code"
SUPERVISOR_EMAIL = "supervisor_email"
SCHOOL_LOGO = "school_logo"

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


# ------------------------------------------------------------ placement


def _multiply(m: list[float], n: list[float]) -> list[float]:
    """Compose two PDF transformation matrices, [a b c d e f]."""
    a1, b1, c1, d1, e1, f1 = m
    a2, b2, c2, d2, e2, f2 = n
    return [
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    ]


def _unit_square_bounds(m: list[float]) -> tuple[float, float, float, float]:
    """Where an image drawn by this matrix actually lands.

    Every image is drawn into the unit square and positioned entirely by the
    matrix in force, so its rectangle is that square's four corners transformed.
    Taking all four rather than the width and height alone keeps this correct
    for a rotated or mirrored placement.
    """
    a, b, c, d, e, f = m
    corners = [
        (e, f),
        (a + e, b + f),
        (c + e, d + f),
        (a + c + e, b + d + f),
    ]
    xs = [x for x, _ in corners]
    ys = [y for _, y in corners]
    return min(xs), min(ys), max(xs), max(ys)


def _image_boxes(page, depth: int = 0) -> list[tuple[float, float, float, float]]:
    """Rectangles of every image drawn on the page, in page coordinates.

    pypdf reports which images a page *contains* but not where they are put:
    position lives in the content stream, in the transformation matrix in force
    when each image is drawn. So the stream is walked here, tracking that matrix
    through the save/restore stack the same way a reader would.

    Note the coordinate system: PDF's origin is the bottom-left with y
    increasing upwards, so a large y means near the top of the page.
    """
    from pypdf.generic import ContentStream

    if depth > 3:
        # Form XObjects can nest. A depth limit keeps a malformed or hostile
        # file from turning this into an unbounded walk.
        return []

    try:
        resources = page.get("/Resources")
        resources = resources.get_object() if resources else {}
        xobjects = resources.get("/XObject")
        xobjects = xobjects.get_object() if xobjects else {}
        content = ContentStream(page.get_contents(), page.pdf)
    except Exception:
        return []

    boxes: list[tuple[float, float, float, float]] = []
    ctm: list[float] = [1, 0, 0, 1, 0, 0]
    stack: list[list[float]] = []

    for operands, operator in content.operations:
        try:
            if operator == b"q":
                stack.append(list(ctm))
            elif operator == b"Q":
                if stack:
                    ctm = stack.pop()
            elif operator == b"cm":
                ctm = _multiply([float(v) for v in operands[:6]], ctm)
            elif operator == b"Do":
                name = operands[0]
                target = xobjects.get(name)
                target = target.get_object() if target is not None else None
                if target is None:
                    continue
                subtype = target.get("/Subtype")
                if subtype == "/Image":
                    boxes.append(_unit_square_bounds(ctm))
                elif subtype == "/Form":
                    # A form draws in its own space; compose its matrix so any
                    # image inside it lands where the reader would put it.
                    inner = target.get("/Matrix")
                    nested_ctm = (
                        _multiply([float(v) for v in inner], ctm) if inner else ctm
                    )
                    for box in _image_boxes(target, depth + 1):
                        boxes.append(_shift(box, nested_ctm, ctm))
        except Exception:
            # One unreadable operation must not cost us the whole page.
            continue
    return boxes


def _shift(box, nested_ctm, outer_ctm):
    """Move a rectangle found inside a form into the outer page's coordinates."""
    x0, y0, x1, y1 = box
    a, b, c, d, e, f = nested_ctm
    points = [
        (a * x + c * y + e, b * x + d * y + f)
        for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))
    ]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _logo_check(page, width: float, height: float) -> PosterCheck | None:
    """Whether something logo-shaped sits in the top-left corner.

    Returns ``None`` — no finding either way — when the page holds no images at
    all. A logo placed as vector artwork, which is what PowerPoint produces from
    an EMF or a grouped shape, leaves no image object behind: reporting "no logo"
    for those would be confidently wrong about a poster that has one. Staying
    quiet is the honest answer when the only evidence available is absent.
    """
    if _page_rotation(page):
        # Every rectangle below would need rotating with the page. Rare enough
        # that saying nothing beats saying something wrong.
        return None

    boxes = _image_boxes(page)
    if not boxes:
        return None

    page_area = width * height
    for x0, y0, x1, y1 in boxes:
        box_width = x1 - x0
        box_height = y1 - y0
        if box_width <= 0 or box_height <= 0:
            continue
        if x0 > width * LOGO_MAX_LEFT:
            continue
        if y1 < height * LOGO_MIN_TOP:
            continue
        if not (width * LOGO_MIN_WIDTH <= box_width <= width * LOGO_MAX_WIDTH):
            continue
        if (box_width * box_height) > page_area * LOGO_MAX_AREA:
            # A full-page background sits in the top left too. Size is what
            # separates it from a logo.
            continue
        return PosterCheck(SCHOOL_LOGO, True)

    return PosterCheck(
        SCHOOL_LOGO,
        False,
        "No school logo was found in the top-left corner of the poster.",
    )


# ---------------------------------------------------------------- content


def _text_by_position(page) -> tuple[str, str]:
    """All the poster's text, and just the text in its bottom band.

    The visitor is handed each run of text along with the matrices in force, so
    the run's position on the page can be recovered. Where that fails the bottom
    band comes back empty and the caller falls back to looking everywhere, which
    is a weaker check rather than a wrong one.
    """
    whole: list[str] = []
    bottom: list[str] = []
    height = float(page.mediabox.height)

    def visitor(text, cm, tm, font_dict, font_size):
        if not text or not text.strip():
            return
        whole.append(text)
        try:
            y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
        except Exception:
            return
        if y <= height * BOTTOM_BAND:
            bottom.append(text)

    try:
        page.extract_text(visitor_text=visitor)
    except Exception:
        logger.warning("poster_checks.text_extraction_failed", exc_info=True)
        return "", ""
    return "".join(whole), "".join(bottom)


def _content_checks(text: str, bottom_text: str, *, team_code: str) -> list[PosterCheck]:
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

    at_foot = bool(_EMAIL.search(bottom_text))
    anywhere = bool(_EMAIL.search(text))
    checks.append(
        PosterCheck(
            SUPERVISOR_EMAIL,
            at_foot or anywhere,
            "" if at_foot else (
                # Present but not where the format puts it. Recorded as a pass
                # with a note rather than a warning: the detail a reviewer wants
                # is there, and its position is a formatting preference, not a
                # missing requirement.
                "An email address was found, but not at the foot of the poster."
                if anywhere
                else "We could not find a supervisor email address on the poster."
            ),
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
        page = reader.pages[0] if len(reader.pages) else None
        text, bottom_text = _text_by_position(page) if page else ("", "")
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
    content: list[PosterCheck] = []
    if has_text:
        content.extend(_content_checks(text, bottom_text, team_code=team_code))
    if page is not None:
        try:
            width, height = _page_size(page)
            logo = _logo_check(page, width, height)
        except Exception:
            logger.warning("poster_checks.logo_failed", exc_info=True)
            logo = None
        if logo is not None:
            content.append(logo)

    return PosterCheckResult(
        structural=structural,
        content=content,
        has_text=has_text,
    )
