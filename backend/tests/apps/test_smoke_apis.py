"""End-to-end smoke test for chat-attachment and resource-file APIs.

Exercises every upload/download path the FE team needs against an in-memory
SQLite database, using DRF's ``APIClient`` so no live server is required.
Prints a per-role transcript to stdout. Run via:

    DJANGO_SETTINGS_MODULE=config.test_settings \
        venv/Scripts/python.exe manage.py test \
        tests.apps.test_smoke_apis -v 2

The transcript is the deliverable for FE handoff; the assertions guard
against regressions in expected status codes.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from apps.chat.models import Messages
from apps.common.storage import get_chat_storage, get_resource_storage
from apps.groups.models import Groups, GroupMembership, Countries, CountryStates, Tracks
from apps.resources.models import (
    Resources,
    ResourceAudience,
    Roles,
    RoleAssignmentHistory,
)
from apps.users.models import AdminScope
from tests.apps._helpers import StorageCleanupMixin


CHANNEL_TEST_SETTINGS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class APISmokeTest(StorageCleanupMixin, TestCase):
    """Single transcript-style smoke test. Each step prints its result."""

    storage_attr = "_storage_for_cleanup"
    storage_keys_attr = "_storage_keys_for_cleanup"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The mixin's tearDown can only walk one storage at a time. Track
        # both containers separately and combine in tearDown.
        cls._chat_storage = get_chat_storage()
        cls._resource_storage = get_resource_storage()

    def setUp(self):
        super().setUp()
        User = get_user_model()

        # ---- geography & tracks ----
        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track_a = Tracks.objects.create(track_name="Track A", state=self.state)
        self.track_b = Tracks.objects.create(track_name="Track B", state=self.state)

        # ---- users ----
        self.student = User.objects.create_user(
            email="student@test.com", password="pw", first_name="Stu", last_name="Dent",
            track=self.track_a,
        )
        self.mentor = User.objects.create_user(
            email="mentor@test.com", password="pw", first_name="Men", last_name="Tor",
            track=self.track_a,
        )
        self.outsider = User.objects.create_user(
            email="outsider@test.com", password="pw", first_name="Out", last_name="Sider",
            track=self.track_b,
        )
        self.track_admin_a = User.objects.create_user(
            email="track-admin-a@test.com", password="pw", first_name="TA", last_name="A",
            track=self.track_a,
        )
        self.global_admin = User.objects.create_user(
            email="global-admin@test.com", password="pw", first_name="Gl", last_name="Adm",
            track=self.track_a,
        )

        # ---- roles & assignments ----
        self.role_mentor = Roles.objects.create(role_name="mentor")
        self.role_student = Roles.objects.create(role_name="student")
        now = timezone.now()
        future = now + timedelta(days=365)
        RoleAssignmentHistory.objects.create(
            user=self.mentor, role=self.role_mentor, valid_from=now, valid_to=future,
        )
        RoleAssignmentHistory.objects.create(
            user=self.student, role=self.role_student, valid_from=now, valid_to=future,
        )

        # ---- AdminScope (the canonical admin source) ----
        AdminScope.objects.create(user=self.global_admin, is_global=True)
        AdminScope.objects.create(
            user=self.track_admin_a, track=self.track_a, is_global=False,
        )

        # ---- groups & membership ----
        self.group_a = Groups.objects.create(group_name="Group-A", track=self.track_a)
        self.group_b = Groups.objects.create(group_name="Group-B", track=self.track_b)
        GroupMembership.objects.create(user=self.student, group=self.group_a)
        GroupMembership.objects.create(user=self.mentor, group=self.group_a)
        GroupMembership.objects.create(user=self.outsider, group=self.group_b)

        # cleanup tracking
        self._storage_for_cleanup = self._chat_storage
        self._storage_keys_for_cleanup = []

        # transcript
        self._lines = []

    def tearDown(self):
        # Combine chat + resource storage cleanup paths.
        for storage_key in getattr(self, "_chat_keys", []):
            try:
                if self._chat_storage.exists(storage_key):
                    self._chat_storage.delete(storage_key)
            except OSError:
                pass
        for storage_key in getattr(self, "_resource_keys", []):
            try:
                if self._resource_storage.exists(storage_key):
                    self._resource_storage.delete(storage_key)
            except OSError:
                pass
        super().tearDown()

    # ---- transcript helpers ----------------------------------------------

    def _record(self, who, method, path, status_code, expected, note=""):
        marker = "OK" if status_code == expected else "MISMATCH"
        line = f"  [{marker:>8}] {who:<12} {method:<6} {path:<70} -> {status_code} (expected {expected}) {note}"
        self._lines.append(line)
        # Print immediately so transcript is visible even if assertion fails.
        print(line, flush=True)

    def _client_for(self, user):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    # ---- the smoke test --------------------------------------------------

    def test_smoke_transcript(self):
        print("\n" + "=" * 100)
        print("CHAT + RESOURCE UPLOAD/DOWNLOAD SMOKE TEST")
        print("=" * 100)

        self._chat_keys = []
        self._resource_keys = []

        # ===== Section 1: Chat attachment upload + download =====
        print("\n[1] CHAT ATTACHMENTS")
        print("-" * 100)
        chat_upload_url = reverse(
            "group-messages-upload", kwargs={"group_pk": self.group_a.id}
        )
        list_url = reverse(
            "group-messages-list", kwargs={"group_pk": self.group_a.id}
        )

        # 1a. anonymous -> 403 (DRF returns 403 when no auth class supplies a
        # 401 challenge, which is the case for our token-based auth).
        anon = APIClient()
        resp = anon.post(chat_upload_url, {}, format="multipart")
        self._record("anon", "POST", chat_upload_url, resp.status_code, 403)
        self.assertEqual(resp.status_code, 403)

        # 1b. student member uploads to own group -> 201
        student_client = self._client_for(self.student)
        upload_file = SimpleUploadedFile(
            "smoke.pdf", b"%PDF-1.4 student upload", content_type="application/pdf"
        )
        resp = student_client.post(
            chat_upload_url,
            {"uploaded_file": upload_file, "message_text": "from student"},
            format="multipart",
        )
        self._record("student", "POST", chat_upload_url, resp.status_code, 201, "(member of group_a)")
        self.assertEqual(resp.status_code, 201, resp.content)
        student_msg = resp.json()
        student_msg_id = student_msg["id"]
        student_attachment = student_msg["attachments"][0]
        self._chat_keys.append(student_attachment["storage_key"]) if "storage_key" in student_attachment else None
        # storage_key isn't in public payload — pull it from DB
        self._chat_keys.append(
            Messages.objects.get(pk=student_msg_id).attachments.first().storage_key
        )
        student_attachment_id = student_attachment["id"]

        # 1c. outsider (different track, not member) uploads -> 403
        outsider_client = self._client_for(self.outsider)
        resp = outsider_client.post(
            chat_upload_url,
            {"uploaded_file": SimpleUploadedFile("x.pdf", b"data", "application/pdf")},
            format="multipart",
        )
        self._record("outsider", "POST", chat_upload_url, resp.status_code, 403, "(not member, different track)")
        self.assertEqual(resp.status_code, 403)

        # 1d. track admin for track A uploads to group_a (admin via track scope, not membership) -> 201
        ta_client = self._client_for(self.track_admin_a)
        ta_file = SimpleUploadedFile("ta.pdf", b"%PDF track-admin", "application/pdf")
        resp = ta_client.post(
            chat_upload_url,
            {"uploaded_file": ta_file, "message_text": "from track admin"},
            format="multipart",
        )
        self._record("track_admin", "POST", chat_upload_url, resp.status_code, 201, "(AdminScope track_a)")
        self.assertEqual(resp.status_code, 201)
        self._chat_keys.append(
            Messages.objects.get(pk=resp.json()["id"]).attachments.first().storage_key
        )

        # 1e. global admin uploads -> 201
        ga_client = self._client_for(self.global_admin)
        ga_file = SimpleUploadedFile("ga.pdf", b"%PDF global-admin", "application/pdf")
        resp = ga_client.post(
            chat_upload_url,
            {"uploaded_file": ga_file, "message_text": "from global admin"},
            format="multipart",
        )
        self._record("global_admin", "POST", chat_upload_url, resp.status_code, 201, "(AdminScope is_global)")
        self.assertEqual(resp.status_code, 201)
        self._chat_keys.append(
            Messages.objects.get(pk=resp.json()["id"]).attachments.first().storage_key
        )

        # 1f. list messages as student -> 200
        resp = student_client.get(list_url)
        self._record("student", "GET", list_url, resp.status_code, 200)
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["items"]
        # Confirm public-shape contract: no sender_user / no resource_ids / has attachments[]
        self.assertGreaterEqual(len(items), 1)
        sample = items[0]
        for forbidden in ("sender_user", "resource_ids", "deleted_at", "is_deleted"):
            self.assertNotIn(forbidden, sample, f"field '{forbidden}' leaked into list payload")
        self.assertIn("attachments", sample)
        self._lines.append("  [   shape] message list payload omits internal fields, includes attachments[]")
        print(self._lines[-1], flush=True)

        # 1g. attachment download as student member -> 200 / streamed bytes
        download_url = reverse(
            "group-messages-attachment-download",
            kwargs={
                "group_pk": self.group_a.id,
                "pk": student_msg_id,
                "attachment_pk": student_attachment_id,
            },
        )
        resp = student_client.get(download_url)
        self._record("student", "GET", download_url, resp.status_code, 200)
        self.assertEqual(resp.status_code, 200)
        body = b"".join(resp.streaming_content) if hasattr(resp, "streaming_content") else resp.content
        self.assertEqual(body, b"%PDF-1.4 student upload")
        self.assertIn("attachment", resp.headers.get("Content-Disposition", ""))

        # 1h. attachment download as outsider (no group access) -> 403
        resp = outsider_client.get(download_url)
        self._record("outsider", "GET", download_url, resp.status_code, 403)
        self.assertEqual(resp.status_code, 403)

        # 1i. mentor edits own message within window -> 200
        mentor_client = self._client_for(self.mentor)
        # Mentor needs an own message first
        mentor_send = mentor_client.post(
            reverse("group-messages-list", kwargs={"group_pk": self.group_a.id}),
            {"message_text": "mentor hello"},
            format="json",
        )
        self.assertEqual(mentor_send.status_code, 201)
        mentor_msg_id = mentor_send.json()["id"]
        edit_url = reverse(
            "group-messages-detail",
            kwargs={"group_pk": self.group_a.id, "pk": mentor_msg_id},
        )
        resp = mentor_client.patch(edit_url, {"message_text": "mentor edited"}, format="json")
        self._record("mentor (sender)", "PATCH", edit_url, resp.status_code, 200, "(self-action window)")
        self.assertEqual(resp.status_code, 200)

        # 1j. student tries to edit mentor's message -> 403
        resp = student_client.patch(edit_url, {"message_text": "hijack"}, format="json")
        self._record("student", "PATCH", edit_url, resp.status_code, 403, "(not sender, not admin)")
        self.assertEqual(resp.status_code, 403)

        # 1k. track admin moderates (deletes mentor's message) -> 204
        resp = ta_client.delete(edit_url)
        self._record("track_admin", "DELETE", edit_url, resp.status_code, 204, "(AdminScope track_a)")
        self.assertEqual(resp.status_code, 204)

        # ===== Section 2: Resource files =====
        print("\n[2] RESOURCE FILES")
        print("-" * 100)
        resource_list_url = reverse("resource-files-list")

        # 2a. student tries to create a resource -> 403 (only admins manage)
        resource_file = SimpleUploadedFile(
            "guide.pdf", b"%PDF resource guide", content_type="application/pdf"
        )
        resp = student_client.post(
            resource_list_url,
            {
                "name": "Student Tries Upload",
                "description": "should fail",
                "track": self.track_a.id,
                "visibility_scope": "track",
                "uploaded_file": SimpleUploadedFile("x.pdf", b"x", "application/pdf"),
            },
            format="multipart",
        )
        self._record("student", "POST", resource_list_url, resp.status_code, 403, "(not admin)")
        self.assertEqual(resp.status_code, 403)

        # 2b. track admin creates a track-scoped resource -> 201
        resp = ta_client.post(
            resource_list_url,
            {
                "name": "Track-A Reading List",
                "description": "Required reading for Track A",
                "track": self.track_a.id,
                "visibility_scope": "track",
                "uploaded_file": resource_file,
            },
            format="multipart",
        )
        self._record("track_admin", "POST", resource_list_url, resp.status_code, 201, "(scoped to track_a)")
        self.assertEqual(resp.status_code, 201, resp.content)
        ta_resource_id = resp.json()["id"]
        self._resource_keys.append(
            Resources.objects.get(pk=ta_resource_id).storage_key
        )

        # 2c. global admin creates a public resource -> 201
        resp = ga_client.post(
            resource_list_url,
            {
                "name": "Public Handbook",
                "description": "Public to all",
                "visibility_scope": "public",
                "uploaded_file": SimpleUploadedFile(
                    "public.pdf", b"%PDF public", "application/pdf"
                ),
            },
            format="multipart",
        )
        self._record("global_admin", "POST", resource_list_url, resp.status_code, 201, "(public)")
        self.assertEqual(resp.status_code, 201, resp.content)
        public_res_id = resp.json()["id"]
        self._resource_keys.append(Resources.objects.get(pk=public_res_id).storage_key)

        # 2d. track admin tries to create resource scoped to OTHER track -> 403
        resp = ta_client.post(
            resource_list_url,
            {
                "name": "Cross-Track Attempt",
                "description": "should fail",
                "track": self.track_b.id,
                "visibility_scope": "track",
                "uploaded_file": SimpleUploadedFile("y.pdf", b"y", "application/pdf"),
            },
            format="multipart",
        )
        self._record("track_admin", "POST", resource_list_url, resp.status_code, 403, "(track_b is out of scope)")
        self.assertEqual(resp.status_code, 403)

        # 2e. /access/ endpoint as student in track_a -> 200
        access_url = reverse("resource-files-access", kwargs={"pk": ta_resource_id})
        resp = student_client.get(access_url)
        self._record("student", "GET", access_url, resp.status_code, 200, "(track-scoped, student in track_a)")
        self.assertEqual(resp.status_code, 200)
        access_payload = resp.json()
        for required in ("access_mode", "external_url", "file_name", "download_url"):
            self.assertIn(required, access_payload)

        # 2f. outsider (track_b) tries to access track_a resource -> 403
        resp = outsider_client.get(access_url)
        self._record("outsider", "GET", access_url, resp.status_code, 403, "(track_b cannot see track_a)")
        self.assertEqual(resp.status_code, 403)

        # 2g. download as student in track_a -> 200 streamed bytes
        download_url = reverse("resource-files-download", kwargs={"pk": ta_resource_id})
        resp = student_client.get(download_url)
        self._record("student", "GET", download_url, resp.status_code, 200)
        self.assertEqual(resp.status_code, 200)
        body = b"".join(resp.streaming_content) if hasattr(resp, "streaming_content") else resp.content
        self.assertEqual(body, b"%PDF resource guide")

        # 2h. download as outsider -> 403
        resp = outsider_client.get(download_url)
        self._record("outsider", "GET", download_url, resp.status_code, 403)
        self.assertEqual(resp.status_code, 403)

        # 2i. anyone authenticated can access public resource
        public_access = reverse("resource-files-access", kwargs={"pk": public_res_id})
        resp = outsider_client.get(public_access)
        self._record("outsider", "GET", public_access, resp.status_code, 200, "(public scope)")
        self.assertEqual(resp.status_code, 200)

        # 2j. list /resource-files/ as student -> only resources they can see
        resp = student_client.get(resource_list_url)
        self._record("student", "GET", resource_list_url, resp.status_code, 200)
        self.assertEqual(resp.status_code, 200)
        page = resp.json()
        names = {r["name"] for r in page.get("results", page if isinstance(page, list) else [])}
        # Student is in track_a, should see Track-A reading list AND public handbook
        self.assertIn("Track-A Reading List", names)
        self.assertIn("Public Handbook", names)

        # 2k. list as outsider -> only public (no track_a)
        resp = outsider_client.get(resource_list_url)
        self._record("outsider", "GET", resource_list_url, resp.status_code, 200)
        self.assertEqual(resp.status_code, 200)
        page = resp.json()
        names = {r["name"] for r in page.get("results", page if isinstance(page, list) else [])}
        self.assertIn("Public Handbook", names)
        self.assertNotIn("Track-A Reading List", names)

        # ---- summary banner ----
        print("\n" + "=" * 100)
        print(f"SMOKE TEST COMPLETE — {len(self._lines)} checks recorded above")
        print("=" * 100)
