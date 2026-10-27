"""A finalist's slides download under one name everywhere: "2026_BTF07_Slides.pdf"."""
import io
import tempfile
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.storage import reset_managed_storage_caches
from apps.grading.models import FinalistFlag
from apps.groups.models import GroupMembership, Groups
from apps.management.models import FinalistSlides
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.submissions.models import FinalistEntry
from apps.submissions.services import current_cohort
from apps.submissions.slides_download import slides_download_name
from apps.users.models import User

from tests.apps.submissions.test_finalist import _pdf

STORAGE = "apps.submissions.slides_download.get_slides_storage"


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class SlidesDownloadNameTests(TestCase):
    def setUp(self):
        media = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(media.cleanup)
        setting = override_settings(MEDIA_ROOT=media.name)
        setting.enable()
        self.addCleanup(setting.disable)
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        self.year = current_cohort()
        self.name = f"{self.year}_BTF07_Slides.pdf"
        self.group = Groups.objects.create(group_name="BTF07", year=self.year)
        FinalistFlag.objects.create(group=self.group, notified=True)
        self.student = User.objects.create_user(email="student@test.local", password="x")
        RoleAssignmentHistory.objects.create(
            user=self.student, role=Roles.objects.create(role_name="student"), valid_from=timezone.now(), valid_to=None
        )
        GroupMembership.objects.create(group=self.group, user=self.student, membership_role="student")
        self.admin = User.objects.create_user(email="admin@test.local", password="x", is_staff=True)

        uploaded = self._client(self.student).post(
            reverse("finalist-presentation", kwargs={"group_id": self.group.id}),
            {"file": _pdf("Our FINAL deck (v3).PDF")},
            format="multipart",
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.content)
        FinalistSlides.objects.create(
            group=self.group, file=FinalistEntry.objects.get(group=self.group).presentation, submitted_at=timezone.now()
        )

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def _get(self, user, route, query=""):
        response = self._client(user).get(reverse(route, kwargs={"group_id": self.group.id}) + query)
        # Read to the end, so the test client closes the file. Closing it here
        # instead would end the test's database connection on Postgres.
        if response.streaming:
            self.addCleanup(lambda: b"".join(response.streaming_content))
        return response

    def test_admins_open_and_download_it_under_the_one_name(self):
        opened = self._get(self.admin, "management:presentation-slides-file")
        downloaded = self._get(self.admin, "management:presentation-slides-file", "?download=1")

        self.assertEqual(opened["Content-Disposition"], f'inline; filename="{self.name}"')
        self.assertEqual(downloaded["Content-Disposition"], f'attachment; filename="{self.name}"')
        self.assertEqual(b"".join(downloaded.streaming_content), b"%PDF-1.7\nslides\n%%EOF\n")

    def test_the_team_previews_and_downloads_it_under_the_same_name(self):
        previewed = self._get(self.student, "finalist-presentation-preview")
        downloaded = self._get(self.student, "finalist-presentation-download")

        self.assertEqual(previewed["Content-Disposition"], f'inline; filename="{self.name}"')
        self.assertEqual(downloaded["Content-Disposition"], f'attachment; filename="{self.name}"')

    def test_on_azure_the_signed_link_carries_the_name(self):
        signed = "https://store.blob.core.windows.net/slides/x.pdf?sig=x"
        azure = mock.Mock(is_remote=True)
        azure.backend.url.return_value = signed
        with mock.patch(STORAGE, return_value=azure):
            response = self._get(self.admin, "management:presentation-slides-file", "?download=1")

        self.assertEqual((response.status_code, response["Location"]), (302, signed))
        self.assertEqual(azure.backend.url.call_args.kwargs["parameters"], {
            "content_disposition": f'attachment; filename="{self.name}"',
            "content_type": "application/pdf",
        })

    def test_a_link_that_cannot_be_signed_is_streamed_instead(self):
        azure = mock.Mock(is_remote=True)
        azure.backend.url.side_effect = RuntimeError("no key")
        azure.open.return_value = io.BytesIO(b"%PDF slides")
        with mock.patch(STORAGE, return_value=azure):
            response = self._get(self.student, "finalist-presentation-download")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], f'attachment; filename="{self.name}"')
        self.assertEqual(b"".join(response.streaming_content), b"%PDF slides")

    def test_a_file_gone_from_storage_is_a_404(self):
        FinalistSlides.objects.update(file={"storage_key": "gone.pdf", "name": "gone.pdf", "mime": "application/pdf"})
        self.assertEqual(self._get(self.admin, "management:presentation-slides-file").status_code, 404)

    def test_the_name_keeps_the_type_in_lower_case_and_nothing_else_of_the_upload(self):
        self.assertEqual(slides_download_name(self.group, {"name": "Deck.PPTX"}), f"{self.year}_BTF07_Slides.pptx")
        self.assertEqual(slides_download_name(self.group, {"storage_key": "k/a.ppt"}), f"{self.year}_BTF07_Slides.ppt")
        self.assertEqual(slides_download_name(self.group, {}), f"{self.year}_BTF07_Slides")
