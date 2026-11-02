"""Certificates from a fillable PDF template.

The client's certificate design, saved as a PDF with text fields named as the
Word template's variables (Name, ProjectTitle, Date...), each field filled with
its value and then removed, so the certificate can't be edited. A value is set
in a bundled font (Noto Sans, or Noto Serif for a field whose font is a serif),
bold and italic as the field's font is, at the field's size, colour and
alignment, shrunk to fit its box. A field named Director1Signature or Director2Signature gets that
signature, fitted to its box.
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import ArrayObject, NameObject

PDF = "application/pdf"

# fpdf2 cuts each font down with fontTools, which logs every step at INFO.
logging.getLogger("fontTools").setLevel(logging.WARNING)

_FONTS = Path(__file__).resolve().parent.parent / "fonts"
# By family, bold, italic.
_FACES = {
    ("sans", False, False): "NotoSans-Regular.ttf",
    ("sans", True, False): "NotoSans-Bold.ttf",
    ("sans", False, True): "NotoSans-Italic.ttf",
    ("sans", True, True): "NotoSans-BoldItalic.ttf",
    ("serif", False, False): "NotoSerif-Regular.ttf",
    ("serif", True, False): "NotoSerif-Bold.ttf",
    ("serif", False, True): "NotoSerif-Italic.ttf",
    ("serif", True, True): "NotoSerif-BoldItalic.ttf",
}
# Chinese, Japanese and Korean, for a name in them.
_CJK = "NotoSansCJKsc-Subset.otf"
_SIGNATURES = ("Director1Signature", "Director2Signature")

# Points between a field's edge and its text.
_PAD = 2.0
# A box's height a line takes, and where the baseline sits below its middle.
_LEADING = 1.2
_BASELINE = 0.35
# Raised text (the "th" of a date): its size, and how far up it sits.
_RAISED_SIZE = 0.6
_RAISED_RISE = 0.33
# A multi-line field left to size itself starts at Acrobat's 12pt.
_MULTILINE_SIZE = 12.0
_MULTILINE = 1 << 12
_HIDDEN = 1 << 1
# Parent links followed before a field is taken as broken.
_DEPTH = 32

_SERIF = ("times", "tiro", "tibo", "tiit", "tibi", "serif", "garamond", "georgia", "baskerville", "cambria",
          "palatino", "caslon", "didot", "bodoni", "minion", "playfair", "merriweather", "lora", "constantia")
_BOLD = ("bold", "hebo", "tibo", "tibi", "black", "heavy", "semibold", "demi")
# Acrobat's own names for its italic fonts, and "-It"/"-BoldIt" endings.
_ITALIC_RESOURCES = {"TiIt", "TiBI", "HeOb", "HeBO", "CoOb", "CoBO"}
_ITALIC_ENDING = re.compile(r"[-,][a-z]*it$")

_DA_FONT = re.compile(r"/([^\s/\[\]()<>{}%]+)\s+([-+]?[\d.]+)\s+Tf")
_DA_COLOUR = re.compile(r"((?:[-+]?[\d.]+\s+){1,4})(rg|g|k)(?![\w])")


class CertificatePdfError(ValueError):
    """A PDF template, or a value, a certificate can't be made from; the message is for an admin."""


@dataclass
class _Field:
    name: str
    page: int
    rect: tuple[float, float, float, float]
    shown: bool
    text: bool
    size: float
    rgb: tuple[int, int, int]
    face: tuple[str, bool, bool]
    align: int
    multiline: bool


def is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def as_file(name: str, data: bytes, mimetype: str) -> tuple[str, bytes, str]:
    """``(name, data, mimetype)`` with the extension and type the made file has:
    a certificate from a PDF template is a PDF."""
    stem, dot, _ = name.rpartition(".")
    stem = stem if dot else name
    if is_pdf(data):
        return f"{stem}.pdf", data, PDF
    return f"{stem}.docx", data, mimetype


def extension(field) -> str:
    """A saved template's certificates' extension, from its stored name
    (an upload is named for what it is, see ``upload_name``)."""
    return "pdf" if field and str(field.name).lower().endswith(".pdf") else "docx"


def upload_name(name: str, data: bytes) -> str:
    """An uploaded template's name, its extension what the file is."""
    return as_file(name or "template", data, "")[0]


@lru_cache(maxsize=None)
def _cmap(file: str) -> frozenset[int]:
    font = TTFont(_FONTS / file, lazy=True)
    try:
        return frozenset(font.getBestCmap())
    finally:
        font.close()


