"""Certificates from a fillable PDF template (apps.management.services.certificate_pdf)."""
import io
from unittest import mock

from django.test import SimpleTestCase
from fpdf import FPDF
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject, BooleanObject, DictionaryObject, FloatObject, NameObject, NumberObject, TextStringObject,
)

from apps.management.services import certificate_pdf
from apps.management.services.certificate_pdf import CertificatePdfError

LANDSCAPE = (842, 595)


def field(name, rect, da="/Helv 0 Tf 0 g", q=1, ff=0, ft="/Tx", flags=4, rotate=None):
    return {"name": name, "rect": rect, "da": da, "q": q, "ff": ff, "ft": ft, "flags": flags, "rotate": rotate}


def fillable(*fields, size=LANDSCAPE, origin=(0, 0), rotate=0, password=None, link=False) -> bytes:
    """A certificate design with form fields, as Acrobat saves one: each field
    holding sample text, the fonts in the form's resources."""
    design = FPDF(unit="pt", format=size)
    design.add_page()
    design.set_font("helvetica", "B", 30)
    design.set_xy(0, 60)
    design.cell(w=size[0], text="CERTIFICATE OF PARTICIPATION", align="C")
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(bytes(design.output()))))
    page = writer.pages[0]
    if origin != (0, 0):
        page.mediabox.lower_left = origin
        page.mediabox.upper_right = (origin[0] + size[0], origin[1] + size[1])
    if rotate:
        page.rotation = rotate

    def font(base):
        return writer._add_object(DictionaryObject({
            NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject(base),
        }))

    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({
        NameObject("/Helv"): font("/Helvetica"),
        NameObject("/TiBo"): font("/Times-Bold"),
        NameObject("/F7"): font("/ABCDEF+Montserrat-SemiBold"),
        NameObject("/F8"): font("/Georgia-Italic"),
        NameObject("/F9"): font("/Arial,BoldItalic"),
    })})
    annots = ArrayObject()
    for spec in fields:
        widget = DictionaryObject({
            NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/FT"): NameObject(spec["ft"]), NameObject("/T"): TextStringObject(spec["name"]),
            NameObject("/Rect"): ArrayObject([FloatObject(v) for v in spec["rect"]]),
            NameObject("/DA"): TextStringObject(spec["da"]), NameObject("/Q"): NumberObject(spec["q"]),
            NameObject("/F"): NumberObject(spec["flags"]), NameObject("/Ff"): NumberObject(spec["ff"]),
            NameObject("/V"): TextStringObject("SAMPLE TEXT"), NameObject("/P"): page.indirect_reference,
        })
        if spec["rotate"]:
            widget[NameObject("/MK")] = DictionaryObject({NameObject("/R"): NumberObject(spec["rotate"])})
        annots.append(writer._add_object(widget))
    if link:
        annots.append(writer._add_object(DictionaryObject({
            NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Link"),
            NameObject("/Rect"): ArrayObject([FloatObject(v) for v in (10, 10, 50, 30)]),
        })))
    page[NameObject("/Annots")] = annots
    writer.root_object[NameObject("/AcroForm")] = writer._add_object(DictionaryObject({
        NameObject("/Fields"): ArrayObject(list(annots)[: len(fields)]),
        NameObject("/DR"): resources,
        NameObject("/DA"): TextStringObject("/Helv 0 Tf 0 g"),
        NameObject("/NeedAppearances"): BooleanObject(True),
    }))
    if password:
        writer.encrypt(password)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def text_of(pdf: bytes) -> str:
    return "".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


def squashed(text: str) -> str:
    # pypdf reads a NUL between CJK characters; viewers don't.
    return "".join(text.replace("\x00", "").split())


def placed(pdf: bytes) -> list[tuple[str, float, float]]:
    """Each piece of text on the first page, where it lands on the page."""
    found = []

    def visit(text, cm, tm, _font, _size):
        if text.strip():
            x, y = tm[4], tm[5]
            found.append((text.strip(), x * cm[0] + y * cm[2] + cm[4], x * cm[1] + y * cm[3] + cm[5]))

    PdfReader(io.BytesIO(pdf)).pages[0].extract_text(visitor_text=visit)
    return found


