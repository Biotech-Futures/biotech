"""Export downloads: the sync per-group zip, the async per-component job,
and the job polling endpoint."""
import io
import zipfile

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import GradingJob

from .fixtures import _GradingFixture


class GroupDownloadViewTests(_GradingFixture):
    """Sync per-group zip. Bounded selection, streamed straight to the client."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_zip_contains_submission_text_and_link(self):
        # Add a prototype link to the entry and resubmit so the snapshot has it.
        self.submission.prototype_url = "https://example.com/prototype"
        self.submission.snapshot(self.staff)
        self.submission.save()

        url = reverse("grading:group-download", kwargs={"group_id": self.group.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "application/zip")
        self.assertIn("attachment;", resp["Content-Disposition"])

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = set(zf.namelist())
        # Group folder + component subfolders with the right pseudo-files.
        self.assertIn("BTF-TEST-1/SAQ/text.txt", names)
        self.assertIn("BTF-TEST-1/PROTOTYPE/link.txt", names)
        # The fixture's poster storage key has no backing blob; the archive
        # notes it instead of failing.
        self.assertIn("BTF-TEST-1/POSTER/MISSING.txt", names)
        self.assertIn("Some student answers.", zf.read("BTF-TEST-1/SAQ/text.txt").decode())
        self.assertEqual(zf.read("BTF-TEST-1/PROTOTYPE/link.txt").decode().strip(), "https://example.com/prototype")

    def test_component_filter(self):
        url = reverse("grading:group-download", kwargs={"group_id": self.group.id}) + "?component=SAQ"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = zipfile.ZipFile(io.BytesIO(resp.content)).namelist()
        # Single-component downloads skip the redundant component folder layer.
        self.assertTrue(all(n.startswith("BTF-TEST-1/") for n in names), names)
        self.assertTrue(all("/SAQ/" not in n for n in names), names)

    def test_non_staff_denied(self):
        self.client.force_authenticate(self.non_staff)
        resp = self.client.get(reverse("grading:group-download", kwargs={"group_id": self.group.id}))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(GRADING_JOB_DISPATCH_SYNC=True)
class ComponentDownloadViewTests(_GradingFixture):
    """Async per-component export. DISPATCH_SYNC runs inline so the job row is
    already ``done`` (or ``failed``) by the time the 202 returns."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_zip_job_runs_inline_and_produces_url(self):
        url = reverse("grading:component-download", kwargs={"code": "SAQ"})
        resp = self.client.post(url, {"format": "zip"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.content)
        job_id = resp.json()["job_id"]
        job = GradingJob.objects.get(pk=job_id)
        self.assertEqual(job.status, GradingJob.STATUS_DONE, job.error)
        self.assertTrue(job.result_url)

    def test_xlsx_only_for_saq(self):
        url = reverse("grading:component-download", kwargs={"code": "POSTER"})
        resp = self.client.post(url, {"format": "xlsx"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bad_format_rejected(self):
        url = reverse("grading:component-download", kwargs={"code": "SAQ"})
        resp = self.client.post(url, {"format": "docx"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_staff_denied(self):
        self.client.force_authenticate(self.non_staff)
        url = reverse("grading:component-download", kwargs={"code": "SAQ"})
        resp = self.client.post(url, {"format": "zip"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(GRADING_JOB_DISPATCH_SYNC=True)
class GradingJobDetailViewTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_poll_shape(self):
        job = GradingJob.objects.create(
            kind=GradingJob.KIND_BULK_ZIP,
            status=GradingJob.STATUS_DONE,
            params={"kind": "component_zip", "component_code": "SAQ"},
            result_url="grading/jobs/1/SAQ-bundle.zip",  # opaque storage key now
            created_by=self.staff,
        )
        resp = self.client.get(reverse("grading:job-detail", kwargs={"pk": job.pk}))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["status"], "done")
        self.assertTrue(data["download_url"].endswith(f"/api/v1/grading/jobs/{job.pk}/download/"))

    def test_unknown_job_404(self):
        resp = self.client.get(reverse("grading:job-detail", kwargs={"pk": 999_999}))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
