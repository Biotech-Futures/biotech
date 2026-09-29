"""Poster format checks.

Structural checks (page count, orientation) refuse the upload. Content checks
(A-series size, team code, supervisor email, school logo) only record warnings.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# Where a logo is expected, as fractions of the page.
LOGO_MAX_LEFT = 0.40
LOGO_MIN_TOP = 0.72
LOGO_MIN_WIDTH = 0.02
LOGO_MAX_WIDTH = 0.45
LOGO_MAX_AREA = 0.20

BOTTOM_BAND = 0.33

# Short side, long side, in millimetres.
A_SERIES_MM = {
    "A0": (841, 1189), "A1": (594, 841), "A2": (420, 594), "A3": (297, 420),
    "A4": (210, 297), "A5": (148, 210), "A6": (105, 148),
}
# Absorbs rounding when a poster is exported to PDF.
SIZE_TOLERANCE_MM = 5
POINTS_PER_MM = 72 / 25.4

# Stored on the submission, so these codes are a contract.
SINGLE_PAGE = "single_page"
PORTRAIT = "portrait"
A_SERIES_SIZE = "a_series_size"
TEAM_CODE = "team_code"
SUPERVISOR_EMAIL = "supervisor_email"
SCHOOL_LOGO = "school_logo"

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")

GENERIC_REFUSAL = "This poster is not in the required format."


@dataclass(frozen=True)
class PosterCheck:
    code: str
    passed: bool
    message: str = ""
    # Whether the message is plain enough to show a student verbatim.
    explicit: bool = False

    def as_dict(self) -> dict:
        return {"code": self.code, "passed": self.passed, "message": self.message}


def student_facing_problems(checks: list[PosterCheck]) -> list[str]:
    """Messages a student can act on; any non-explicit finding becomes a general refusal."""
    named = [check.message for check in checks if check.explicit and check.message]
    if any(not check.explicit for check in checks):
        named.append(GENERIC_REFUSAL)
    return named or [GENERIC_REFUSAL]


@dataclass(frozen=True)
class PosterCheckResult:
    structural: list[PosterCheck] = field(default_factory=list)
    content: list[PosterCheck] = field(default_factory=list)
    # False for a poster flattened to an image; text checks are then skipped.
    has_text: bool = True
    unreadable: bool = False

    @property
    def blocking(self) -> list[PosterCheck]:
        return [check for check in self.structural if not check.passed]

    @property
    def warnings(self) -> list[PosterCheck]:
        return [check for check in self.content if not check.passed]

    def as_flag(self) -> dict:
        return {
            "has_text": self.has_text,
            "unreadable": self.unreadable,
            "warnings": [check.as_dict() for check in self.warnings],
        }


def _page_size(page) -> tuple[float, float]:
    """Width and height as displayed, accounting for page rotation."""
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


def _structural_checks(reader) -> list[PosterCheck]:
    pages = len(reader.pages)
    checks = [
        PosterCheck(
            SINGLE_PAGE,
            pages == 1,
            "" if pages == 1
            else f"The poster should be a single page. This file has {pages}.",
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
            explicit=True,
        )
    )

    return checks


def _size_check(width: float, height: float) -> PosterCheck:
    size = _a_series_size(width, height)
    return PosterCheck(
        A_SERIES_SIZE,
        size is not None,
        "" if size else (
            f"The page is {round(width / POINTS_PER_MM)} × {round(height / POINTS_PER_MM)} mm, "
            "not an A-series size (A2 expected)."
        ),
    )


def _a_series_size(width: float, height: float) -> str | None:
    short, long = sorted((width / POINTS_PER_MM, height / POINTS_PER_MM))
    for name, (a, b) in A_SERIES_MM.items():
        if abs(short - a) <= SIZE_TOLERANCE_MM and abs(long - b) <= SIZE_TOLERANCE_MM:
            return name
    return None


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
    """Bounding box of the unit square under this matrix, correct under rotation."""
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
    """Image rectangles in page coordinates (origin bottom-left), read from the content stream."""
    from pypdf.generic import ContentStream

    if depth > 3:
        # Stops a malformed file recursing through nested forms forever.
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
                    # A form draws in its own space, so its matrix is composed in.
                    inner = target.get("/Matrix")
                    nested_ctm = (
                        _multiply([float(v) for v in inner], ctm) if inner else ctm
                    )
                    for box in _image_boxes(target, depth + 1):
                        boxes.append(_shift(box, nested_ctm, ctm))
        except Exception:
            continue
    return boxes


def _shift(box, nested_ctm, outer_ctm):
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
    """None when the page has no images, since a vector logo leaves no image behind."""
    if _page_rotation(page):
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
            # Too large to be a logo, e.g. a full-page background.
            continue
        return PosterCheck(SCHOOL_LOGO, True)

    return PosterCheck(
        SCHOOL_LOGO,
        False,
        "No school logo was found in the top-left corner of the poster.",
    )


def _text_by_position(page) -> tuple[str, str]:
    """All of the page's text, and the text in its bottom band."""
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
    # Joined with spaces so adjacent runs like "2026" and "BTF1" stay separate words.
    return " ".join(whole), " ".join(bottom)


def _content_checks(text: str, bottom_text: str, *, team_code: str) -> list[PosterCheck]:
    # Word boundaries so BTF1 is not matched inside BTF12.
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
                "An email address was found, but not at the foot of the poster."
                if anywhere
                else "We could not find a supervisor email address on the poster."
            ),
        )
    )
    return checks


def inspect_poster(uploaded_file, *, team_code: str) -> PosterCheckResult:
    """Check one uploaded poster. Never raises; a file that cannot be parsed is accepted as unreadable."""
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
            content.append(_size_check(width, height))
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
