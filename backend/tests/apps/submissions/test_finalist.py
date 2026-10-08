"""Tests for the finalist round: access, availability, presentation and submit.
The times are the Finalist Presentation tab's, each student gives their own
availability, and the submitted slides land in that tab's table."""
import io
import tempfile
import zipfile
from datetime import time

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.storage import reset_managed_storage_caches
from apps.grading.models import FinalistFlag
from apps.groups.models import GroupMembership, Groups
from apps.management.models import FinalistSlides, PresentationAvailability, PresentationSettings, PresentationSlot
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import FinalistEntry
from apps.submissions.services import current_cohort
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
        # Files are stored under fixed names; keep each test's in a throwaway folder.
        # A download a test leaves open can't be deleted on Windows; skip it.
        media = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(media.cleanup)
        setting = override_settings(MEDIA_ROOT=media.name)
        setting.enable()
        self.addCleanup(setting.disable)
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
        # This year's times, as set on Management > Finalist Presentation.
        year = current_cohort()
        self.morning = PresentationSlot.objects.create(year=year, starts_at=time(10), ends_at=time(11))
        self.noon = PresentationSlot.objects.create(year=year, starts_at=time(11, 40), ends_at=time(12, 30))
        # Shown to finalists, as Management turns them on once they're final.
        PresentationSettings.objects.create(times_shown=True)

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
        # A student submits the team's times; whoever submits uploads the slides.
        self._client(self.student).put(self.url, {"session_ids": [self.morning.id]}, format="json")
        client = client or self._client(self.student)
        client.post(self.file_url, {"file": _pdf()}, format="multipart")
        return client

    # Access
    def test_every_member_role_can_read_a_notified_finalist_entry(self):
        for user in (self.student, self.mentor, self.supervisor):
            with self.subTest(user=user.email):
                response = self._client(user).get(self.url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([s["label"] for s in response.data["sessions"]],
                                 ["10:00 – 11:00", "11:40 – 12:30"])

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
    def test_the_teams_availability_is_submitted_with_who_and_when(self):
        response = self._client(self.student).put(
            self.url, {"session_ids": [self.noon.id, self.morning.id]}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        entry = response.data["entry"]
        self.assertEqual(entry["available_session_ids"], sorted([self.morning.id, self.noon.id]))
        self.assertEqual(entry["availability_submitted_by_name"], "Test Student")
        self.assertIsNotNone(entry["availability_submitted_at"])
        # Kept as the team's answer, which the tab's Allocate Slot table reads.
        answer = PresentationAvailability.objects.get(group=self.group)
        self.assertEqual(sorted(answer.slots.values_list("id", flat=True)), sorted([self.morning.id, self.noon.id]))
        self.assertEqual(answer.submitted_by, self.student)

    def test_the_whole_team_shares_one_answer(self):
        self._client(self.student).put(self.url, {"session_ids": [self.morning.id]}, format="json")
        self.assertEqual(
            self._client(self.mentor).get(self.url).data["entry"]["available_session_ids"], [self.morning.id]
        )

        entry = self._client(self.mentor).put(self.url, {"session_ids": [self.noon.id]}, format="json").data["entry"]

        # The mentor's answer replaces the student's, for everyone.
        self.assertEqual((entry["available_session_ids"], entry["availability_submitted_by_name"]),
                         ([self.noon.id], "Test Mentor"))
        self.assertEqual(
            self._client(self.student).get(self.url).data["entry"]["available_session_ids"], [self.noon.id]
        )
        self.assertEqual(PresentationAvailability.objects.filter(group=self.group).count(), 1)

    def test_mentors_supervisors_and_admins_can_submit_it(self):
        for user in (self.mentor, self.supervisor, self.admin):
            with self.subTest(user=user.email):
                response = self._client(user).put(self.url, {"session_ids": [self.morning.id]}, format="json")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(PresentationAvailability.objects.get(group=self.group).submitted_by, user)

    def test_no_times_at_all_is_refused(self):
        response = self._client(self.student).put(self.url, {"session_ids": []}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Choose at least one session your team can attend.", str(response.data))
        self.assertFalse(PresentationAvailability.objects.exists())

    def test_times_carried_over_but_never_submitted_do_not_count(self):
        # As the migration leaves the students' old answers: ticked, not submitted.
        PresentationAvailability.objects.create(group=self.group).slots.set([self.morning])
        client = self._client(self.student)
        client.post(self.file_url, {"file": _pdf()}, format="multipart")

        entry = client.get(self.url).data["entry"]
        self.assertEqual((entry["available_session_ids"], entry["availability_submitted_at"]), ([self.morning.id], None))
        self.assertEqual(client.post(self.submit_url, {}, format="json").data["code"], "availability_required")

    def test_a_time_from_another_year_cannot_be_chosen(self):
        old = PresentationSlot.objects.create(year=current_cohort() - 1, starts_at=time(9), ends_at=time(10))

        response = self._client(self.student).put(self.url, {"session_ids": [old.id]}, format="json")

        self.assertEqual(response.status_code, 400)

    def test_a_removed_time_drops_out_of_a_students_choices(self):
        client = self._client(self.student)
        client.put(self.url, {"session_ids": [self.morning.id, self.noon.id]}, format="json")
        self.noon.delete()

        entry = client.get(self.url).data["entry"]
        self.assertEqual(entry["available_session_ids"], [self.morning.id])
        response = client.put(self.url, {"session_ids": entry["available_session_ids"]}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_a_removed_time_alone_does_not_count_as_availability(self):
        client = self._client(self.student)
        client.put(self.url, {"session_ids": [self.noon.id]}, format="json")
        client.post(self.file_url, {"file": _pdf()}, format="multipart")
        self.noon.delete()

        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.data["code"], "availability_required")

    def test_only_this_years_times_are_offered(self):
        PresentationSlot.objects.create(year=current_cohort() - 1, starts_at=time(9), ends_at=time(10))

        labels = [s["label"] for s in self._client(self.student).get(self.url).data["sessions"]]
        self.assertEqual(labels, ["10:00 – 11:00", "11:40 – 12:30"])

    # Presentation
    def test_pdf_pptx_and_ppt_are_accepted(self):
        client = self._client(self.student)
        for upload in (_pdf(), _pptx(), _ppt()):
            with self.subTest(name=upload.name):
                response = client.post(self.file_url, {"file": upload}, format="multipart")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["entry"]["presentation"]["name"], upload.name)

    def test_slides_are_stored_named_for_the_year_and_group(self):
        response = self._client(self.student).post(self.file_url, {"file": _pptx("Our Deck.pptx")}, format="multipart")

        self.assertEqual(response.status_code, 200)
        entry = FinalistEntry.objects.get(group=self.group)
        self.assertEqual(entry.presentation["storage_key"], f"{self.group.year}_BTF-FINAL_Slides.pptx")

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

    def test_while_the_times_are_hidden_none_are_offered_or_needed(self):
        PresentationSettings.objects.update(times_shown=False)
        client = self._client(self.student)
        body = client.get(self.url).json()
        self.assertEqual((body["times_shown"], body["sessions"]), (False, []))
        # Giving times is refused, and submitting doesn't wait for them.
        response = client.put(self.url, {"session_ids": [self.morning.id]}, format="json")
        self.assertEqual(response.data["code"], "times_not_shown")
        client.post(self.file_url, {"file": _pdf()}, format="multipart")
        response = client.post(self.submit_url, {}, format="json")
        self.assertEqual(response.status_code, 200, response.content)

    def test_submitting_needs_a_presentation(self):
        client = self._client(self.student)
        client.put(self.url, {"session_ids": [self.morning.id]}, format="json")

        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.data["code"], "presentation_required")

    def test_submitting_freezes_the_presentation_for_the_finalist_presentation_tab(self):
        client = self._ready(self._client(self.supervisor))

        response = client.post(self.submit_url, {}, format="json")

        self.assertEqual(response.status_code, 200)
        entry = response.data["entry"]
        self.assertTrue(entry["is_locked"])
        self.assertEqual(entry["submitted_presentation"]["name"], "deck.pdf")
        # The tab's Finalist Submissions table has it, and its Open serves it.
        slides = FinalistSlides.objects.get(group=self.group)
        self.assertEqual((slides.file["name"], slides.submitted_by), ("deck.pdf", self.supervisor))
        opened = self._client(self.admin).get(
            reverse("management:presentation-slides-file", kwargs={"group_id": self.group.id})
        )
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(b"".join(opened.streaming_content), b"%PDF-1.7\nslides\n%%EOF\n")
        opened.close()

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
        self.assertEqual(entry.submitted_presentation["name"], "deck.pdf")
        self.assertEqual(entry.presentation["name"], "deck.pptx")
        # The tab still shows the submitted slides until the next submit.
        self.assertEqual(FinalistSlides.objects.get(group=self.group).file["name"], "deck.pdf")

    # Due when the slides are; shown, not enforced
    def test_the_due_date_is_the_slides_due_date_from_notify_finalists(self):
        from datetime import date, datetime
        from zoneinfo import ZoneInfo

        from apps.management.models import FinalistEmailSettings

        FinalistEmailSettings.objects.update_or_create(pk=1, defaults={"slides_due": date(2026, 10, 16)})
        deadline = self._client(self.student).get(self.url).data["deadline"]
        # The end of that day, Sydney time.
        self.assertEqual(
            deadline["closes_at"], datetime(2026, 10, 16, 23, 59, tzinfo=ZoneInfo("Australia/Sydney"))
        )
        self.assertTrue(deadline["is_open"])

    def test_the_finalist_round_stays_open_without_a_deadline(self):
        client = self._client(self.student)
        # No finalist or main submission deadline exists in this test at all.
        deadline = client.get(self.url).data["deadline"]
        self.assertEqual((deadline["closes_at"], deadline["is_open"]), (None, True))

        self.assertEqual(client.put(self.url, {"session_ids": [self.morning.id]}, format="json").status_code, 200)
        self.assertEqual(client.post(self.file_url, {"file": _pdf()}, format="multipart").status_code, 200)
        self.assertEqual(client.post(self.submit_url, {}, format="json").status_code, 200)
        self.assertEqual(client.post(self.reopen_url, {}, format="json").status_code, 200)
