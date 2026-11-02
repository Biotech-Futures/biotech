"""Re-issuing the results emails to everyone (Resend To Everyone), and
certificates as PDFs in those emails and every download while the converter
is set (apps.management.services.certificate_pdf), Word files otherwise."""
import io
import zipfile
from unittest import mock

import requests
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.groups.models import GroupMembership
from apps.management.models import EmailDelivery, ResultsSupervisorEmail, ResultsTeamEmail
from apps.management.services import certificate_pdf
from apps.users.models import User

from tests.apps.grading.fixtures import _GradingFixture
from tests.apps.management import test_results_emails as base
from tests.apps.management.test_results_emails import LOCMEM, SEND, _files

CONVERTER = "http://localhost:3000"
PDF_BYTES = b"%PDF-1.7 a certificate"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def converted(*_args, **_kwargs):
    answer = mock.Mock(status_code=200, content=PDF_BYTES)
    return answer


@override_settings(EMAIL_BACKEND=LOCMEM, CERTIFICATE_PDF_URL="")
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


class CertificatePdfTests(ResultsTestCase):
    def certificates(self, files):
        return sorted(name for name in files if "Certificate" in name)

    @override_settings(CERTIFICATE_PDF_URL=CONVERTER)
    def test_the_group_email_carries_certificates_as_pdfs_and_the_marks_summary_as_word(self):
        with mock.patch.object(certificate_pdf.requests, "post", side_effect=converted) as post:
            self.send("groups")

        files = _files(mail.outbox[0])
        self.assertTrue(self.certificates(files))
        self.assertTrue(all(name.endswith(".pdf") for name in self.certificates(files)))
        self.assertTrue(all(files[name] == PDF_BYTES for name in self.certificates(files)))
        self.assertEqual([name for name in files if "Marks" in name and name.endswith(".docx")], [
            name for name in files if "Marks" in name
        ])
        url = post.call_args.args[0]
        self.assertEqual(url, f"{CONVERTER}/forms/libreoffice/convert")
        sent_name, sent_bytes = post.call_args.kwargs["files"]["files"]
        self.assertTrue(sent_name.endswith(".docx"))
        self.assertTrue(sent_bytes.startswith(b"PK"))

    @override_settings(CERTIFICATE_PDF_URL=CONVERTER)
    def test_a_converter_that_fails_leaves_word_files_and_the_email_still_goes(self):
        with mock.patch.object(certificate_pdf.requests, "post", side_effect=requests.ConnectionError("down")):
            self.send("groups")

        files = _files(mail.outbox[0])
        self.assertTrue(self.certificates(files))
        self.assertTrue(all(name.endswith(".docx") for name in self.certificates(files)))

    def test_without_a_converter_certificates_stay_word_files(self):
        with mock.patch.object(certificate_pdf.requests, "post") as post:
            self.send("groups")
        post.assert_not_called()
        self.assertTrue(all(name.endswith(".docx") for name in self.certificates(_files(mail.outbox[0]))))

    @override_settings(CERTIFICATE_PDF_URL=CONVERTER)
    def test_the_admin_downloads_are_pdfs(self):
        with mock.patch.object(certificate_pdf.requests, "post", side_effect=converted):
            zipped = self.client.get(reverse("management:all-results-certificates"))
            self.assertEqual(zipped.status_code, status.HTTP_200_OK)
            with zipfile.ZipFile(io.BytesIO(zipped.content)) as archive:
                names = archive.namelist()
                self.assertTrue(names)
                self.assertTrue(all(name.endswith(".pdf") for name in names), names)
                self.assertTrue(all(archive.read(name) == PDF_BYTES for name in names))

            student = GroupMembership.objects.filter(group=self.group, membership_role="student").first().user
            one = self.client.get(reverse("management:all-results-certificate", args=[self.group.id, student.id]))
        self.assertEqual(one.status_code, status.HTTP_200_OK)
        self.assertEqual(one["Content-Type"], certificate_pdf.PDF)
        self.assertIn(".pdf", one["Content-Disposition"])


    @override_settings(CERTIFICATE_PDF_URL=CONVERTER)
    def test_a_groups_own_download_and_document_setups_test_are_pdfs_too(self):
        amy = User.objects.get(email="amy@example.com")
        own = APIClient()
        own.force_authenticate(amy)
        with mock.patch.object(certificate_pdf.requests, "post", side_effect=converted):
            mine = own.get(reverse("management:group-results-certificate", args=[self.group.id, amy.id]))
            tried = self.client.get(reverse("management:settings-test-render", args=["certificate"]))
            marks = self.client.get(reverse("management:settings-test-render", args=["marks-summary"]))

        for response in (mine, tried):
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response["Content-Type"], certificate_pdf.PDF)
            self.assertIn(".pdf", response["Content-Disposition"])
        # Only certificates: the marks summary stays a Word file.
        self.assertEqual(marks["Content-Type"], DOCX_MIME)

class ConverterTests(_GradingFixture):
    @override_settings(CERTIFICATE_PDF_URL=CONVERTER + "/", CERTIFICATE_PDF_TIMEOUT_SECONDS=12)
    def test_it_asks_gotenberg_and_takes_only_a_real_pdf(self):
        with mock.patch.object(certificate_pdf.requests, "post", side_effect=converted) as post:
            self.assertEqual(
                certificate_pdf.as_pdf("2026_BTF_Student_Certificate_Amy.docx", b"PK word", DOCX_MIME),
                ("2026_BTF_Student_Certificate_Amy.pdf", PDF_BYTES, certificate_pdf.PDF),
            )
        self.assertEqual(post.call_args.args[0], f"{CONVERTER}/forms/libreoffice/convert")
        self.assertEqual(post.call_args.kwargs["timeout"], 12)

        not_pdf = mock.Mock(status_code=200, content=b"<html>error</html>")
        with mock.patch.object(certificate_pdf.requests, "post", return_value=not_pdf):
            self.assertEqual(
                certificate_pdf.as_pdf("2026_BTF_Student_Certificate_Amy.pdf", b"PK word", DOCX_MIME),
                ("2026_BTF_Student_Certificate_Amy.docx", b"PK word", DOCX_MIME),
            )

    def test_names_follow_whether_the_converter_is_set(self):
        with override_settings(CERTIFICATE_PDF_URL=""):
            self.assertEqual(certificate_pdf.extension(), "docx")
        with override_settings(CERTIFICATE_PDF_URL=CONVERTER):
            self.assertEqual(certificate_pdf.extension(), "pdf")