def plain(text: str) -> list[tuple[str, bool]]:
    return [(text, False)]


def png(width=300, height=100) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (20, 40, 160)).save(buffer, "PNG")
    return buffer.getvalue()


NAME_BOX = [171, 330, 671, 380]
TEMPLATE = fillable(
    field("Name", NAME_BOX, da="/TiBo 28 Tf 0.1 0.2 0.5 rg"),
    field("ProjectTitle", [221, 230, 621, 300], ff=1 << 12),
    field("Date", [100, 100, 300, 130], da="/Helv 14 Tf 0 g", q=0),
    field("Typo", [560, 140, 760, 170]),
)


class FillTests(SimpleTestCase):
    def test_each_field_gets_its_value_and_the_fields_are_gone(self):
        out = certificate_pdf.fill(TEMPLATE, {
            "Name": plain("Amy Chen"),
            "ProjectTitle": plain("A Soil Sensor for Small Farms"),
            "Date": [("29", False), ("th", True), (" September 2026", False)],
        }, {})

        text = squashed(text_of(out))
        for value in ("AmyChen", "ASoilSensorforSmallFarms", "29thSeptember2026", "CERTIFICATEOFPARTICIPATION"):
            self.assertIn(value, text)
        reader = PdfReader(io.BytesIO(out))
        self.assertNotIn("/AcroForm", reader.root_object)
        self.assertNotIn("/Annots", reader.pages[0])
        # Nothing of the fields is left in the file, their sample text included.
        self.assertNotIn(b"SAMPLE TEXT", out)

    def test_a_value_sits_inside_its_field_and_follows_its_alignment(self):
        out = certificate_pdf.fill(TEMPLATE, {"Name": plain("Amy Chen"), "Date": plain("1 May 2026")}, {})
        spots = {text: (x, y) for text, x, y in placed(out)}

        x, y = spots["Amy Chen"]
        left, bottom, right, top = NAME_BOX
        self.assertTrue(left < x < (left + right) / 2 and bottom < y < top, spots)
        # Left-aligned: two points in from the field's edge.
        self.assertAlmostEqual(spots["1 May 2026"][0], 102, delta=0.5)

    def test_a_page_whose_box_does_not_start_at_nought_is_filled_where_its_fields_are(self):
        template = fillable(field("Name", [300, 400, 500, 440], q=0), origin=(200, 300))
        spots = {text: (x, y) for text, x, y in placed(certificate_pdf.fill(template, {"Name": plain("Amy")}, {}))}
        x, y = spots["Amy"]
        self.assertAlmostEqual(x, 302, delta=0.5)
        self.assertTrue(400 < y < 440)

    def test_a_long_value_is_shrunk_to_fit_its_field(self):
        drawn = []
        real = FPDF.text

        def record(pdf, x, y, text=""):
            drawn.append((x, pdf.get_string_width(text)))
            return real(pdf, x, y, text)

        with mock.patch.object(FPDF, "text", autospec=True, side_effect=record):
            certificate_pdf.fill(TEMPLATE, {"Name": plain("Maximilian Alexander Featherstonehaugh-Montgomery " * 3)}, {})

        x, width = drawn[0]
        self.assertGreaterEqual(x, NAME_BOX[0] + 1.9)
        self.assertLessEqual(x + width, NAME_BOX[2] - 1.9)

    def test_a_multi_line_field_wraps(self):
        title = "Investigating the effects of microplastics on freshwater invertebrates in a river catchment"
        out = certificate_pdf.fill(TEMPLATE, {"ProjectTitle": plain(title)}, {})
        lines = [text for text, _x, _y in placed(out) if text != "CERTIFICATE OF PARTICIPATION"]
        self.assertGreater(len(lines), 1)
        self.assertEqual(squashed("".join(lines)), squashed(title))

    def test_accents_greek_cyrillic_and_cjk_names_print(self):
        for name in ("José Ñúñez-Łukasz", "Ωμέγα Δ", "Дмитрий", "王小明", "김민준", "さくら", "José"):
            with self.subTest(name=name):
                out = certificate_pdf.fill(TEMPLATE, {"Name": plain(name)}, {})
                self.assertIn(squashed(name.replace("é", "é")), squashed(text_of(out)))

    def test_a_character_the_fonts_lack_is_refused_by_name(self):
        for name in ("سارة", "Amy 🙂"):
            with self.subTest(name=name), self.assertRaises(CertificatePdfError) as caught:
                certificate_pdf.fill(TEMPLATE, {"Name": plain(name)}, {})
            self.assertIn("Name field", str(caught.exception))

    def test_spaces_and_invisible_characters_are_tidied(self):
        out = certificate_pdf.fill(TEMPLATE, {"Name": plain("  Amy​ \t Chen\n ")}, {})
        self.assertIn(("Amy Chen"), [text for text, _x, _y in placed(out)])

    def test_a_blank_or_missing_value_leaves_its_field_empty(self):
        out = certificate_pdf.fill(TEMPLATE, {"Name": plain("   "), "Date": []}, {})
        self.assertEqual([text for text, _x, _y in placed(out)], ["CERTIFICATE OF PARTICIPATION"])

    def test_the_fields_font_picks_serif_bold_and_italic(self):
        fields = {f.name: f for f in certificate_pdf._fields(PdfReader(io.BytesIO(fillable(
            field("A", [0, 0, 100, 20], da="/TiBo 12 Tf 0 g"),
            field("B", [0, 30, 100, 50], da="/Helv 12 Tf 0 g"),
            field("C", [0, 60, 100, 80], da="/F7 12 Tf 0 g"),
            field("D", [0, 90, 100, 110], da="/F8 12 Tf 0 g"),
            field("E", [0, 120, 100, 140], da="/F9 12 Tf 0 g"),
            field("F", [0, 150, 100, 170], da="/TiIt 12 Tf 0 g"),
        ))))}
        self.assertEqual(fields["A"].face, ("serif", True, False))
        self.assertEqual(fields["B"].face, ("sans", False, False))
        self.assertEqual(fields["C"].face, ("sans", True, False))
        self.assertEqual(fields["D"].face, ("serif", False, True))
        self.assertEqual(fields["E"].face, ("sans", True, True))
        self.assertEqual(fields["F"].face, ("serif", False, True))
        self.assertEqual(fields["A"].size, 12)
        # Adobe's short endings, and names that merely end in "it".
        self.assertEqual(certificate_pdf._face("F1 MinionPro-It"), ("serif", False, True))
        self.assertEqual(certificate_pdf._face("F1 MinionPro-BoldIt"), ("serif", True, True))
        self.assertEqual(certificate_pdf._face("F1 Summit"), ("sans", False, False))

    def test_an_italic_field_is_set_in_italic(self):
        template = fillable(field("Name", NAME_BOX, da="/F8 20 Tf 0 g"))
        out = certificate_pdf.fill(template, {"Name": plain("Amy Chen")}, {})
        self.assertIn(b"NotoSerifItalic", out)
        self.assertIn("AmyChen", squashed(text_of(out)))

    def test_colours_are_read_from_gray_rgb_and_cmyk(self):
        self.assertEqual(certificate_pdf._colour("/Helv 0 Tf 0.5 g"), (128, 128, 128))
        self.assertEqual(certificate_pdf._colour("/Helv 0 Tf 1 0 0 rg"), (255, 0, 0))
        self.assertEqual(certificate_pdf._colour("/Helv 0 Tf 0 0 0 1 k"), (0, 0, 0))
        self.assertEqual(certificate_pdf._colour(""), (0, 0, 0))

    def test_a_signature_field_gets_the_signature_and_none_leaves_it_empty(self):
        template = fillable(field("Name", NAME_BOX), field("Director1Signature", [100, 60, 250, 110], ft="/Btn"))
        signed = PdfReader(io.BytesIO(certificate_pdf.fill(template, {"Name": plain("Amy")}, {
            "Director1Signature": png(),
        })))
        unsigned = PdfReader(io.BytesIO(certificate_pdf.fill(template, {"Name": plain("Amy")}, {})))
        self.assertEqual(len(signed.pages[0].images), 1)
        self.assertEqual(len(unsigned.pages[0].images), 0)

    def test_a_hidden_field_is_neither_filled_nor_kept(self):
        template = fillable(field("Name", NAME_BOX, flags=2, ft="/Btn"))
        out = certificate_pdf.fill(template, {"Name": plain("Amy")}, {})
        self.assertNotIn("Amy", text_of(out))
        self.assertNotIn("/Annots", PdfReader(io.BytesIO(out)).pages[0])

    def test_links_on_the_page_are_kept(self):
        out = certificate_pdf.fill(fillable(field("Name", NAME_BOX), link=True), {"Name": plain("Amy")}, {})
        annots = PdfReader(io.BytesIO(out)).pages[0]["/Annots"]
        self.assertEqual([a.get_object()["/Subtype"] for a in annots], ["/Link"])


