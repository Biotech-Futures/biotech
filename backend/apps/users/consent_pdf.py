"""The signed consent record as a PDF, matching the "2026-09-16 Participant
Consent" Word template: an A4 page with one-inch margins, the emblem and a
green Times wordmark, green Times headings, Arial 9pt body text, dashed
statements, and the label/value lines under the declaration, with the drawn
signature in place of {{Signature}}. Pages after the first carry the
template's footer line.

Measurements are in points, taken from the template: page positions, sizes
and spacing below are the Word document's own.

The wording comes from the consent's own version (consent_form.py), so a
record always shows what that guardian actually signed. Only the media
section that applies is included; the template's red "If media consent was
(not) provided" lines are instructions for choosing it, not record text.

The template's fonts are Times New Roman and Arial; the PDF's built-in Times
and Helvetica match them, but write only Windows-1252. When NotoSans-Regular
and NotoSans-Bold are in assets/fonts, they're used for names that don't fit,
so any script prints; without them such characters print as "?".
"""
import io
import os

from django.conf import settings
from django.utils import dateformat, timezone
from fpdf import FPDF

from .consent_form import consent_wording

_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
_LOGO = os.path.join(_ASSETS, "consent-logo.jpeg")
_FONT_REGULAR = os.path.join(_ASSETS, "fonts", "NotoSans-Regular.ttf")
_FONT_BOLD = os.path.join(_ASSETS, "fonts", "NotoSans-Bold.ttf")

GREEN = (3, 114, 81)  # #037251
INK = (29, 28, 29)  # #1D1C1D

MARGIN = 72  # one inch
BODY_SIZE = 9
LINE = 10.35  # Arial 9pt, single spacing
LIST_LINE = 12.25  # the template's dashed statements
PARA_AFTER = 12
FOOTER_TEXT = "This document is a record of consent submitted electronically to {brand}."

MEDIA_GIVEN = "Yes – media consent provided"
MEDIA_NOT_GIVEN = "No – media consent not provided"


def _fits_cp1252(text: str) -> bool:
    try:
        text.encode("cp1252")
    except UnicodeEncodeError:
        return False
    return True


