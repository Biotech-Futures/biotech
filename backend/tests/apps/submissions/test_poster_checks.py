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



def _check(pdf_bytes, *, team_code="BTF1"):
    from io import BytesIO

    return inspect_poster(BytesIO(pdf_bytes), team_code=team_code)


def _codes(checks):
    return {check.code for check in checks}


class PosterShapeTests(SimpleTestCase):
    def test_a2_is_accepted(self):
        self.assertEqual(_check(_build_pdf(*A2)).blocking, [])

    def test_a4_is_refused_even_though_it_is_the_right_shape(self):
        # Recorded because it is the sharpest edge of enforcing the stated size
        # rather than the stated proportions: this poster would print
        # identically to an A2 one, and is still refused.
        result = _check(_build_pdf(*A4))

        self.assertIn(PAGE_SIZE, _codes(result.blocking))

    def test_the_programmes_instruction_deck_size_is_refused(self):
        # Deliberate. That file is an instruction deck with an example layout,
        # not a canvas teams build on, so a poster arriving at its size has not
        # been set up at A2.
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
        # A landscape box turned 90 degrees displays as portrait. Reading the
        # box alone would refuse a poster that looks perfectly correct to the
        # person who made it.
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
        # A poster flattened to an image has no text to search. Reporting every
        # content check as failed would be a wall of warnings that are all
        # wrong, which teaches students to ignore the ones that are right.
        result = _check(_build_pdf(*A2))

        self.assertFalse(result.has_text)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.content, [])


class UnreadablePosterTests(SimpleTestCase):
    def test_a_file_that_cannot_be_parsed_is_allowed_through(self):
        # Refusing a team's poster because our own reader gave up — at the
        # deadline — is worse than accepting one a marker may have to open by
        # hand. It is recorded, not blocked.
        result = _check(b"%PDF-1.4\nnot really a pdf\n%%EOF\n")

        self.assertTrue(result.unreadable)
        self.assertEqual(result.blocking, [])
        self.assertEqual(result.warnings, [])

    def test_the_stored_flag_says_what_happened(self):
        flag = _check(_build_pdf(*A2, text="Our Project")).as_flag()

        self.assertTrue(flag["has_text"])
        self.assertFalse(flag["unreadable"])
        self.assertIn(TEAM_CODE, {w["code"] for w in flag["warnings"]})
