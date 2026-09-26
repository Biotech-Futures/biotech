"""Docx generation: {{Variable}} templates for marks summaries and certificates,
plus director names and signature images in rendered documents."""
import io
import zipfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from apps.grading.models import (
    ComponentFeedback,
    Grade,
    GradingSettings,
    GroupMarkingCategories,
)
from apps.grading.services.docx import (
    _render_token_template,
    _sum_marks,
)

from .fixtures import _GradingFixture, _build_docx, _seed_doc_templates


class ClientDocxTemplateTests(_GradingFixture):
    """Both templates render correctly from uploaded {{Variable}} templates,
    with every variable replaced and our data in place.
    """

    @staticmethod
    def _document_xml(data: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return z.read("word/document.xml").decode("utf8")

    def test_marks_release_tokens_filled(self):
        from apps.grading.services.docx import marks_summary_context, render_marks_summary
        from apps.grading.views.student import _grades_payload

        _seed_doc_templates()
        Grade.objects.create(
            submission=self.saq_submission, criterion=self.saq_c1,
            mark=Decimal("4.00"), comment="Nice claim.", graded_by=self.staff,
        )
        Grade.objects.create(
            submission=self.poster_submission, criterion=self.poster_c1,
            mark=Decimal("3.50"), graded_by=self.staff,
        )
        ComponentFeedback.objects.create(
            group=self.group, component=self.poster, comment="Strong poster overall.",
        )
        components = _grades_payload(self.group, 2026)
        data = render_marks_summary(marks_summary_context(self.group, 2026, components))
        xml = self._document_xml(data)
        self.assertNotIn("<<[", xml)
        self.assertNotIn("{{", xml)
        self.assertIn("BTF-TEST-1", xml)      # TeamCode
        self.assertIn("S1 4 (Nice claim.)", xml)  # S1 mark as a whole number, S1 comment
        self.assertIn("total 7.5 ", xml)         # CombinedTotal = 4.00 + 3.50
        self.assertIn("Strong poster overall.", xml)  # PosterComment

    def test_director_positions_fill_both_templates(self):
        from apps.grading.services.docx import (
            certificate_context,
            marks_summary_context,
            render_certificate_data,
            render_marks_summary_data,
            scan_template_data,
        )

        row = GradingSettings.load()
        row.director_1_position, row.director_2_position = "Chair", "Co-Chair"
        row.save()
        template = _build_docx("{{Director1Position}} and {{Director2Position}}")
        summary = render_marks_summary_data(template, marks_summary_context(self.group, 2026, []))
        certificate = render_certificate_data(
            template, certificate_context("Ada Grader", "BTF-TEST-1", 2026)
        )
        self.assertIn("Chair and Co-Chair", self._document_xml(summary))
        self.assertIn("Chair and Co-Chair", self._document_xml(certificate))
        for kind in ("marks-summary", "certificate"):
            report = scan_template_data(kind, template)
            self.assertEqual(
                (report["present"], report["unknown"]),
                (["Director1Position", "Director2Position"], []),
                kind,
            )

    def test_saq_comment_is_the_overall_saq_comment(self):
        from apps.grading.services.docx import (
            marks_summary_context,
            render_marks_summary_data,
            scan_template_data,
        )
        from apps.grading.views.student import _grades_payload

        ComponentFeedback.objects.create(
            group=self.group, component=self.poster, comment="Strong poster overall.",
        )
        ComponentFeedback.objects.create(
            group=self.group, component=self.saq, comment="Clear, well argued answers.",
        )
        template = _build_docx("Poster: {{PosterComment}} | SAQ: {{SAQComment}}")
        context = marks_summary_context(self.group, 2026, _grades_payload(self.group, 2026))
        xml = self._document_xml(render_marks_summary_data(template, context))
        self.assertIn("Poster: Strong poster overall. | SAQ: Clear, well argued answers.", xml)

        report = scan_template_data("marks-summary", template)
        self.assertEqual(report["unknown"], [])

    def test_marks_summary_carries_the_markers_categories(self):
        from apps.grading.services.docx import marks_summary_context, render_marks_summary

        row = GradingSettings.load()
        row.marks_summary_template = SimpleUploadedFile("marks.docx", _build_docx(
            "Project: {{ProjectCategory}} | Solution: {{SolutionCategory}}"
        ))
        row.save()
        GroupMarkingCategories.objects.create(
            group=self.group,
            product_categories=["Health and Medicine", "Other"],
            product_category_other="Wearables",
            solution_category="Other",
            solution_category_other="App",
        )
        xml = self._document_xml(render_marks_summary(
            marks_summary_context(self.group, 2026, [])
        ))
        self.assertIn("Project: Health and Medicine, Wearables | Solution: App", xml)

    def test_marks_summary_headings_count_the_team(self):
        from apps.grading.services.docx import marks_summary_context, render_marks_summary_data
        from apps.groups.models.group_members import GroupMembership
        from apps.users.models import StudentProfile, User

        roles = GroupMembership.MembershipRoleChoices
        for i, school in enumerate(("North High", "South High")):
            student = User.objects.create_user(
                email=f"s{i}@example.com", first_name=f"Stu{i}", last_name="Dent", password="pw12345!",
            )
            GroupMembership.objects.create(group=self.group, user=student, membership_role=roles.STUDENT)
            StudentProfile.objects.create(
                user=student, pg_first_name="P", pg_last_name="G", school_name=school, year_lvl="11",
            )
        for i in range(2):
            supervisor = User.objects.create_user(
                email=f"sup{i}@example.com", first_name=f"Sup{i}", last_name="Visor", password="pw12345!",
            )
            GroupMembership.objects.create(group=self.group, user=supervisor, membership_role=roles.SUPERVISOR)
        GroupMarkingCategories.objects.create(
            group=self.group, product_categories=["Health and Medicine", "Regulation Ethics"],
        )

        template = _build_docx(
            "{{ProjectCategoryHeading}}: {{ProjectCategory}} | "
            "{{SupervisorHeading}}: {{Supervisors}} | {{SchoolHeading}}: {{Schools}}"
        )
        xml = self._document_xml(render_marks_summary_data(
            template, marks_summary_context(self.group, 2026, [])
        ))
        self.assertIn(
            "Project Categories: Health and Medicine, Regulation Ethics | "
            "Supervisors: Sup0 Visor, Sup1 Visor | Schools: North High, South High",
            xml,
        )

    def test_marks_summary_categories_blank_when_none_chosen(self):
        from apps.grading.services.docx import marks_summary_context

        context = marks_summary_context(self.group, 2026, [])
        self.assertEqual(context["project_category"], "")
        self.assertEqual(context["solution_category"], "")

    def _render_dated_certificate(self) -> str:
        from apps.grading.services import docx as docx_service

        row = GradingSettings.load()
        row.certificate_template = SimpleUploadedFile("cert.docx", _build_docx("Issued {{Date}}"))
        row.save()
        return self._document_xml(docx_service.render_participation_certificate(
            docx_service.certificate_context("Ada Grader", "BTF-TEST-1", 2026)
        ))

    def test_certificate_date_is_the_release_date_not_the_download_date(self):
        from datetime import datetime, timezone as dt_timezone

        from apps.grading.models import CertificatesRelease

        release = CertificatesRelease.load()
        release.released_at = datetime(2026, 3, 14, 3, 0, tzinfo=dt_timezone.utc)
        release.save()
        # Downloaded on any later day, the certificate keeps its release date.
        self.assertIn("Issued 14 March 2026", self._render_dated_certificate())

    def test_certificate_date_is_the_release_day_in_sydney(self):
        from datetime import datetime, timezone as dt_timezone

        from apps.grading.models import CertificatesRelease

        # 20:00 UTC on 13 March is 7am on 14 March in Sydney (AEDT, UTC+11).
        release = CertificatesRelease.load()
        release.released_at = datetime(2026, 3, 13, 20, 0, tzinfo=dt_timezone.utc)
        release.save()
        xml = self._render_dated_certificate()
        self.assertIn("Issued 14 March 2026", xml)
        self.assertNotIn("13 March 2026", xml)

    def test_certificate_date_before_release_is_today(self):
        from django.utils import timezone

        today = timezone.localdate()
        self.assertIn(f"Issued {today.day} {today:%B %Y}", self._render_dated_certificate())

    def test_the_document_setup_test_render_uses_sydneys_today_even_after_release(self):
        from datetime import datetime, timezone as dt_timezone
        from unittest import mock

        from apps.grading.models import CertificatesRelease
        from apps.grading.services.docx import render_certificate_data, sample_certificate_context

        release = CertificatesRelease.load()
        release.released_at = datetime(2025, 12, 1, 3, 0, tzinfo=dt_timezone.utc)
        release.save()
        # 20:00 UTC on 13 March is already 14 March in Sydney.
        now = datetime(2026, 3, 13, 20, 0, tzinfo=dt_timezone.utc)
        with mock.patch("django.utils.timezone.now", return_value=now):
            context = sample_certificate_context()
        xml = self._document_xml(render_certificate_data(_build_docx("Issued {{Date}}"), context))
        self.assertIn("Issued 14 March 2026", xml)
        self.assertNotIn("1 December 2025", xml)

    def _render_year(self, *, download_year: int = 2031) -> tuple[str, str]:
        """{{Year}} in a summary and a certificate, downloaded in ``download_year``."""
        from apps.grading.services.docx import (
            certificate_context,
            marks_summary_context,
            render_certificate_data,
            render_marks_summary_data,
        )

        template = _build_docx("Chair {{Year}}")
        summary = render_marks_summary_data(
            template, marks_summary_context(self.group, download_year, [])
        )
        certificate = render_certificate_data(
            template, certificate_context("Ada Grader", "BTF-TEST-1", download_year)
        )
        return self._document_xml(summary), self._document_xml(certificate)

    @staticmethod
    def _release_both_at(moment):
        from apps.grading.models import CertificatesRelease, MarksRelease

        for model in (MarksRelease, CertificatesRelease):
            release = model.load()
            release.released_at = moment
            release.save()

    def test_year_is_the_release_year_not_the_download_year(self):
        from datetime import datetime, timezone as dt_timezone

        self._release_both_at(datetime(2026, 3, 14, 3, 0, tzinfo=dt_timezone.utc))
        summary, certificate = self._render_year(download_year=2031)
        self.assertIn("Chair 2026", summary)
        self.assertIn("Chair 2026", certificate)

    def test_year_is_the_release_year_in_sydney(self):
        from datetime import datetime, timezone as dt_timezone

        # 14:00 UTC on 31 December is 1am on 1 January in Sydney (AEDT, UTC+11).
        self._release_both_at(datetime(2026, 12, 31, 14, 0, tzinfo=dt_timezone.utc))
        summary, certificate = self._render_year()
        self.assertIn("Chair 2027", summary)
        self.assertIn("Chair 2027", certificate)

    def test_year_before_release_is_this_year(self):
        from django.utils import timezone

        summary, certificate = self._render_year()
        self.assertIn(f"Chair {timezone.localdate().year}", summary)
        self.assertIn(f"Chair {timezone.localdate().year}", certificate)

    def test_the_test_render_year_is_sydneys_this_year_even_after_release(self):
        from datetime import datetime, timezone as dt_timezone
        from unittest import mock

        from apps.grading.services.docx import (
            render_certificate_data,
            render_marks_summary_data,
            sample_certificate_context,
            sample_marks_summary_context,
        )

        self._release_both_at(datetime(2025, 12, 1, 3, 0, tzinfo=dt_timezone.utc))
        # 14:00 UTC on 31 December 2026 is already 2027 in Sydney.
        now = datetime(2026, 12, 31, 14, 0, tzinfo=dt_timezone.utc)
        with mock.patch("django.utils.timezone.now", return_value=now):
            summary_context = sample_marks_summary_context()
            certificate_context = sample_certificate_context()
        template = _build_docx("Chair {{Year}}")
        for data in (
            render_marks_summary_data(template, summary_context),
            render_certificate_data(template, certificate_context),
        ):
            self.assertIn("Chair 2027", self._document_xml(data))

    def test_the_template_check_recognises_year(self):
        from apps.grading.services.docx import scan_template_data

        for kind in ("marks-summary", "certificate"):
            report = scan_template_data(kind, _build_docx("Chair {{Year}}"))
            self.assertEqual((report["present"], report["unknown"]), (["Year"], []), kind)

    def test_the_template_check_recognises_date(self):
        from apps.grading.services.docx import scan_template_data

        report = scan_template_data("certificate", _build_docx("{{Date}}"))
        self.assertEqual((report["present"], report["unknown"]), (["Date"], []))

    def test_certificate_tokens_named_as_document_setup_lists_them(self):
        from apps.grading.services.docx import (
            certificate_context,
            render_participation_certificate,
            scan_template_data,
        )

        template = _build_docx(
            "{{FirstName}} {{LastName}} — {{ProjectTitle}} — {{Director1Name}}, {{Director2Name}}"
        )
        row = GradingSettings.load()
        row.director_1_name, row.director_2_name = "Mr William Nixon", "Mr Joshua Aarons"
        row.certificate_template = SimpleUploadedFile("cert.docx", template)
        row.save()

        xml = self._document_xml(render_participation_certificate(
            certificate_context("Ada Grader", "BTF-TEST-1", 2026, first_name="Ada", last_name="Grader")
        ))
        self.assertIn("Ada Grader — BTF-TEST-1 — Mr William Nixon, Mr Joshua Aarons", xml)
        report = scan_template_data("certificate", template)
        self.assertEqual(
            report["present"],
            ["Director1Name", "Director2Name", "FirstName", "LastName", "ProjectTitle"],
        )
        self.assertEqual(report["unknown"], [])


class DocxEngineEdgeTests(SimpleTestCase):
    """The rendering engine's awkward inputs: tokens Word has split across
    runs, tokens inside tables, corrupt images, and unknown control aliases.
    Exercised at the engine seam — no DB needed."""

    @staticmethod
    def _document_xml(data: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return z.read("word/document.xml").decode("utf8")

    def test_a_token_split_across_runs_is_still_replaced(self):
        from docx import Document as NewDocument

        doc = NewDocument()
        p = doc.add_paragraph()
        # Word routinely fragments "{{TeamCode}}" like this after edits.
        p.add_run("{{Team")
        p.add_run("Code}}")
        buf = io.BytesIO()
        doc.save(buf)

        xml = self._document_xml(_render_token_template(buf.getvalue(), {"TeamCode": "BTF-9"}))
        self.assertIn("BTF-9", xml)
        self.assertNotIn("{{", xml)

    def test_a_space_between_split_tokens_survives_in_word(self):
        from docx import Document as NewDocument

        doc = NewDocument()
        p = doc.add_paragraph()
        # How Word split the certificate's name line: the space between the
        # two tokens ends up at the start of a text node after the splice.
        for text in ("{{", "F", "irstName}} {{", "L", "astName}}"):
            p.add_run(text)
        buf = io.BytesIO()
        doc.save(buf)

        xml = self._document_xml(_render_token_template(
            buf.getvalue(), {"FirstName": "Jane", "LastName": "Doe"}
        ))
        self.assertIn('<w:t xml:space="preserve"> Doe</w:t>', xml)

    def test_headings_are_plural_only_for_more_than_one(self):
        from apps.grading.services.docx import marks_release_fields

        def headings(count):
            fields = marks_release_fields({
                "project_category_count": count,
                "supervisor_count": count,
                "school_count": count,
            })
            return (fields["ProjectCategoryHeading"], fields["SupervisorHeading"],
                    fields["SchoolHeading"])

        singular = ("Project Category", "Supervisor", "School")
        self.assertEqual(headings(0), singular)
        self.assertEqual(headings(1), singular)
        self.assertEqual(headings(2), ("Project Categories", "Supervisors", "Schools"))

    def test_characters_a_docx_cannot_hold_are_cleaned_not_fatal(self):
        data = _build_docx("{{Comment}}")
        # Shift+Enter and a page break pasted from Word, plus a stray control
        # character; tabs, newlines, accents and XML specials stay as typed.
        comment = "Line one\x0bline two\x0cend\x01. Tab\there & <José>"

        xml = self._document_xml(_render_token_template(data, {"Comment": comment}))
        self.assertIn("Line one line two end. Tab\there &amp; &lt;José&gt;", xml)

    def test_tokens_inside_table_cells_are_replaced(self):
        from docx import Document as NewDocument

        doc = NewDocument()
        table = doc.add_table(rows=1, cols=1)
        table.cell(0, 0).paragraphs[0].add_run("Team {{TeamCode}}")
        buf = io.BytesIO()
        doc.save(buf)

        xml = self._document_xml(_render_token_template(buf.getvalue(), {"TeamCode": "BTF-9"}))
        self.assertIn("BTF-9", xml)
        self.assertNotIn("{{TeamCode}}", xml)

    def test_tokens_in_headers_and_footers_are_replaced(self):
        from docx import Document as NewDocument

        doc = NewDocument()
        doc.add_paragraph("Team {{TeamCode}}")
        section = doc.sections[0]
        section.header.paragraphs[0].add_run("Marks {{TeamCode}}")
        section.footer.paragraphs[0].add_run("{{Director1Name}}")
        # A different first page gets its own footer, filled as well.
        section.different_first_page_header_footer = True
        section.first_page_footer.paragraphs[0].add_run("First page {{TeamCode}}")
        buf = io.BytesIO()
        doc.save(buf)

        rendered = _render_token_template(
            buf.getvalue(), {"TeamCode": "BTF-9", "Director1Name": "Mr William Nixon"}
        )
        with zipfile.ZipFile(io.BytesIO(rendered)) as z:
            parts = {
                n: z.read(n).decode("utf8") for n in z.namelist()
                if n.startswith(("word/header", "word/footer")) and n.endswith(".xml")
            }
        text = " | ".join(parts.values())
        self.assertIn("Marks BTF-9", text)
        self.assertIn("Mr William Nixon", text)
        self.assertIn("First page BTF-9", text)
        self.assertNotIn("{{", text)

    def test_a_signature_token_in_a_footer_becomes_an_image(self):
        from docx import Document as NewDocument

        doc = NewDocument()
        doc.add_paragraph("Body")
        doc.sections[0].footer.paragraphs[0].add_run("{{Director1Signature}}")
        buf = io.BytesIO()
        doc.save(buf)

        rendered = _render_token_template(
            buf.getvalue(), {}, images={"Director1Signature": DirectorSignatureTests.PNG_1PX}
        )
        with zipfile.ZipFile(io.BytesIO(rendered)) as z:
            footer = z.read("word/footer1.xml").decode("utf8")
            footer_rels = z.read("word/_rels/footer1.xml.rels").decode("utf8")
        self.assertIn("<w:drawing>", footer)
        self.assertNotIn("{{", footer)
        self.assertIn("media/", footer_rels)

    def test_a_document_without_headers_or_footers_gains_none(self):
        rendered = _render_token_template(_build_docx("Team {{TeamCode}}"), {"TeamCode": "BTF-9"})
        with zipfile.ZipFile(io.BytesIO(rendered)) as z:
            names = z.namelist()
        self.assertFalse([n for n in names if n.startswith(("word/header", "word/footer"))], names)

    def test_a_corrupt_signature_image_does_not_sink_the_document(self):
        data = _build_docx("{{Director1Signature}} {{Director1Name}}")
        rendered = _render_token_template(
            data,
            {"Director1Name": "Prof. Alice Adams"},
            images={"Director1Signature": b"plainly not pixels"},
        )
        with zipfile.ZipFile(io.BytesIO(rendered)) as z:
            names = z.namelist()
            xml = z.read("word/document.xml").decode("utf8")
        # No picture landed, the token is cleared, and the name still prints.
        self.assertFalse([n for n in names if n.startswith("word/media/")], names)
        self.assertNotIn("{{", xml)
        self.assertIn("Prof. Alice Adams", xml)

    def test_sum_marks_skips_unparseable_values(self):
        total = _sum_marks([
            {"mark": "3.50"},
            {"mark": "abc"},
            {"mark": None},
            {"mark": "1.25"},
        ])
        self.assertEqual(total, Decimal("4.75"))

    def test_marks_print_as_whole_numbers_when_whole(self):
        from apps.grading.services.docx import marks_release_fields

        poster = [{"mark": m} for m in ("4.00", "4.50", "1.92", "", "5.00")]
        saq = [{"mark": "5.00"}, {"mark": "5.00"}]
        fields = marks_release_fields({"components": [
            {"code": "POSTER", "criteria": poster},
            {"code": "SAQ", "criteria": saq},
        ]})
        self.assertEqual(
            [fields[f"P{i}"] for i in range(1, 6)], ["4", "4.5", "1.92", "", "5"]
        )
        self.assertEqual(fields["PosterTotal"], "15.42")
        self.assertEqual(fields["SAQTotal"], "10")
        self.assertEqual(fields["CombinedTotal"], "25.42")
        # No marks at all still prints a plain zero.
        self.assertEqual(marks_release_fields({})["CombinedTotal"], "0")


class DirectorSignatureTests(_GradingFixture):
    """Director names and signature images reach the rendered documents.

    The client's own templates carry no director placeholders, so these build
    a token template on the fly — the same path an admin gets after adding the
    tokens to their docx.
    """

    # Smallest valid PNG: python-docx reads its real dimensions from IHDR.
    PNG_1PX = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    @staticmethod
    def _token_template(text: str) -> bytes:
        from docx import Document as NewDocument

        doc = NewDocument()
        doc.add_paragraph(text)
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    def _configure(self, template_text: str, *, with_signatures: bool):
        from apps.grading.models import GradingSettings

        settings_row = GradingSettings.load()
        settings_row.director_1_name = "Prof. Alice Adams"
        settings_row.director_2_name = "Dr. Bob Brown"
        settings_row.marks_summary_template = SimpleUploadedFile(
            "tpl.docx", self._token_template(template_text)
        )
        if with_signatures:
            settings_row.director_1_signature = SimpleUploadedFile("sig1.png", self.PNG_1PX)
            settings_row.director_2_signature = SimpleUploadedFile("sig2.png", self.PNG_1PX)
        settings_row.save()
        return settings_row

    def _render(self):
        from apps.grading.services.docx import marks_summary_context, render_marks_summary

        return render_marks_summary(marks_summary_context(self.group, 2026, []))

    def test_director_names_fill_their_tokens(self):
        self._configure(
            "Signed: {{Director1Name}} and {{Director2Name}}", with_signatures=False
        )
        with zipfile.ZipFile(io.BytesIO(self._render())) as z:
            xml = z.read("word/document.xml").decode("utf8")
        self.assertIn("Prof. Alice Adams", xml)
        self.assertIn("Dr. Bob Brown", xml)
        self.assertNotIn("{{", xml)

    def test_signature_tokens_become_images(self):
        self._configure(
            "{{Director1Signature}} {{Director2Signature}} {{Director1Name}}",
            with_signatures=True,
        )
        payload = self._render()
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            names = z.namelist()
            xml = z.read("word/document.xml").decode("utf8")
        # Two inline pictures, and the token text gone. Only one media part is
        # expected: both fixtures are byte-identical, so python-docx stores the
        # image once and both drawings point at it.
        self.assertEqual(xml.count("<w:drawing>"), 2, xml[:400])
        self.assertTrue([n for n in names if n.startswith("word/media/")], names)
        self.assertNotIn("{{", xml)
        self.assertIn("Prof. Alice Adams", xml)

    def test_missing_signature_leaves_document_renderable(self):
        # No signature uploaded: the token clears and the name still prints.
        self._configure("{{Director1Signature}}{{Director1Name}}", with_signatures=False)
        with zipfile.ZipFile(io.BytesIO(self._render())) as z:
            names = z.namelist()
            xml = z.read("word/document.xml").decode("utf8")
        self.assertFalse([n for n in names if n.startswith("word/media/")], names)
        self.assertNotIn("{{", xml)
        self.assertIn("Prof. Alice Adams", xml)