def _font_file(key: str) -> str:
    if key == "cjk":
        return _CJK
    family, _, style = key.partition("-")
    return _FACES[(family, "b" in style, "i" in style)]


def _clean(segments: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    """A value's pieces as printed: composed accents, each run of spaces one
    space, no invisible characters, nothing before or after."""
    cleaned = []
    for text, raised in segments:
        text = unicodedata.normalize("NFC", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cf", "Cc") or ch.isspace())
        text = re.sub(r"\s+", " ", text)
        if text:
            cleaned.append((text, raised))
    if cleaned:
        cleaned[0] = (cleaned[0][0].lstrip(), cleaned[0][1])
        cleaned[-1] = (cleaned[-1][0].rstrip(), cleaned[-1][1])
    return [(text, raised) for text, raised in cleaned if text]


def _runs(
    name: str, segments: list[tuple[str, bool]], face: tuple[str, bool, bool],
) -> list[tuple[str, str, bool]]:
    """The value as ``(font key, text, raised)`` runs: each character in the
    field's face, or the CJK font when the face lacks it."""
    family, bold, italic = face
    style = ("b" if bold else "") + ("i" if italic else "")
    primary = f"{family}-{style}" if style else family
    runs: list[tuple[str, str, bool]] = []
    for text, raised in segments:
        for ch in text:
            if ch == " " or (ord(ch) in _cmap(_font_file(primary)) and not unicodedata.category(ch).startswith("M")):
                key = primary
            elif ord(ch) in _cmap(_CJK) and not unicodedata.category(ch).startswith("M"):
                key = "cjk"
            else:
                value = "".join(t for t, _ in segments)
                raise CertificatePdfError(
                    f'The certificate font has no "{ch}" (U+{ord(ch):04X}), so "{value}" can\'t be printed in '
                    f"the {name} field."
                )
            if runs and runs[-1][0] == key and runs[-1][2] == raised:
                runs[-1] = (key, runs[-1][1] + ch, raised)
            else:
                runs.append((key, ch, raised))
    return runs


def _obj(value):
    return value.get_object() if value is not None else None


def _parent(node):
    return _obj(node.get("/Parent"))


def _inherited(node, key):
    for _ in range(_DEPTH):
        if node is None:
            return None
        if key in node:
            return _obj(node[key])
        node = _parent(node)
    return None


def _full_name(widget) -> str:
    parts, node = [], widget
    for _ in range(_DEPTH):
        if node is None:
            break
        if "/T" in node:
            parts.append(str(node["/T"]))
        node = _parent(node)
    # "Name.0", "Name.1": Acrobat's copies of one field.
    parts = [part for part in reversed(parts) if not part.strip().isdigit()]
    return ".".join(part.strip().strip("{}").strip() for part in parts)


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _colour(da: str) -> tuple[int, int, int]:
    colour = (0, 0, 0)
    for numbers, op in _DA_COLOUR.findall(da):
        values = [min(1.0, max(0.0, _number(n))) for n in numbers.split()]
        if op == "g" and len(values) >= 1:
            colour = (round(values[-1] * 255),) * 3
        elif op == "rg" and len(values) >= 3:
            colour = tuple(round(v * 255) for v in values[-3:])
        elif op == "k" and len(values) >= 4:
            c, m, y, k = values[-4:]
            colour = tuple(round(255 * (1 - v) * (1 - k)) for v in (c, m, y))
    return colour


def _base_font(resource: str, widget, acroform) -> str:
    """The font a field's /DA names, as its PDF calls it (e.g. "Montserrat-Bold")."""
    for holder in (widget, acroform):
        try:
            font = _obj(_obj(_obj(holder.get("/DR")).get("/Font")).get(f"/{resource}"))
            return f"{resource} {_obj(font.get('/BaseFont')) or ''}"
        except (KeyError, TypeError, AttributeError):
            continue
    return resource


def _face(font_name: str) -> tuple[str, bool, bool]:
    """``(family, bold, italic)`` for a field's "resource BaseFont" font name."""
    resource, _, base = font_name.partition(" ")
    name = font_name.lower()
    serif = "sans" not in name and any(hint in name for hint in _SERIF)
    italic = (
        resource in _ITALIC_RESOURCES or "italic" in name or "oblique" in name
        or bool(_ITALIC_ENDING.search(base.lower().lstrip("/")))
    )
    return ("serif" if serif else "sans", any(hint in name for hint in _BOLD), italic)


def _fields(reader: PdfReader) -> list[_Field]:
    """Every field's box on every page, with how its text is set."""
    acroform = _obj(reader.root_object.get("/AcroForm")) or {}
    fields = []
    for index, page in enumerate(reader.pages):
        for annot in _obj(page.get("/Annots")) or []:
            widget = _obj(annot)
            if widget.get("/Subtype") != "/Widget":
                continue
            name = _full_name(widget)
            if not name:
                continue
            if page.rotation % 360:
                raise CertificatePdfError(
                    "This PDF's page is rotated, so its fields can't be filled; the current template was left "
                    "unchanged. Export the design in the orientation it prints in, add the fields, and upload that."
                )
            if _number(_obj((_obj(widget.get("/MK")) or {}).get("/R"))) % 360:
                raise CertificatePdfError(
                    f"The {name} field is rotated, so it can't be filled; the current template was left unchanged. "
                    "Make it an upright field and upload the PDF again."
                )
            corners = [_number(_obj(v)) for v in (_obj(widget.get("/Rect")) or [])][:4]
            x1, y1, x2, y2 = corners if len(corners) == 4 else (0.0, 0.0, 0.0, 0.0)
            rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            hidden = int(_number(_obj(widget.get("/F")))) & _HIDDEN
            shown = not hidden and rect[2] - rect[0] >= 1 and rect[3] - rect[1] >= 1
            da = str(_inherited(widget, "/DA") or _obj(acroform.get("/DA")) or "")
            font = _DA_FONT.search(da)
            align = _inherited(widget, "/Q")
            fields.append(_Field(
                name=name,
                page=index,
                rect=rect,
                shown=shown,
                text=_inherited(widget, "/FT") == "/Tx",
                size=max(0.0, _number(font.group(2))) if font else 0.0,
                rgb=_colour(da),
                face=_face(_base_font(font.group(1), widget, acroform)) if font else ("sans", False, False),
                align=int(_number(align if align is not None else _obj(acroform.get("/Q")))) % 3,
                multiline=bool(int(_number(_inherited(widget, "/Ff"))) & _MULTILINE),
            ))
    return fields


def _read(data: bytes) -> PdfReader:
    try:
        reader = PdfReader(io.BytesIO(data))
        encrypted = reader.is_encrypted
        if not encrypted and not len(reader.pages):
            raise ValueError("no pages")
    except Exception as exc:  # noqa: BLE001 - any parse failure is a file we can't use
        raise CertificatePdfError(
            "This file could not be opened as a PDF, so the current template was left unchanged. "
            "Save it again as a PDF and upload that."
        ) from exc
    if encrypted:
        raise CertificatePdfError(
            "This PDF is password-protected, so the current template was left unchanged. "
            "Save a copy without a password and upload that."
        )
    return reader


def field_names(data: bytes) -> list[str]:
    """The template's field names, once each."""
    return sorted({field.name for field in _fields(_read(data))})


class _Overlay:
    """The values drawn on a blank page the size of the template's, to lay over it."""

    def __init__(self, pdf: FPDF, page_height: float, origin: tuple[float, float]):
        self.pdf, self.height, self.origin = pdf, page_height, origin

    def _use(self, key: str, size: float) -> None:
        if key not in self.pdf.fonts:
            self.pdf.add_font(key, "", str(_FONTS / _font_file(key)))
        self.pdf.set_font(key, size=size)

    def _width(self, runs, size: float) -> float:
        width = 0.0
        for key, text, raised in runs:
            self._use(key, size * (_RAISED_SIZE if raised else 1))
            width += self.pdf.get_string_width(text)
        return width

    def _lines(self, runs, size: float, width: float) -> list[list[tuple[str, str, bool]]]:
        """The runs broken at spaces into lines no wider than ``width``, where a word allows."""
        words: list[list[tuple[str, str, bool]]] = [[]]
        for key, text, raised in runs:
            for n, piece in enumerate(text.split(" ")):
                if n:
                    words.append([])
                if piece:
                    words[-1].append((key, piece, raised))
        words = [word for word in words if word]
        lines: list[list[tuple[str, str, bool]]] = []
        for word in words:
            if lines and self._width(lines[-1] + [(word[0][0], " ", False)] + word, size) <= width:
                lines[-1] = lines[-1] + [(word[0][0], " ", False)] + word
            else:
                lines.append(list(word))
        return lines

    def text(self, field: _Field, runs) -> None:
        left, bottom, right, top = field.rect
        box_w, box_h = right - left, top - bottom
        pad = _PAD if box_w > 4 * _PAD and box_h > 2 * _PAD else 0.0
        width, height = box_w - 2 * pad, box_h - 2 * pad
        if field.multiline:
            size = field.size or min(_MULTILINE_SIZE, height / _LEADING)
            lines = self._lines(runs, size, width)
            while size > 1 and (
                len(lines) * size * _LEADING > height or max((self._width(line, size) for line in lines), default=0.0) > width
            ):
                size *= 0.95
                lines = self._lines(runs, size, width)
        else:
            size = field.size or height / _LEADING
            natural = self._width(runs, size)
            if natural > width:
                size *= width / natural
            lines = [runs]
        size = max(size, 1.0)
        line_h = size * _LEADING
        first = (self.height - top + self.origin[1]) + pad + (height - len(lines) * line_h) / 2
        self.pdf.set_text_color(*field.rgb)
        for n, line in enumerate(lines):
            line_w = self._width(line, size)
            x = left - self.origin[0] + pad + (0, (width - line_w) / 2, width - line_w)[field.align]
            baseline = first + (n + 0.5) * line_h + _BASELINE * size
            for key, text, raised in line:
                run_size = size * (_RAISED_SIZE if raised else 1)
                self._use(key, run_size)
                self.pdf.text(x, baseline - (size * _RAISED_RISE if raised else 0), text)
                x += self.pdf.get_string_width(text)

    def image(self, field: _Field, data: bytes) -> None:
        left, bottom, right, top = field.rect
        try:
            self.pdf.image(
                io.BytesIO(data), x=left - self.origin[0], y=self.height - top + self.origin[1],
                w=right - left, h=top - bottom, keep_aspect_ratio=True,
            )
        except Exception as exc:  # noqa: BLE001 - any image the PDF library can't place
            raise CertificatePdfError(
                f"The signature for the {field.name} field couldn't be placed. Upload it again as a PNG or JPEG."
            ) from exc


def check_image(data: bytes) -> None:
    """Raises unless a signature field could hold this image."""
    pdf = FPDF(unit="pt")
    pdf.add_page()
    pdf.image(io.BytesIO(data), x=0, y=0, w=100, h=50, keep_aspect_ratio=True)
    pdf.output()


def fill(data: bytes, values: dict[str, list[tuple[str, bool]]], images: dict[str, bytes]) -> bytes:
    """The certificate: ``data`` (a PDF template) with each field named in
    ``values`` set to its value, given as ``(text, raised)`` pieces, each
    signature field given its image from ``images``, and every field removed.
    Raises ``CertificatePdfError`` when it can't be made."""
    reader = _read(data)
    fields = _fields(reader)
    for field in fields:
        if field.shown and field.name in values and not field.text and field.name not in _SIGNATURES:
            raise CertificatePdfError(
                f"The {field.name} field isn't a text field, so it can't be filled; the current template was "
                "left unchanged. Make it a text field and upload the PDF again."
            )
    writer = PdfWriter(clone_from=reader)
    for index, page in enumerate(writer.pages):
        here = [f for f in fields if f.page == index and f.shown and (f.text or f.name in _SIGNATURES)]
        box = page.mediabox
        origin = (min(float(box.left), float(box.right)), min(float(box.bottom), float(box.top)))
        page_w, page_h = abs(float(box.width)), abs(float(box.height))
        pdf = FPDF(unit="pt", format=(max(page_w, 1.0), max(page_h, 1.0)))
        pdf.set_auto_page_break(False)
        pdf.set_margin(0)
        pdf.add_page()
        overlay = _Overlay(pdf, page_h, origin)
        drawn = False
        for field in here:
            if field.name in _SIGNATURES:
                if images.get(field.name):
                    overlay.image(field, images[field.name])
                    drawn = True
                continue
            runs = _runs(field.name, _clean(values.get(field.name) or []), field.face)
            if runs:
                overlay.text(field, runs)
                drawn = True
        if drawn:
            layer = PdfReader(io.BytesIO(bytes(pdf.output()))).pages[0]
            page.merge_transformed_page(layer, Transformation().translate(*origin))
        annots = _obj(page.get("/Annots"))
        if annots is not None:
            kept = [a for a in annots if _obj(a).get("/Subtype") != "/Widget"]
            if kept:
                page[NameObject("/Annots")] = ArrayObject(kept)
            else:
                del page["/Annots"]
    if "/AcroForm" in writer.root_object:
        del writer.root_object["/AcroForm"]
    # The removed fields, sample text and all, left out of the file: each pass
    # drops what nothing refers to, and so frees what only those referred to.
    for _ in range(_DEPTH):
        before = sum(obj is not None for obj in writer._objects)
        writer.compress_identical_objects(remove_duplicates=False, remove_unreferenced=True)
        if sum(obj is not None for obj in writer._objects) == before:
            break
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