class _ConsentPDF(FPDF):
    def __init__(self):
        super().__init__(unit="pt", format="A4")
        self.core_fonts_encoding = "cp1252"
        self.has_unicode_font = os.path.exists(_FONT_REGULAR) and os.path.exists(_FONT_BOLD)
        if self.has_unicode_font:
            self.add_font("Unicode", "", _FONT_REGULAR)
            self.add_font("Unicode", "B", _FONT_BOLD)
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(auto=True, margin=MARGIN)
        # Word puts text right at the margin; fpdf pads cells by default.
        self.c_margin = 0
        self.footer_text = FOOTER_TEXT.format(brand=settings.BRAND_NAME)

    def use(self, family: str, size: float, style: str = "", colour=INK, text: str = ""):
        """Set the font, falling back to the Unicode font for text the
        built-in fonts can't write."""
        if text and not _fits_cp1252(text) and self.has_unicode_font:
            family, style = "Unicode", style.replace("I", "").replace("U", "")
        self.set_font(family, style, size)
        self.set_text_color(*colour)

    def safe(self, text: str) -> str:
        if self.font_family == "unicode":
            return text
        return text.encode("cp1252", "replace").decode("cp1252")

    def footer(self):
        # The template has a different first page with no footer.
        if self.page_no() == 1:
            return
        self.set_y(self.h - 71 - 8)
        self.use("Helvetica", BODY_SIZE, text=self.footer_text)
        self.cell(0, LINE, self.safe(self.footer_text))

    # -- blocks -------------------------------------------------------------

    def body(self, text: str, after: float = PARA_AFTER, line: float = LINE):
        self.use("Helvetica", BODY_SIZE, text=text)
        self.multi_cell(0, line, self.safe(text), align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(after)

    def body_with_bold(self, text: str, bold: str, after: float = PARA_AFTER):
        """A body paragraph with each occurrence of ``bold`` in bold, as the
        template sets the guardian's or student's name."""
        parts = text.split(bold) if bold else [text]
        for i, part in enumerate(parts):
            if part:
                self.use("Helvetica", BODY_SIZE, text=part)
                self.write(LINE, self.safe(part))
            if i < len(parts) - 1:
                self.use("Helvetica", BODY_SIZE, "B", text=bold)
                self.write(LINE, self.safe(bold))
        self.ln(LINE)
        self.ln(after)

    def body_with_link(self, text: str, address: str, after: float = PARA_AFTER):
        """A body paragraph with ``address`` as a green, underlined mail link."""
        before, _, rest = text.partition(address)
        self.use("Helvetica", BODY_SIZE)
        self.write(LINE, self.safe(before))
        if rest or text.endswith(address):
            self.use("Helvetica", BODY_SIZE, "U", colour=GREEN)
            # write() would split the address mid-word; wrap it whole, as Word does.
            if self.get_x() + self.get_string_width(address) > self.w - self.r_margin:
                self.ln(LINE)
            self.write(LINE, address, link=f"mailto:{address}")
            self.use("Helvetica", BODY_SIZE)
            self.write(LINE, self.safe(rest))
        self.ln(LINE)
        self.ln(after)

    def keep_with_next(self, needed: float):
        """Start a new page unless ``needed`` points fit, so a heading isn't
        left at the foot of a page without its text."""
        if self.get_y() + needed > self.page_break_trigger:
            self.add_page()

    def heading(self, text: str, size: float = 16, after: float = PARA_AFTER):
        self.use("Times", size, colour=GREEN, text=text)
        self.multi_cell(0, size * 1.15, self.safe(text), align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(after)

    def dashes(self, items):
        """The template's statement list: a dash 18pt in, text 36pt in, no
        space between statements."""
        self.use("Helvetica", BODY_SIZE)
        for item in items:
            self.use("Helvetica", BODY_SIZE, text=item)
            y = self.get_y()
            self.set_xy(MARGIN + 18, y)
            self.cell(18, LIST_LINE, "-")
            self.set_xy(MARGIN + 36, y)
            self.multi_cell(0, LIST_LINE, self.safe(item), align="L", new_x="LMARGIN", new_y="NEXT")

    def label_value(self, label: str, value: str):
        self.use("Helvetica", BODY_SIZE, "B")
        self.cell(0, LINE, self.safe(label), new_x="LMARGIN", new_y="NEXT")
        self.body(value)

    def label_signature(self, label: str, png: bytes):
        self.use("Helvetica", BODY_SIZE, "B")
        self.cell(0, LINE, self.safe(label), new_x="LMARGIN", new_y="NEXT")
        height = 40
        if self.get_y() + height > self.page_break_trigger:
            self.add_page()
        self.image(io.BytesIO(png), x=MARGIN, y=self.get_y() + 2, h=height, w=220, keep_aspect_ratio=True)
        self.set_y(self.get_y() + height + 2)
        self.ln(PARA_AFTER)


def _masthead(pdf: _ConsentPDF):
    # The emblem image and the Times wordmark, where the template puts them.
    if os.path.exists(_LOGO):
        pdf.image(_LOGO, x=MARGIN, y=41, w=81, h=66.45)
    pdf.use("Times", 28, "B", colour=GREEN)
    pdf.set_xy(172.3, 58)
    pdf.cell(0, 32, pdf.safe(settings.BRAND_NAME))
    pdf.set_xy(MARGIN, 126)


def render_consent_pdf(consent) -> bytes:
    """The signed record for ``consent`` (a GuardianConsent) as PDF bytes,
    with the student named as they were when the guardian signed."""
    student = consent.student_full_name
    guardian = consent.guardian_full_name
    wording = consent_wording(student, consent.consent_version)
    record = wording["record"]
    signed = dateformat.format(timezone.localtime(consent.signed_at), "j F Y, g:i A T")
    media = MEDIA_GIVEN if consent.media_consent else MEDIA_NOT_GIVEN
    brand = settings.BRAND_NAME

    pdf = _ConsentPDF()
    pdf.set_title(f"{brand} consent record {consent.reference}")
    pdf.set_author(brand)
    pdf.add_page()
    _masthead(pdf)

    pdf.body("This document records the consent provided for:", after=12)
    pdf.heading(student, size=18)
    pdf.body(
        f"by {guardian}, who confirmed that they are the parent, guardian or other person "
        "authorised to provide consent for the participant named above.",
        after=14,
    )

    pdf.heading("Participant Consent")
    pdf.body_with_bold(f"By signing the {brand} consent form, {guardian} confirmed that:", guardian, after=14)
    pdf.dashes(wording["participation"])
    pdf.ln(10)

    pdf.heading("Media Consent")
    pdf.body(f"Recorded selection: {media}")
    for paragraph in record["media_given" if consent.media_consent else "media_not_given"]:
        pdf.body_with_bold(paragraph, student)

    pdf.ln(9)
    pdf.keep_with_next(80)
    pdf.use("Helvetica", 12)
    pdf.cell(0, 14, pdf.safe("Withdrawal of media consent"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    for paragraph in record["media_withdrawal"]:
        if settings.SUPPORT_EMAIL in paragraph:
            pdf.body_with_link(paragraph, settings.SUPPORT_EMAIL)
        else:
            pdf.body(paragraph)

    pdf.ln(6)
    pdf.keep_with_next(60)
    pdf.heading("Declaration")
    pdf.body(record["declaration"])

    pdf.label_value("Participant", student)
    pdf.label_value("Authorised Consent Provider", guardian)
    pdf.label_signature("Signature", bytes(consent.signature_png))
    pdf.label_value("Date signed", signed)
    pdf.label_value("Media consent selection", media)
    pdf.label_value("Reference", consent.reference)

    return bytes(pdf.output())
