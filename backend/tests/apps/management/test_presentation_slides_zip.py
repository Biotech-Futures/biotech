"""Finalist Submissions' Download All: every finalist team's slides in one zip."""
import io
import tempfile
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.storage import reset_managed_storage_caches
from apps.grading.models import FinalistFlag
from apps.groups.models import Groups
from apps.management.models import FinalistSlides
from apps.management.views.presentation import MISSING_NOTE, SLIDES_FILES
from apps.submissions.services import current_cohort

from tests.apps._helpers import close_response
from tests.apps.grading.fixtures import _GradingFixture

ZIP = "management:presentation-slides-zip"
ZIP_FILE = "management:presentation-slides-zip-file"


@override_settings(USE_AZURE_BLOB_STORAGE=False)
class FinalistSlidesZipTests(_GradingFixture):
    def setUp(self):
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        media_setting = override_settings(MEDIA_ROOT=media.name)
        media_setting.enable()
        self.addCleanup(media_setting.disable)
        reset_managed_storage_caches()
        self.addCleanup(reset_managed_storage_caches)

        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.year = current_cohort()
        self.btf3 = self._finalist("BTF3")
        self.btf10 = self._finalist("BTF10")
        self._hand_in(self.btf3, "BTF3 slides.pdf", b"%PDF-1.4 three", "application/pdf")
        self._hand_in(self.btf10, "Deck.PPTX", b"PK pptx ten", "application/vnd.ms-powerpoint")

    def _finalist(self, name):
        team = Groups.objects.create(group_name=name)
        FinalistFlag.objects.create(group=team, flagged_by=self.staff)
        return team

    def _hand_in(self, team, name, content, mime):
        return FinalistSlides.objects.create(
            group=team,
            file=SLIDES_FILES.save_uploaded_file(
                SimpleUploadedFile(name, content, content_type=mime),
                content_type_field="mime",
                size_field="size",
                original_filename_field="name",
            ),
            submitted_at=timezone.now(),
        )

    def _make(self):
        return self.client.post(reverse(ZIP))

    def _fetch(self):
        response = self.client.get(reverse(ZIP_FILE))
        # Lets go of the file, so the temporary folder can be removed.
        self.addCleanup(close_response, response)
        return response

    def _archive(self):
        made = self._make()
        self.assertEqual(made.status_code, status.HTTP_200_OK, made.content)
        self.assertEqual(made.json(), {"file_name": f"{self.year}_BTF_Finalist_Slides.zip"})
        response = self._fetch()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response, zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content)))

    def test_every_teams_slides_in_one_zip_named_as_grading_names_them(self):
        response, archive = self._archive()

        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn(f'filename="{self.year}_BTF_Finalist_Slides.zip"', response["Content-Disposition"])
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        self.assertEqual(
            archive.namelist(), [f"{self.year}_BTF3_Slides.pdf", f"{self.year}_BTF10_Slides.pptx"]
        )
        self.assertEqual(archive.read(f"{self.year}_BTF3_Slides.pdf"), b"%PDF-1.4 three")
        self.assertEqual(archive.read(f"{self.year}_BTF10_Slides.pptx"), b"PK pptx ten")

    def test_teams_without_slides_and_non_finalists_are_left_out(self):
        self._finalist("BTF4")
        FinalistSlides.objects.create(group=self.group, file={"storage_key": "x", "name": "x.pdf"}, submitted_at=timezone.now())

        _, archive = self._archive()

        self.assertEqual(len(archive.namelist()), 2)

    def test_slides_that_cannot_be_read_leave_a_note(self):
        FinalistSlides.objects.filter(group=self.btf10).update(file={"storage_key": "gone.pptx", "name": "gone.pptx"})

        _, archive = self._archive()

        self.assertEqual(archive.namelist(), [f"{self.year}_BTF3_Slides.pdf", f"{self.year}_BTF10_Slides_MISSING.txt"])
        self.assertEqual(archive.read(f"{self.year}_BTF10_Slides_MISSING.txt").decode(), MISSING_NOTE)

    def test_many_teams_stay_in_order_while_read_a_few_at_once(self):
        for number in range(20, 29):
            team = self._finalist(f"BTF{number}")
            self._hand_in(team, "s.pdf", f"%PDF {number}".encode(), "application/pdf")
        FinalistSlides.objects.filter(group__group_name="BTF24").update(file={"storage_key": "gone.pdf", "name": "s.pdf"})

        _, archive = self._archive()

        names = [f"{self.year}_BTF3_Slides.pdf", f"{self.year}_BTF10_Slides.pptx"]
        names += [f"{self.year}_BTF{n}_Slides.pdf" for n in (20, 21, 22, 23)]
        names += [f"{self.year}_BTF24_Slides_MISSING.txt"]
        names += [f"{self.year}_BTF{n}_Slides.pdf" for n in (25, 26, 27, 28)]
        self.assertEqual(archive.namelist(), names)
        self.assertEqual(archive.read(f"{self.year}_BTF27_Slides.pdf"), b"%PDF 27")

    def test_each_zip_made_replaces_the_last(self):
        self._archive()
        FinalistSlides.objects.filter(group=self.btf10).delete()

        _, archive = self._archive()

        self.assertEqual(archive.namelist(), [f"{self.year}_BTF3_Slides.pdf"])

    def test_on_azure_the_download_comes_straight_from_storage(self):
        from unittest import mock

        signed = "https://store.blob.core.windows.net/slides/zips/z.zip?sig=x"
        azure = mock.Mock(is_remote=True)
        azure.exists.return_value = True
        azure.backend.url.return_value = signed
        with (
            mock.patch("apps.management.views.presentation.get_slides_storage", return_value=azure),
            mock.patch("apps.submissions.slides_download.get_slides_storage", return_value=azure),
        ):
            response = self._fetch()

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response["Location"], signed)
        key, = azure.backend.url.call_args.args
        self.assertEqual(key, f"zips/{self.year}_BTF_Finalist_Slides.zip")
        self.assertEqual(azure.backend.url.call_args.kwargs["parameters"], {
            "content_disposition": f'attachment; filename="{self.year}_BTF_Finalist_Slides.zip"',
            "content_type": "application/zip",
        })

    def test_nothing_to_download_until_slides_are_in(self):
        FinalistSlides.objects.all().delete()
        self.assertEqual(self._make().status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self._fetch().status_code, status.HTTP_404_NOT_FOUND)

    def test_graders_only(self):
        self._make()
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(self._make().status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self._fetch().status_code, status.HTTP_403_FORBIDDEN)
