"""Tests for the poster format checks.

The PDFs here are built by hand rather than fetched, so each test states the
one property it is about — a page size, a rotation, an image, a line of text —
and nothing else varies between them.

The sizes are real. 643 x 915 points is the exact size of the programme's own
PowerPoint file (its slide is 8166100 x 11620500 EMU, and there are 12700 EMU
to a point). That file is an instruction deck rather than a canvas teams build
in, so its size is *not* accepted: the programme asks for A2 and A2 is what is
enforced. The test naming it below records that this is a decision rather than
an oversight.
"""
from django.test import SimpleTestCase

from apps.submissions.poster_checks import (
    PAGE_SIZE,
    PORTRAIT,
    SCHOOL_LOGO,
    SINGLE_PAGE,
    SUPERVISOR_EMAIL,
    TEAM_CODE,
    inspect_poster,
)


# Points, at 72 to the inch.
A2 = (1190.55, 1683.78)          # 420mm x 594mm — what the programme asks for
INSTRUCTION_DECK = (643.0, 915.0)  # the programme's PowerPoint file
A4 = (595.28, 841.89)            # 210mm x 297mm — right shape, wrong size
US_LETTER = (612.0, 792.0)       # the nearest wrong shape by accident


def _build_pdf(width, height, *, text="", pages=1, rotate=0) -> bytes:
    """A minimal but structurally valid PDF, with a real cross-reference table."""
    page_ids = [3 + i for i in range(pages)]
    content_ids = [3 + pages + i for i in range(pages)]
    font_id = 3 + 2 * pages

    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        font_id: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode()

    for pid, cid in zip(page_ids, content_ids):
        rotation = f" /Rotate {rotate}" if rotate else ""
        objects[pid] = (
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {width:.2f} {height:.2f}]{rotation} "
            f"/Contents {cid} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        ).encode()

        body = b""
        if text:
            escaped = text.replace("(", r"\(").replace(")", r"\)")
            body = f"BT /F1 12 Tf 40 40 Td ({escaped}) Tj ET".encode()
        objects[cid] = (
            b"<< /Length " + str(len(body)).encode() + b" >>\nstream\n" + body + b"\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + objects[num] + b"\nendobj\n"

    start_xref = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n".encode() + b"0000000000 65535 f \n"
    for num in range(1, size):
        out += f"{offsets[num]:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{start_xref}\n%%EOF\n"
    ).encode()
    return bytes(out)



def _build_pdf_with_image(width, height, *, x, y, w, h, text="") -> bytes:
    """A one-page PDF with a single 1x1 image placed at a given rectangle.

    The image itself is meaningless — one grey pixel. What is under test is
    where it lands, which is decided entirely by the matrix in the content
    stream, so a real picture would only make the fixture bigger.
    """
    img = bytes([0x80])  # one mid-grey 8-bit pixel
    body = f"q {w:.2f} 0 0 {h:.2f} {x:.2f} {y:.2f} cm /Im0 Do Q".encode()
    if text:
        escaped = text.replace("(", r"\(").replace(")", r"\)")
        body += f"\nBT /F1 12 Tf 40 40 Td ({escaped}) Tj ET".encode()

    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:.2f} {height:.2f}] "
            f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> "
            f"/XObject << /Im0 6 0 R >> >> >>"
        ).encode(),
        4: (
            b"<< /Length " + str(len(body)).encode() + b" >>\nstream\n"
            + body + b"\nendstream"
        ),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        6: (
            b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
            b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\n"
            b"stream\n" + img + b"\nendstream"
        ),
    }

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + objects[num] + b"\nendobj\n"
    start_xref = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n".encode() + b"0000000000 65535 f \n"
    for num in range(1, size):
        out += f"{offsets[num]:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{start_xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


def _check(pdf_bytes, *, team_code="BTF1"):
    from io import BytesIO

    return inspect_poster(BytesIO(pdf_bytes), team_code=team_code)


def _codes(checks):
    return {check.code for check in checks}


class PosterShapeTests(SimpleTestCase):
    def test_a2_is_accepted(self):
        self.assertEqual(_check(_build_pdf(*A2)).blocking, [])

    def test_a4_is_refused_even_though_it_is_the_right_shape(self):
        # The sharpest edge of enforcing size over proportion: this would print
        # identically to an A2 poster and is still refused.
        result = _check(_build_pdf(*A4))

        self.assertIn(PAGE_SIZE, _codes(result.blocking))

    def test_the_programmes_instruction_deck_size_is_refused(self):
        # Deliberate: that file is an instruction deck, not a canvas teams build
        # on, so its size means the poster was not set up at A2.
        result = _check(_build_pdf(*INSTRUCTION_DECK))

        self.assertIn(PAGE_SIZE, _codes(result.blocking))

    def test_the_refusal_names_the_size_it_found(self):
        # A page size is a number in the export dialog, so telling the student
        # what theirs is tells them exactly what to change.
        result = _check(_build_pdf(*A4))

        message = next(c.message for c in result.blocking if c.code == PAGE_SIZE)
        self.assertIn("A2", message)
        self.assertIn("210", message)
        self.assertIn("297", message)

    def test_landscape_is_refused(self):
        result = _check(_build_pdf(A2[1], A2[0]))

        self.assertIn(PORTRAIT, _codes(result.blocking))

    def test_us_letter_is_refused(self):
        # Portrait, but neither A2 nor the right shape — the mistake a student
        # makes by exporting with a US page default.
        result = _check(_build_pdf(*US_LETTER))

        self.assertNotIn(PORTRAIT, _codes(result.blocking))
        self.assertIn(PAGE_SIZE, _codes(result.blocking))

    def test_more_than_one_page_is_refused(self):
        result = _check(_build_pdf(*A2, pages=2))

        self.assertIn(SINGLE_PAGE, _codes(result.blocking))

    def test_a_rotated_page_is_judged_as_it_is_displayed(self):
        # A landscape box turned 90 degrees displays as portrait; reading the box
        # alone would refuse a poster that looks correct to its author.
        result = _check(_build_pdf(A2[1], A2[0], rotate=90))

        self.assertEqual(result.blocking, [])


