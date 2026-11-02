"""Re-issuing the results emails to everyone (Resend To Everyone), and
certificates from a fillable PDF template as PDFs, in those emails and every
download (apps.management.services.certificate_pdf); a Word template's stay
Word files."""
import io
import zipfile

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.groups.models import GroupMembership
from apps.management.models import EmailDelivery, GradingSettings, ResultsSupervisorEmail, ResultsTeamEmail
from apps.management.services import certificate_pdf, results_notify
from apps.users.models import User

from tests.apps.grading.fixtures import _GradingFixture
from tests.apps.management import test_results_emails as base
from tests.apps.management.test_certificate_pdf import field, fillable, text_of
from tests.apps.management.test_results_emails import LOCMEM, SEND, _files

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
NAME_BOX = [171, 330, 671, 380]
STUDENT_PDF = fillable(field("Name", NAME_BOX), field("ProjectTitle", [221, 230, 621, 300]))
MENTOR_PDF = fillable(field("Name", NAME_BOX), field("Typo", [221, 230, 621, 300]))


def is_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF")


def squashed(text: str) -> str:
    return "".join(text.split())


@override_settings(EMAIL_BACKEND=LOCMEM)
class ResultsTestCase(_GradingFixture):
    """The results emails' own setup: a submitted group with two students, a
    mentor and their supervisor, marks and certificates released."""

    def setUp(self):
        base.ResultsEmailTests.setUp(self)

    def send(self, audience, which=""):
        r = self.client.post(reverse(SEND), {"audience": audience, "which": which}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        return r.json()


class ResendToEveryoneTests(ResultsTestCase):
    def test_every_group_is_emailed_again_with_the_templates_as_they_are_now(self):
        self.send("groups")
        first = sorted(address for m in mail.outbox for address in m.to)
        mail.outbox.clear()
        # The client changes the certificate template, then re-issues.
        self.assertEqual(self.send("groups")["groups"]["emailed"], 1)
        self.assertEqual(mail.outbox, [], "a plain send skips groups already emailed")

        body = self.send("groups", "all")

        self.assertEqual(sorted(address for m in mail.outbox for address in m.to), first)
        self.assertEqual(body["groups"]["emailed"], 1)
        self.assertEqual(ResultsTeamEmail.objects.filter(group=self.group).count(), 1)

    def test_every_supervisor_is_emailed_again(self):
        self.send("supervisors")
        mail.outbox.clear()

        self.send("supervisors", "all")

        self.assertEqual([m.to for m in mail.outbox], [["sam.lee@example.com"]])
        self.assertEqual(ResultsSupervisorEmail.objects.count(), 1)

    def test_resending_one_audience_leaves_the_other_as_it_was(self):
        self.send("groups")
        self.send("supervisors")
        mail.outbox.clear()

        self.send("supervisors", "all")

        self.assertTrue(ResultsTeamEmail.objects.filter(group=self.group).exists())
        self.assertTrue(EmailDelivery.objects.filter(group=self.group).exists())
        self.assertEqual([m.to for m in mail.outbox], [["sam.lee@example.com"]])

    def test_an_unknown_which_is_refused(self):
        r = self.client.post(reverse(SEND), {"audience": "groups", "which": "everyone"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.json()["detail"], 'which must be "missed" or "all"')


class PdfTemplateTests(ResultsTestCase):
    """Both certificate templates fillable PDFs; the marks summary a Word file."""

    def setUp(self):
        super().setUp()
        row = GradingSettings.load()
        row.certificate_template = SimpleUploadedFile("cert.pdf", STUDENT_PDF)
        row.mentor_certificate_template = SimpleUploadedFile("mentor.pdf", MENTOR_PDF)
        row.save()

    def certificates(self, message):
        return {
            name: (data, mimetype) for name, data, mimetype in (
                a for a in message.attachments if isinstance(a, tuple)
            ) if "Certificate" in name
        }

    def test_the_group_email_carries_pdf_certificates_and_the_marks_summary_as_word(self):
        self.send("groups")

        message = mail.outbox[0]
        certificates = self.certificates(message)
        self.assertEqual(len(certificates), 3)
        for name, (data, mimetype) in certificates.items():
            self.assertTrue(name.endswith(".pdf") and is_pdf(data), name)
            self.assertEqual(mimetype, certificate_pdf.PDF)
        mentor = next(data for name, (data, _) in certificates.items() if "Mentor_Certificate" in name)
        self.assertIn("MoMentor", squashed(text_of(mentor)))
        marks = [name for name in _files(message) if "Marks" in name]
        self.assertTrue(marks and all(name.endswith(".docx") for name in marks), marks)

    def test_the_supervisor_email_carries_pdf_certificates(self):
        self.send("supervisors")
        certificates = self.certificates(mail.outbox[0])
        self.assertTrue(certificates)
        self.assertTrue(all(name.endswith(".pdf") for name in certificates), certificates)

    def test_a_name_the_fonts_cannot_print_stops_that_email_and_says_why_on_download(self):
        User.objects.filter(email="amy@example.com").update(first_name="سارة")
        failed = self.send("groups")["runs"]["groups"]["run"]["missed"]
        self.assertEqual(mail.outbox, [])
        self.assertFalse(ResultsTeamEmail.objects.filter(group=self.group).exists())
        # The Release Results page says why beside each of the group's people.
        self.assertTrue(failed and all("can't be printed in the Name field" in f["reason"] for f in failed), failed)

        amy = User.objects.get(email="amy@example.com")
        r = self.client.get(reverse("management:all-results-certificate", args=[self.group.id, amy.id]))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("can't be printed", r.json()["detail"])
        r = self.client.get(reverse("management:all-results-certificates"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_admin_downloads_are_pdfs(self):
        zipped = self.client.get(reverse("management:all-results-certificates"))
        self.assertEqual(zipped.status_code, status.HTTP_200_OK)
        with zipfile.ZipFile(io.BytesIO(zipped.content)) as archive:
            names = archive.namelist()
            self.assertGreaterEqual(len(names), 3)
            self.assertTrue(all(name.endswith(".pdf") and is_pdf(archive.read(name)) for name in names), names)

        listed = self.client.get(reverse("management:all-results")).json()["people"]
        self.assertTrue(listed and all(row["file_name"].endswith(".pdf") for row in listed), listed)

        student = GroupMembership.objects.filter(group=self.group, membership_role="student").first().user
        one = self.client.get(reverse("management:all-results-certificate", args=[self.group.id, student.id]))
        self.assertEqual(one.status_code, status.HTTP_200_OK)
        self.assertEqual(one["Content-Type"], certificate_pdf.PDF)
        self.assertIn(".pdf", one["Content-Disposition"])

    def test_a_groups_own_results_list_and_download_pdfs(self):
        amy = User.objects.get(email="amy@example.com")
        own = APIClient()
        own.force_authenticate(amy)
        listed = own.get(reverse("management:group-results", args=[self.group.id])).json()["certificates"]
        self.assertTrue(listed and all(row["file_name"].endswith(".pdf") for row in listed), listed)

        mine = own.get(reverse("management:group-results-certificate", args=[self.group.id, amy.id]))
        self.assertEqual(mine.status_code, status.HTTP_200_OK)
        self.assertEqual(mine["Content-Type"], certificate_pdf.PDF)
        self.assertIn(".pdf", mine["Content-Disposition"])

    def test_document_setup_tests_and_downloads_the_pdf(self):
        tried = self.client.get(reverse("management:settings-test-render", args=["certificate"]))
        saved = self.client.get(reverse("management:settings-template-download", args=["mentor-certificate"]))
        marks = self.client.get(reverse("management:settings-test-render", args=["marks-summary"]))

        self.assertEqual(tried["Content-Type"], certificate_pdf.PDF)
        self.assertIn("JaneDoe", squashed(text_of(tried.content)))
        self.assertEqual(saved["Content-Type"], certificate_pdf.PDF)
        self.assertIn("BTF_Mentor_Certificate_Template.pdf", saved["Content-Disposition"])
        self.assertEqual(saved.content, MENTOR_PDF)
        self.assertEqual(marks["Content-Type"], DOCX_MIME)

    def test_a_test_email_carries_pdf_certificates_as_the_real_one_does(self):
        r = self.client.post(
            reverse("management:test-email", args=["results-groups"]),
            {"recipient": str(self.group.id), "to": "tester@example.com"}, format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        certificates = self.certificates(mail.outbox[0])
        self.assertTrue(certificates)
        self.assertTrue(all(name.endswith(".pdf") and mimetype == certificate_pdf.PDF
                            for name, (_data, mimetype) in certificates.items()), certificates)

    def test_the_release_page_names_pdf_certificates(self):
        names = results_notify.example_file_names(results_notify.GROUPS, 2026)
        self.assertEqual([name.rpartition(".")[2] for name in names], ["pdf", "pdf", "docx"])
        # The Attachments list a group's preview shows, before anything is made.
        audience = results_notify.results_audience()
        planned = results_notify.team_files(results_notify.Documents(audience.year), audience, self.group)
        self.assertEqual(
            [file.name.rpartition(".")[2] for file in planned], ["pdf"] * (len(planned) - 1) + ["docx"],
        )


class PdfTemplateUploadTests(ResultsTestCase):
    def upload(self, field_name, name, data):
        return self.client.patch(
            reverse("management:settings"), {field_name: SimpleUploadedFile(name, data)}, format="multipart",
        )

    def test_a_fillable_pdf_is_saved_as_a_pdf_and_scanned_for_its_fields(self):
        r = self.upload("mentor_certificate_template", "Final Design", MENTOR_PDF)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertRegex(r.json()["mentor_certificate_template"], r"/Final.Design\.pdf$")

        scan = self.client.get(reverse("management:settings-template-scan", args=["mentor-certificate"])).json()
        self.assertEqual(scan, {"uploaded": True, "present": ["Name"], "unknown": ["Typo"]})

        candidate = self.client.post(
            reverse("management:settings-test-render", args=["certificate"]),
            {"file": SimpleUploadedFile("candidate.pdf", STUDENT_PDF)}, format="multipart",
        )
        self.assertEqual(candidate.status_code, status.HTTP_200_OK)
        self.assertEqual(candidate["Content-Type"], certificate_pdf.PDF)

    def test_a_word_file_named_pdf_is_saved_as_a_docx(self):
        with GradingSettings.load().certificate_template.open("rb") as fh:
            word = fh.read()
        r = self.upload("certificate_template", "cert.pdf", word)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertTrue(r.json()["certificate_template"].endswith("/cert.docx"))

    def test_unusable_pdfs_are_refused_and_the_template_kept(self):
        before = GradingSettings.load().certificate_template.name
        for name, data, message in (
            ("plain.pdf", fillable(), "no form fields"),
            ("broken.pdf", b"%PDF-1.7 truncated", "could not be opened as a PDF"),
            ("rotated.pdf", fillable(field("Name", NAME_BOX), rotate=90), "rotated"),
            ("locked.pdf", fillable(field("Name", NAME_BOX), password="pw"), "password-protected"),
            ("button.pdf", fillable(field("Name", NAME_BOX, ft="/Btn")), "isn't a text field"),
        ):
            with self.subTest(name=name):
                r = self.upload("certificate_template", name, data)
                self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(message, str(r.json()))
        self.assertEqual(GradingSettings.load().certificate_template.name, before)

    def test_the_marks_summary_cannot_be_a_pdf(self):
        r = self.upload("marks_summary_template", "marks.pdf", STUDENT_PDF)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(".docx", str(r.json()))


class WordTemplateTests(ResultsTestCase):
    def test_word_templates_still_make_word_certificates(self):
        self.send("groups")
        files = _files(mail.outbox[0])
        certificates = [name for name in files if "Certificate" in name]
        self.assertTrue(certificates)
        self.assertTrue(all(name.endswith(".docx") and files[name].startswith(b"PK") for name in certificates))
