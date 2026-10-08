"""The signed consent record as a PDF, laid out after the "2026-09-16
Participant Consent" Word template: who consented for whom, what they
confirmed, their media-consent choice, and a signature block with the drawn
signature.

The wording comes from the consent's own version (consent_form.py), so a
record always shows what that guardian actually signed.

Text uses an embedded Unicode font when its files are present in
assets/fonts (NotoSans-Regular.ttf and NotoSans-Bold.ttf); without them the
PDF's built-in font is used, which writes Windows-1252: Western European
names come through, anything else prints as "?".
"""
import io
import os

from django.conf import settings
from django.utils import dateformat, timezone
from fpdf import FPDF

from .consent_form import consent_wording

_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
_FONT_REGULAR = os.path.join(_ASSETS, "fonts", "NotoSans-Regular.ttf")
_FONT_BOLD = os.path.join(_ASSETS, "fonts", "NotoSans-Bold.ttf")
_LOGO = os.path.join(os.path.dirname(__file__), "..", "services", "assets", "btf-logo-white.png")

_GREEN = (26, 79, 63)
_INK = (26, 46, 35)
_MUTED = (98, 112, 104)
_RULE = (216, 225, 220)

MEDIA_GIVEN = "Yes – media consent provided"
MEDIA_NOT_GIVEN = "No – media consent not provided"


class _ConsentPDF(FPDF):
    def __init__(self, footer_text: str):
        super().__init__(format="A4")
        self.footer_text = footer_text
        if os.path.exists(_FONT_REGULAR) and os.path.exists(_FONT_BOLD):
            self.add_font("Body", "", _FONT_REGULAR)
            self.add_font("Body", "B", _FONT_BOLD)
            self.body_family = "Body"
            self.has_unicode_font = True
        else:
            self.core_fonts_encoding = "cp1252"
            self.body_family = "Helvetica"
            self.has_unicode_font = False
        self.set_margins(20, 20, 20)
        self.set_auto_page_break(auto=True, margin=22)

    def text_of(self, text: str) -> str:
        if self.has_unicode_font:
            return text
        return text.encode("cp1252", "replace").decode("cp1252")

    def font(self, size: float, bold: bool = False, colour=_INK):
        self.set_font(self.body_family, "B" if bold else "", size)
        self.set_text_color(*colour)

    def footer(self):
        self.set_y(-14)
        self.font(8, colour=_MUTED)
        self.cell(0, 5, self.text_of(f"{self.footer_text} · Page {self.page_no()} of {{nb}}"), align="C")

    def paragraph(self, text: str, size: float = 10.5, bold: bool = False, colour=_INK, after: float = 3):
        self.font(size, bold, colour)
        self.multi_cell(0, size * 0.55, self.text_of(text), align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(after)

    def heading(self, text: str):
        self.ln(3)
        self.font(13, bold=True, colour=_GREEN)
        self.cell(0, 8, self.text_of(text), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*_RULE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def bullets(self, items):
        self.font(10.5)
        indent = 6
        for item in items:
            y = self.get_y()
            self.set_x(self.l_margin + 1.5)
            self.cell(indent - 1.5, 5.8, self.text_of("•"))
            self.set_xy(self.l_margin + indent, y)
            self.multi_cell(0, 5.8, self.text_of(item), align="L", new_x="LMARGIN", new_y="NEXT")
            self.ln(1.5)
        self.ln(1)


def _banner(pdf: _ConsentPDF):
    pdf.set_fill_color(*_GREEN)
    pdf.rect(0, 0, pdf.w, 26, style="F")
    if os.path.exists(_LOGO):
        pdf.image(_LOGO, x=20, y=6, h=14)
    pdf.set_xy(37, 8)
    pdf.font(15, bold=True, colour=(255, 255, 255))
    pdf.cell(80, 10, pdf.text_of(settings.BRAND_NAME))
    pdf.set_xy(pdf.w - 20 - 80, 8)
    pdf.font(11, colour=(220, 238, 228))
    pdf.cell(80, 10, pdf.text_of("Participant Consent Record"), align="R")
    pdf.set_xy(pdf.l_margin, 36)


def _signature_block(pdf: _ConsentPDF, rows, signature_png: bytes):
    """The table at the end of the record: label on the left, value on the
    right, with the drawn signature as the Signature row's value."""
    label_w = 58
    value_w = pdf.w - pdf.l_margin - pdf.r_margin - label_w
    pdf.set_draw_color(*_RULE)
    for label, value in rows:
        is_signature = value is None
        height = 26 if is_signature else 9
        if pdf.get_y() + height > pdf.page_break_trigger:
            pdf.add_page()
        x, y = pdf.l_margin, pdf.get_y()
        pdf.rect(x, y, label_w, height)
        pdf.rect(x + label_w, y, value_w, height)
        pdf.set_xy(x + 3, y + 2)
        pdf.font(10, bold=True, colour=_MUTED)
        pdf.cell(label_w - 6, 5, pdf.text_of(label))
        if is_signature:
            pdf.image(io.BytesIO(signature_png), x=x + label_w + 3, y=y + 2, h=height - 4, keep_aspect_ratio=True,
                      w=value_w - 6)
        else:
            pdf.set_xy(x + label_w + 3, y + 2)
            pdf.font(10.5)
            pdf.cell(value_w - 6, 5, pdf.text_of(value))
        pdf.set_xy(x, y + height)


def render_consent_pdf(consent) -> bytes:
    """The signed record for ``consent`` (a GuardianConsent) as PDF bytes."""
    profile = consent.student
    user = profile.user
    student = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
    guardian = consent.guardian_full_name
    wording = consent_wording(student, consent.consent_version)
    record = wording["record"]
    signed = dateformat.format(timezone.localtime(consent.signed_at), "j F Y, g:i A T")
    media = MEDIA_GIVEN if consent.media_consent else MEDIA_NOT_GIVEN

    pdf = _ConsentPDF(f"{consent.reference} · Consent form version {consent.consent_version}")
    pdf.set_title(pdf.text_of(f"{settings.BRAND_NAME} consent record {consent.reference}"))
    pdf.set_author(pdf.text_of(settings.BRAND_NAME))
    pdf.add_page()
    _banner(pdf)

    pdf.paragraph("This document records the consent provided for:", colour=_MUTED, after=1)
    pdf.paragraph(student, size=18, bold=True, after=2)
    pdf.paragraph(
        f"by {guardian}, who confirmed that they are the parent, guardian or other person "
        "authorised to provide consent for the participant named above."
    )

    pdf.heading("Participant Consent")
    pdf.paragraph(f"By signing the {settings.BRAND_NAME} consent form, {guardian} confirmed that:")
    pdf.bullets(wording["participation"])

    pdf.heading("Media Consent")
    pdf.paragraph(f"Recorded selection: {media}", bold=True)
    if consent.media_consent:
        pdf.paragraph("Media consent was provided", bold=True, colour=_GREEN, after=2)
        pdf.bullets(record["media_given"])
    else:
        pdf.paragraph("Media consent was not provided", bold=True, colour=_GREEN, after=2)
        pdf.bullets(record["media_not_given"])

    pdf.heading("Withdrawal of media consent")
    pdf.bullets(record["media_withdrawal"])

    pdf.heading("Declaration")
    pdf.paragraph(record["declaration"], after=5)

    _signature_block(pdf, [
        ("Participant", student),
        ("Authorised Consent Provider", guardian),
        ("Signature", None),
        ("Date signed", signed),
        ("Media consent selection", media),
        ("Reference", consent.reference),
    ], bytes(consent.signature_png))

    return bytes(pdf.output())