class PosterContentTests(SimpleTestCase):
    def test_a_poster_naming_the_team_and_a_supervisor_email_warns_about_neither(self):
        pdf = _build_pdf(*A2, text="BTF1 Our Project - supervisor@school.edu.au")

        result = _check(pdf)

        self.assertTrue(result.has_text)
        self.assertEqual(result.warnings, [])

    def test_a_missing_team_code_is_a_warning_not_a_refusal(self):
        pdf = _build_pdf(*A2, text="Our Project - supervisor@school.edu.au")

        result = _check(pdf)

        self.assertEqual(result.blocking, [])
        self.assertIn(TEAM_CODE, _codes(result.warnings))

    def test_a_missing_email_is_a_warning(self):
        result = _check(_build_pdf(*A2, text="BTF1 Our Project"))

        self.assertEqual(result.blocking, [])
        self.assertIn(SUPERVISOR_EMAIL, _codes(result.warnings))

    def test_one_team_code_is_not_found_inside_another(self):
        # BTF1 must not be satisfied by a poster that only says BTF12.
        result = _check(_build_pdf(*A2, text="BTF12 project"), team_code="BTF1")

        self.assertIn(TEAM_CODE, _codes(result.warnings))

    def test_a_lowercase_team_code_still_counts(self):
        result = _check(_build_pdf(*A2, text="btf1 - a@b.com"), team_code="BTF1")

        self.assertNotIn(TEAM_CODE, _codes(result.warnings))

    def test_a_poster_with_no_text_layer_is_not_warned_about_at_all(self):
        # Flattened to an image, there is nothing to search. A wall of warnings
        # that are all wrong teaches students to ignore the right ones.
        result = _check(_build_pdf(*A2))

        self.assertFalse(result.has_text)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.content, [])


class UnreadablePosterTests(SimpleTestCase):
    def test_a_file_that_cannot_be_parsed_is_allowed_through(self):
        # Refusing a poster at the deadline because our reader gave up is worse
        # than accepting one a marker opens by hand. Recorded, not blocked.
        result = _check(b"%PDF-1.4\nnot really a pdf\n%%EOF\n")

        self.assertTrue(result.unreadable)
        self.assertEqual(result.blocking, [])
        self.assertEqual(result.warnings, [])

    def test_the_stored_flag_says_what_happened(self):
        flag = _check(_build_pdf(*A2, text="Our Project")).as_flag()

        self.assertTrue(flag["has_text"])
        self.assertFalse(flag["unreadable"])
        self.assertIn(TEAM_CODE, {w["code"] for w in flag["warnings"]})


class SchoolLogoTests(SimpleTestCase):
    # A2 is 1190.55 x 1683.78 points.
    W, H = A2

    def _logo_at(self, x, y, w, h, text="BTF1 a@b.edu.au"):
        return _check(
            _build_pdf_with_image(self.W, self.H, x=x, y=y, w=w, h=h, text=text)
        )

    def test_a_logo_in_the_top_left_passes(self):
        # 60pt square, 40pt in from the left, near the top edge.
        result = self._logo_at(40, self.H - 100, 60, 60)

        self.assertNotIn(SCHOOL_LOGO, _codes(result.warnings))

    def test_a_logo_in_the_top_right_is_flagged(self):
        result = self._logo_at(self.W - 100, self.H - 100, 60, 60)

        self.assertIn(SCHOOL_LOGO, _codes(result.warnings))

    def test_an_image_at_the_foot_of_the_page_is_not_mistaken_for_a_logo(self):
        result = self._logo_at(40, 40, 60, 60)

        self.assertIn(SCHOOL_LOGO, _codes(result.warnings))

    def test_a_full_page_background_is_not_mistaken_for_a_logo(self):
        # Its top-left corner is exactly where a logo would be; only its size
        # tells the two apart.
        result = self._logo_at(0, 0, self.W, self.H)

        self.assertIn(SCHOOL_LOGO, _codes(result.warnings))

    def test_a_poster_with_no_images_says_nothing_either_way(self):
        # A logo placed as vector artwork leaves no image behind. Reporting it
        # missing would be confidently wrong about a poster that has one.
        result = _check(_build_pdf(*A2, text="BTF1 a@b.edu.au"))

        codes = {check.code for check in result.content}
        self.assertNotIn(SCHOOL_LOGO, codes)


class SupervisorEmailPlacementTests(SimpleTestCase):
    W, H = A2

    def test_an_email_at_the_foot_passes(self):
        # The text helper draws at y=40, which is the bottom of the page.
        result = _check(_build_pdf(*A2, text="BTF1 supervisor@school.edu.au"))

        self.assertNotIn(SUPERVISOR_EMAIL, _codes(result.warnings))

    def test_no_email_anywhere_is_flagged(self):
        result = _check(_build_pdf(*A2, text="BTF1 and nothing else"))

        self.assertIn(SUPERVISOR_EMAIL, _codes(result.warnings))
