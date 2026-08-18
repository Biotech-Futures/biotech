"""Tests for the three submission attachment slots.

Covers the checks that protect a real team: a genuine PDF is accepted, a file
merely *named* like one is not, replacing an attachment does not leave the old
file behind, and nothing can be attached after the deadline.
"""
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.common.storage import reset_managed_storage_caches
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import Deadline, Submission
from apps.submissions.storage import SUBMISSION_FILE_SERVICE
from apps.users.models import User
from rest_framework.test import APIClient


def _pdf_bytes(body: bytes = b"a tiny poster") -> bytes:
    """Minimal content that passes the "is it really a PDF" check."""
    return b"%PDF-1.7\n" + body + b"\n%%EOF\n"


def _pdf_upload(name="poster.pdf", content=None):
    return SimpleUploadedFile(
        name, content if content is not None else _pdf_bytes(), content_type="application/pdf"
    )


# Local filesystem storage keeps these tests off Azure entirely.
@override_settings(USE_AZURE_BLOB_STORAGE=False)
class SubmissionFileTests(TestCase):
    def setUp(self):
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        roles = {n: Roles.objects.create(role_name=n) for n in ("student", "mentor")}
        self.group = Groups.objects.create(group_name="BTF-FILES")

        self.student = User.objects.create_user(
            email="filestudent@test.local", password="testUser@123",
            first_name="File", last_name="Student",
        )
        RoleAssignmentHistory.objects.create(
            user=self.student, role=roles["student"], valid_from=timezone.now(), valid_to=None
        )
        GroupMembership.objects.create(
            group=self.group, user=self.student, membership_role="student"
        )

        Deadline.objects.create(closes_at=timezone.now() + timedelta(days=1), is_active=True)

        self.client = APIClient()
        self.client.force_authenticate(user=self.student)

        self.detail_url = reverse("group-submission", kwargs={"group_id": self.group.id})
        self.submit_url = reverse("group-submission-submit", kwargs={"group_id": self.group.id})

    def _file_url(self, slot):
        return reverse(
            "group-submission-file", kwargs={"group_id": self.group.id, "slot": slot}
        )

    def _upload(self, slot, upload):
        return self.client.post(self._file_url(slot), {"file": upload}, format="multipart")

    def _stored(self, slot):
        return getattr(Submission.objects.get(group=self.group), slot)

    # ------------------------------------------------------------- accepting
    def test_poster_pdf_is_accepted(self):
        response = self._upload("poster", _pdf_upload())

        self.assertEqual(response.status_code, 200)
        stored = self._stored("poster")
        self.assertEqual(stored["name"], "poster.pdf")
        self.assertEqual(stored["mime"], "application/pdf")
        self.assertTrue(SUBMISSION_FILE_SERVICE.exists(stored["storage_key"]))

    def test_prototype_accepts_a_non_pdf(self):
        upload = SimpleUploadedFile(
            "model.stl", b"solid teapot\nendsolid\n", content_type="application/octet-stream"
        )
        self.assertEqual(self._upload("prototype", upload).status_code, 200)
        self.assertEqual(self._stored("prototype")["name"], "model.stl")

    # ------------------------------------------------------------- rejecting
    def test_non_pdf_rejected_for_poster(self):
        upload = SimpleUploadedFile("notes.txt", b"just text", content_type="text/plain")
        self.assertEqual(self._upload("poster", upload).status_code, 400)
        self.assertFalse(Submission.objects.filter(group=self.group).exists())

    def test_file_renamed_to_pdf_is_rejected(self):
        # Named and declared as a PDF, but the contents are not one. This is the
        # check that extension and content-type alone would miss.
        upload = SimpleUploadedFile(
            "poster.pdf", b"this is plain text pretending", content_type="application/pdf"
        )
        response = self._upload("poster", upload)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Submission.objects.filter(group=self.group).exists())

    def test_executable_rejected_for_prototype(self):
        # "MZ" is the leading signature of a Windows executable.
        upload = SimpleUploadedFile(
            "demo.bin", b"MZ\x90\x00 payload", content_type="application/octet-stream"
        )
        self.assertEqual(self._upload("prototype", upload).status_code, 400)

    def test_executable_extension_rejected_even_when_disguised(self):
        upload = SimpleUploadedFile(
            "demo.exe.zip", b"PK\x03\x04 archive", content_type="application/zip"
        )
        self.assertEqual(self._upload("prototype", upload).status_code, 400)

    def test_unknown_slot_is_404(self):
        url = reverse(
            "group-submission-file", kwargs={"group_id": self.group.id, "slot": "nonsense"}
        )
        response = self.client.post(url, {"file": _pdf_upload()}, format="multipart")
        self.assertEqual(response.status_code, 404)

    def test_missing_file_is_rejected(self):
        self.assertEqual(
            self.client.post(self._file_url("poster"), {}, format="multipart").status_code, 400
        )

    # ------------------------------------------------------------- replacing
    def test_replacing_a_file_removes_the_old_one(self):
        self._upload("poster", _pdf_upload("first.pdf"))
        first_key = self._stored("poster")["storage_key"]

        self._upload("poster", _pdf_upload("second.pdf", _pdf_bytes(b"replacement")))
        second_key = self._stored("poster")["storage_key"]

        self.assertNotEqual(first_key, second_key)
        self.assertEqual(self._stored("poster")["name"], "second.pdf")
        self.assertFalse(SUBMISSION_FILE_SERVICE.exists(first_key))
        self.assertTrue(SUBMISSION_FILE_SERVICE.exists(second_key))

    def test_deleting_a_file_clears_the_slot(self):
        self._upload("poster", _pdf_upload())
        key = self._stored("poster")["storage_key"]

        response = self.client.delete(self._file_url("poster"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self._stored("poster"))
        self.assertFalse(SUBMISSION_FILE_SERVICE.exists(key))

    def test_deleting_an_empty_slot_is_404(self):
        self.assertEqual(self.client.delete(self._file_url("report")).status_code, 404)

    # ----------------------------------------------------------- downloading
    def test_download_returns_the_file(self):
        self._upload("poster", _pdf_upload())
        url = reverse(
            "group-submission-file-download",
            kwargs={"group_id": self.group.id, "slot": "poster"},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"%PDF-", b"".join(response.streaming_content))

    # -------------------------------------------------------------- submitting
    def test_cannot_submit_without_a_poster(self):
        response = self.client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(Submission.objects.get(group=self.group).submitted_at)

    def test_can_submit_once_a_poster_is_attached(self):
        self._upload("poster", _pdf_upload())
        response = self.client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(Submission.objects.get(group=self.group).submitted_at)

    # ---------------------------------------------------------------- closing
    def test_uploads_refused_after_the_deadline(self):
        Deadline.objects.update(closes_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(self._upload("poster", _pdf_upload()).status_code, 403)

    def test_deletes_refused_after_the_deadline(self):
        self._upload("poster", _pdf_upload())
        Deadline.objects.update(closes_at=timezone.now() - timedelta(hours=1))

        self.assertEqual(self.client.delete(self._file_url("poster")).status_code, 403)
        # The attachment must survive the refused delete.
        self.assertIsNotNone(self._stored("poster"))