class TemplateTests(SimpleTestCase):
    def test_field_names_are_read_once_each_without_braces_or_copy_numbers(self):
        template = fillable(
            field("Name", NAME_BOX), field("{{ ProjectTitle }}", [0, 0, 100, 20]), field("Typo", [0, 30, 100, 50]),
        )
        self.assertEqual(certificate_pdf.field_names(template), ["Name", "ProjectTitle", "Typo"])
        self.assertEqual(certificate_pdf._full_name({"/T": "0", "/Parent": mock.Mock(
            get_object=lambda: {"/T": "Name"},
        )}), "Name")

    def test_a_file_that_is_not_a_pdf_is_refused(self):
        with self.assertRaisesMessage(CertificatePdfError, "could not be opened as a PDF"):
            certificate_pdf.field_names(b"%PDF-1.7 not really a pdf")

    def test_a_password_protected_pdf_is_refused(self):
        with self.assertRaisesMessage(CertificatePdfError, "password-protected"):
            certificate_pdf.field_names(fillable(field("Name", NAME_BOX), password="secret"))

    def test_a_rotated_page_or_field_is_refused(self):
        with self.assertRaisesMessage(CertificatePdfError, "page is rotated"):
            certificate_pdf.field_names(fillable(field("Name", NAME_BOX), rotate=90))
        with self.assertRaisesMessage(CertificatePdfError, "Name field is rotated"):
            certificate_pdf.field_names(fillable(field("Name", NAME_BOX, rotate=90)))

    def test_a_variable_that_is_not_a_text_field_is_refused(self):
        with self.assertRaisesMessage(CertificatePdfError, "Name field isn't a text field"):
            certificate_pdf.fill(fillable(field("Name", NAME_BOX, ft="/Btn")), {"Name": plain("Amy")}, {})

    def test_a_made_file_is_named_and_typed_for_what_it_is(self):
        docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        self.assertEqual(
            certificate_pdf.as_file("2026_BTF_Student_Certificate_Amy.docx", b"%PDF-1.7", docx),
            ("2026_BTF_Student_Certificate_Amy.pdf", b"%PDF-1.7", certificate_pdf.PDF),
        )
        self.assertEqual(certificate_pdf.as_file("a.pdf", b"PK\x03\x04", docx), ("a.docx", b"PK\x03\x04", docx))
        self.assertEqual(certificate_pdf.upload_name("Design Final.PDF", b"%PDF-"), "Design Final.pdf")
        self.assertEqual(certificate_pdf.upload_name("cert", b"PK\x03\x04"), "cert.docx")

    def test_a_signature_image_is_checked_as_a_pdf_would_place_it(self):
        certificate_pdf.check_image(png())
        with self.assertRaises(Exception):
            certificate_pdf.check_image(b"not an image")
