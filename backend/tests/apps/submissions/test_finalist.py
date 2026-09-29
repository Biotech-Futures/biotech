"""Tests for the finalist round: access, availability, presentation and submit."""
import io
import zipfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.storage import reset_managed_storage_caches
from apps.grading.models import FinalistFlag
from apps.groups.models import GroupMembership, Groups
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import FinalistDeadline, FinalistEntry, FinalistSession
from apps.users.models import User


def _pdf(name="deck.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.7\nslides\n%%EOF\n", content_type="application/pdf")


def _pptx(name="deck.pptx"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("ppt/presentation.xml", "<p:presentation/>")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/octet-stream")


def _ppt(name="deck.ppt"):
    return SimpleUploadedFile(
        name, bytes.fromhex("D0CF11E0A1B11AE1") + b"\x00" * 64, content_type="application/vnd.ms-powerpoint"
    )


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class FinalistTests(TestCase):
    def setUp(self):
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        self.roles = {n: Roles.objects.create(role_name=n) for n in ("student", "mentor", "supervisor")}
        self.group = Groups.objects.create(group_name="BTF-FINAL")
        self.other = Groups.objects.create(group_name="BTF-OTHER")
        self.student = self._member("student")
        self.mentor = self._member("mentor")
        self.supervisor = self._member("supervisor")
        self.outsider = self._user("outsider@test.local", "student")
        self.admin = User.objects.create_user(
            email="admin@test.local", password="testUser@123", first_name="A", last_name="Admin",
            is_staff=True,
        )

        FinalistFlag.objects.create(group=self.group, notified=True)
        FinalistDeadline.objects.create(closes_at=timezone.now() + timedelta(days=3), is_active=True)
        self.morning = FinalistSession.objects.create(label="10:00 - 11:00 am", order=1)
        self.noon = FinalistSession.objects.create(label="11:40am - 12:30pm", order=2)

        self.url = reverse("finalist-entry", kwargs={"group_id": self.group.id})
        self.file_url = reverse("finalist-presentation", kwargs={"group_id": self.group.id})
        self.submit_url = reverse("finalist-submit", kwargs={"group_id": self.group.id})
        self.reopen_url = reverse("finalist-reopen", kwargs={"group_id": self.group.id})

    def _user(self, email, role):
        user = User.objects.create_user(
            email=email, password="testUser@123", first_name="Test", last_name=role.title()
        )
        RoleAssignmentHistory.objects.create(
            user=user, role=self.roles[role], valid_from=timezone.now(), valid_to=None
        )
        return user

    def _member(self, role):
        user = self._user(f"{role}@test.local", role)
        GroupMembership.objects.create(group=self.group, user=user, membership_role=role)
        return user

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _ready(self, client=None):
        client = client or self._client(self.student)
        client.put(self.url, {"session_ids": [self.morning.id]}, format="json")
        client.post(self.file_url, {"file": _pdf()}, format="multipart")
        return client

    # Access
    def test_every_member_role_can_read_a_notified_finalist_entry(self):
        for user in (self.student, self.mentor, self.supervisor):
            with self.subTest(user=user.email):
                response = self._client(user).get(self.url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([s["label"] for s in response.data["sessions"]],
                                 ["10:00 - 11:00 am", "11:40am - 12:30pm"])

    def test_a_group_flagged_but_not_yet_notified_is_not_a_finalist(self):
        FinalistFlag.objects.filter(group=self.group).update(notified=False)

        response = self._client(self.student).get(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "not_a_finalist")

    def test_a_group_that_is_not_a_finalist_is_refused(self):
        GroupMembership.objects.create(group=self.other, user=self.student, membership_role="student")
        url = reverse("finalist-entry", kwargs={"group_id": self.other.id})

        self.assertEqual(self._client(self.student).get(url).data["code"], "not_a_finalist")

    def test_someone_outside_the_team_is_refused(self):
        self.assertEqual(self._client(self.outsider).get(self.url).status_code, 403)

    def test_an_admin_can_edit_and_submit_on_the_teams_behalf(self):
        client = self._ready(self._client(self.admin))

        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FinalistEntry.objects.get(group=self.group).submitted_by, self.admin)

    def test_an_admin_still_cannot_edit_a_group_that_is_not_a_finalist(self):
        url = reverse("finalist-entry", kwargs={"group_id": self.other.id})

        response = self._client(self.admin).put(url, {"session_ids": [self.morning.id]}, format="json")

        self.assertEqual(response.data["code"], "not_a_finalist")

    # Availability
    def test_availability_is_saved(self):
        response = self._client(self.mentor).put(
            self.url, {"session_ids": [self.noon.id, self.morning.id]}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["entry"]["available_session_ids"], sorted([self.morning.id, self.noon.id]))

    def test_a_retired_session_cannot_be_chosen(self):
        self.noon.is_active = False
        self.noon.save()

        response = self._client(self.student).put(self.url, {"session_ids": [self.noon.id]}, format="json")

        self.assertEqual(response.status_code, 400)

    def test_a_retired_session_drops_out_of_the_teams_choices(self):
        client = self._client(self.student)
        client.put(self.url, {"session_ids": [self.morning.id, self.noon.id]}, format="json")
        self.noon.is_active = False
        self.noon.save()

        entry = client.get(self.url).data["entry"]
        self.assertEqual(entry["available_session_ids"], [self.morning.id])
        # The team can keep editing without the retired session blocking the save.
        response = client.put(self.url, {"session_ids": entry["available_session_ids"]}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_a_retired_session_alone_does_not_count_as_availability(self):
        client = self._client(self.student)
        client.put(self.url, {"session_ids": [self.noon.id]}, format="json")
        client.post(self.file_url, {"file": _pdf()}, format="multipart")
        self.noon.is_active = False
        self.noon.save()

        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.data["code"], "availability_required")

    def test_retired_sessions_are_not_offered(self):
        self.noon.is_active = False
        self.noon.save()

        labels = [s["label"] for s in self._client(self.student).get(self.url).data["sessions"]]
        self.assertEqual(labels, ["10:00 - 11:00 am"])

    # Presentation
    def test_pdf_pptx_and_ppt_are_accepted(self):
        client = self._client(self.student)
        for upload in (_pdf(), _pptx(), _ppt()):
            with self.subTest(name=upload.name):
                response = client.post(self.file_url, {"file": upload}, format="multipart")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["entry"]["presentation"]["name"], upload.name)

    def test_other_file_types_are_refused(self):
        upload = SimpleUploadedFile("deck.docx", b"PK\x03\x04rest", content_type="application/octet-stream")

        response = self._client(self.student).post(self.file_url, {"file": upload}, format="multipart")

        self.assertEqual(response.data["error"], "The presentation must be a PDF or PowerPoint file.")

    def test_a_file_named_like_a_presentation_but_not_one_is_refused(self):
        for name in ("deck.pdf", "deck.pptx", "deck.ppt"):
            with self.subTest(name=name):
                upload = SimpleUploadedFile(name, b"just some notes", content_type="application/pdf")
                response = self._client(self.student).post(self.file_url, {"file": upload}, format="multipart")
                self.assertIn("contents are not", response.data["error"])

    def test_a_zip_that_is_not_a_presentation_is_refused(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", "<w:document/>")
        upload = SimpleUploadedFile("deck.pptx", buffer.getvalue(), content_type="application/octet-stream")

        response = self._client(self.student).post(self.file_url, {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, 400)

    def test_a_presentation_over_25_mb_is_refused(self):
        upload = SimpleUploadedFile("deck.pdf", b"%PDF-" + b"0" * (25 * 1024 * 1024), content_type="application/pdf")

        response = self._client(self.student).post(self.file_url, {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertIn("larger than 25 MB", response.data["error"])

    def test_only_a_pdf_can_be_previewed(self):
        client = self._client(self.student)
        preview = reverse("finalist-presentation-preview", kwargs={"group_id": self.group.id})

        client.post(self.file_url, {"file": _pptx()}, format="multipart")
        self.assertEqual(client.get(preview).status_code, 404)

        client.post(self.file_url, {"file": _pdf()}, format="multipart")
        self.assertEqual(client.get(preview).status_code, 200)

    def test_the_presentation_can_be_removed(self):
        client = self._client(self.student)
        client.post(self.file_url, {"file": _pdf()}, format="multipart")

        response = client.delete(self.file_url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["entry"]["presentation"])

    # Submitting
    def test_submitting_needs_availability(self):
        client = self._client(self.student)
        client.post(self.file_url, {"file": _pdf()}, format="multipart")

        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.data["code"], "availability_required")

    def test_submitting_needs_a_presentation(self):
        client = self._client(self.student)
        client.put(self.url, {"session_ids": [self.morning.id]}, format="json")

        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.data["code"], "presentation_required")

    def test_submitting_freezes_availability_and_presentation(self):
        client = self._ready(self._client(self.supervisor))

        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 200)
        entry = response.data["entry"]
        self.assertTrue(entry["is_locked"])
        self.assertEqual(entry["submitted_session_ids"], [self.morning.id])
        self.assertEqual(entry["submitted_presentation"]["name"], "deck.pdf")

    def test_a_submitted_entry_cannot_be_edited_until_reopened(self):
        client = self._ready()
        client.post(self.submit_url, {}, format="json")

        refused = client.put(self.url, {"session_ids": [self.noon.id]}, format="json")
        self.assertEqual(refused.status_code, 409)

        self.assertEqual(client.post(self.reopen_url, {}, format="json").status_code, 200)
        self.assertEqual(
            client.put(self.url, {"session_ids": [self.noon.id]}, format="json").status_code, 200
        )

    def test_the_submitted_copy_stands_while_a_revision_is_unfinished(self):
        client = self._ready()
        client.post(self.submit_url, {}, format="json")
        client.post(self.reopen_url, {}, format="json")

        client.put(self.url, {"session_ids": [self.noon.id]}, format="json")
        client.post(self.file_url, {"file": _pptx()}, format="multipart")

        entry = FinalistEntry.objects.get(group=self.group)
        self.assertEqual(list(entry.submitted_sessions.values_list("id", flat=True)), [self.morning.id])
        self.assertEqual(entry.submitted_presentation["name"], "deck.pdf")
        self.assertEqual(entry.presentation["name"], "deck.pptx")

    # Deadline
    def test_nothing_can_be_saved_before_a_finalist_deadline_is_set(self):
        FinalistDeadline.objects.all().delete()

        response = self._client(self.student).put(self.url, {"session_ids": [self.morning.id]}, format="json")

        self.assertEqual(response.data["code"], "submissions_not_configured")

    def test_nothing_can_be_saved_after_the_finalist_deadline(self):
        FinalistDeadline.objects.update(closes_at=timezone.now() - timedelta(minutes=1))
        client = self._client(self.student)

        self.assertEqual(
            client.put(self.url, {"session_ids": [self.morning.id]}, format="json").data["code"],
            "submissions_closed",
        )
        self.assertEqual(client.post(self.file_url, {"file": _pdf()}, format="multipart").status_code, 403)
        self.assertFalse(client.get(self.url).data["deadline"]["is_open"])

    def test_the_finalist_deadline_is_independent_of_the_main_deadline(self):
        # No main submission deadline exists in this test at all.
        response = self._client(self.student).put(self.url, {"session_ids": [self.morning.id]}, format="json")

        self.assertEqual(response.status_code, 200)
