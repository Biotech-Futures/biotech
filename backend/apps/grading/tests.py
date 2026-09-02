import io
import zipfile
from decimal import Decimal
from importlib import import_module

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APIClient

from apps.groups.models.group_members import GroupMembership
from apps.groups.models.groups import Groups
from apps.grading.models import (
    CertificatesRelease,
    ComponentFeedback,
    FinalistFlag,
    Grade,
    GradingJob,
    MarksRelease,
    Rubric,
    RubricCriterion,
    SubmissionComponent,
)
from apps.submissions.models import Submission, SubmissionQuestion
from apps.users.models import AdminScope, User


class GradingURLsMountedTests(TestCase):
    """Sanity: the grading URLs must always resolve."""

    def test_urls_resolve(self):
        self.assertEqual(reverse("grading:group-marking", kwargs={"group_id": 1}), "/api/v1/grading/groups/1/")
        self.assertEqual(reverse("grading:grade-bulk"), "/api/v1/grading/grades/bulk/")
        self.assertEqual(reverse("grading:grade-detail", kwargs={"pk": 1}), "/api/v1/grading/grades/1/")
        self.assertEqual(reverse("grading:component-list", kwargs={"code": "SAQ"}), "/api/v1/grading/components/SAQ/")
        self.assertEqual(reverse("grading:group-download", kwargs={"group_id": 1}), "/api/v1/grading/groups/1/download/")
        self.assertEqual(reverse("grading:component-download", kwargs={"code": "SAQ"}), "/api/v1/grading/components/SAQ/download/")
        self.assertEqual(reverse("grading:job-detail", kwargs={"pk": 1}), "/api/v1/grading/jobs/1/")
        self.assertEqual(reverse("grading:component-bulk-upload", kwargs={"code": "SAQ"}), "/api/v1/grading/components/SAQ/bulk-upload/")
        self.assertEqual(reverse("grading:release"), "/api/v1/grading/release/")
        self.assertEqual(reverse("grading:settings"), "/api/v1/grading/settings/")
        self.assertEqual(reverse("grading:me-grades"), "/api/v1/grading/me/grades/")
        self.assertEqual(reverse("grading:me-summary"), "/api/v1/grading/me/summary/")
        self.assertEqual(reverse("grading:me-certificate"), "/api/v1/grading/me/certificate/")
        self.assertEqual(reverse("grading:supervisor-grades"), "/api/v1/grading/supervisor/students/grades/")
        self.assertEqual(reverse("grading:supervisor-download"), "/api/v1/grading/supervisor/download/")
        self.assertEqual(reverse("grading:finalist-list"), "/api/v1/grading/finalists/")
        self.assertEqual(reverse("grading:finalist-toggle", kwargs={"group_id": 1}), "/api/v1/grading/groups/1/finalist/")
        self.assertEqual(reverse("grading:component-analytics", kwargs={"code": "SAQ"}), "/api/v1/grading/components/SAQ/analytics/")


class _GradingFixture(TestCase):
    """Shared setup: one group with a submitted entry (SAQ answers + a poster),
    four seeded components, SAQ + POSTER rubrics, one staff user.

    A team's entry is one Submission row; ``saq_submission`` and
    ``poster_submission`` are kept as aliases of it so the per-component tests
    read naturally — grades tell components apart via their criterion.
    """

    @classmethod
    def setUpTestData(cls):
        # settings_test disables migrations entirely, so the 0002_seed_components
        # data migration never runs there — seed the same rows ourselves, reusing
        # the migration's own COMPONENTS list so the two can't drift.
        seed_components = import_module(
            "apps.grading.migrations.0002_seed_components"
        ).COMPONENTS
        for row in seed_components:
            SubmissionComponent.objects.update_or_create(
                code=row["code"],
                defaults={k: v for k, v in row.items() if k != "code"},
            )

        cls.group = Groups.objects.create(group_name="BTF-TEST-1")
        cls.saq = SubmissionComponent.objects.get(code="SAQ")
        cls.poster = SubmissionComponent.objects.get(code="POSTER")

        cls.saq_rubric = Rubric.objects.create(component=cls.saq, year=2026, active=True)
        cls.poster_rubric = Rubric.objects.create(component=cls.poster, year=2026, active=True)

        cls.saq_c1 = RubricCriterion.objects.create(rubric=cls.saq_rubric, name="Content", max_mark=Decimal("10.00"), order=10)
        cls.saq_c2 = RubricCriterion.objects.create(rubric=cls.saq_rubric, name="Clarity", max_mark=Decimal("5.00"), order=20)
        cls.poster_c1 = RubricCriterion.objects.create(rubric=cls.poster_rubric, name="Design", max_mark=Decimal("10.00"), order=10)

        cls.staff = User.objects.create_user(
            email="grader@example.com", first_name="Ada", last_name="Grader",
            password="pw12345!", is_staff=True,
        )
        cls.non_staff = User.objects.create_user(
            email="student@example.com", first_name="Stu", last_name="Dent",
            password="pw12345!", is_staff=False,
        )

        # A question so the SAQ export carries a heading, not a raw key.
        SubmissionQuestion.objects.create(
            key="q_answers", prompt="Team answers", order=10,
        )
        cls.submission = Submission.objects.create(
            group=cls.group,
            answers={"q_answers": "Some student answers."},
            poster={"storage_key": "2026/01/01/fixture/poster.pdf",
                    "name": "poster.pdf", "mime": "application/pdf", "size": 42},
        )
        cls.submission.snapshot(cls.staff)
        cls.submission.save()
        # One row, two component views of it.
        cls.saq_submission = cls.submission
        cls.poster_submission = cls.submission


class GroupMarkingViewTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()

    def test_anonymous_denied(self):
        resp = self.client.get(reverse("grading:group-marking", kwargs={"group_id": self.group.id}))
        self.assertIn(resp.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    def test_non_staff_denied(self):
        self.client.force_authenticate(self.non_staff)
        resp = self.client.get(reverse("grading:group-marking", kwargs={"group_id": self.group.id}))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_admin_allowed(self):
        scoped = User.objects.create_user(
            email="scoped-admin@example.com", first_name="Sco", last_name="Ped",
            password="pw12345!", is_staff=False,
        )
        AdminScope.objects.create(user=scoped)
        self.client.force_authenticate(scoped)
        resp = self.client.get(reverse("grading:group-marking", kwargs={"group_id": self.group.id}))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_non_staff_superuser_allowed(self):
        superuser = User.objects.create_user(
            email="super@example.com", first_name="Sue", last_name="Per",
            password="pw12345!", is_staff=False, is_superuser=True,
        )
        self.client.force_authenticate(superuser)
        resp = self.client.get(reverse("grading:group-marking", kwargs={"group_id": self.group.id}))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_payload_shape(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.get(
            reverse("grading:group-marking", kwargs={"group_id": self.group.id}) + "?year=2026"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["group"]["id"], self.group.id)
        self.assertEqual(data["year"], 2026)
        # Four seeded components; every one appears even if no submission exists.
        codes = [c["component"]["code"] for c in data["components"]]
        self.assertEqual(sorted(codes), sorted(["SAQ", "POSTER", "REPORT", "PROTOTYPE"]))
        saq_block = next(c for c in data["components"] if c["component"]["code"] == "SAQ")
        self.assertIsNotNone(saq_block["submission"])
        # SAQ text is the answers flattened under their question prompts.
        self.assertIn("Team answers", saq_block["submission"]["text"])
        self.assertIn("Some student answers.", saq_block["submission"]["text"])
        self.assertEqual(len(saq_block["criteria"]), 2)
        self.assertEqual(saq_block["grades"], [])
        # REPORT has no submission and no rubric — should still render as an empty slot.
        report_block = next(c for c in data["components"] if c["component"]["code"] == "REPORT")
        self.assertIsNone(report_block["submission"])
        self.assertEqual(report_block["criteria"], [])


class GradeBulkViewTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_bulk_upserts_and_updates(self):
        url = reverse("grading:grade-bulk")
        payload = {"items": [
            {"submission": self.saq_submission.id, "criterion": self.saq_c1.id, "mark": "8.00", "comment": "Great."},
            {"submission": self.saq_submission.id, "criterion": self.saq_c2.id, "mark": "4.50", "comment": ""},
        ]}
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(Grade.objects.count(), 2)
        g = Grade.objects.get(submission=self.saq_submission, criterion=self.saq_c1)
        self.assertEqual(g.mark, Decimal("8.00"))
        self.assertEqual(g.graded_by_id, self.staff.id)

        # Second call updates the same rows in place — upsert, not insert.
        payload["items"][0]["mark"] = "9.00"
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(Grade.objects.count(), 2)
        g.refresh_from_db()
        self.assertEqual(g.mark, Decimal("9.00"))

    def test_overall_comment_saved_with_bulk(self):
        url = reverse("grading:grade-bulk")
        payload = {
            "items": [
                {"submission": self.saq_submission.id, "criterion": self.saq_c1.id, "mark": "8.00"},
            ],
            "overall_comments": [
                # The entry has SAQ + POSTER content, so the component code is
                # required to say which comment this is.
                {"submission": self.poster_submission.id, "component": "POSTER",
                 "comment": "Strong poster overall."},
            ],
        }
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        feedback = ComponentFeedback.objects.get(group=self.group, component=self.poster)
        self.assertEqual(feedback.comment, "Strong poster overall.")
        self.assertEqual(feedback.updated_by_id, self.staff.id)

        # Unknown submission id in overall_comments is a 400.
        bad = {"items": [], "overall_comments": [{"submission": 99999, "comment": "x"}]}
        self.assertEqual(self.client.post(url, bad, format="json").status_code, status.HTTP_400_BAD_REQUEST)

        # Omitting the component on a multi-component entry is also a 400.
        ambiguous = {"items": [], "overall_comments": [
            {"submission": self.submission.id, "comment": "which one?"},
        ]}
        self.assertEqual(
            self.client.post(url, ambiguous, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_component_mismatch_rejected_atomically(self):
        url = reverse("grading:grade-bulk")
        # A REPORT criterion exists but the entry has no submitted report, so
        # binding it to this submission is a client bug and must be rejected.
        report = SubmissionComponent.objects.get(code="REPORT")
        report_rubric = Rubric.objects.create(component=report, year=2026, active=True)
        report_c1 = RubricCriterion.objects.create(
            rubric=report_rubric, name="Rigour", max_mark=Decimal("10.00"), order=10,
        )
        payload = {"items": [
            {"submission": self.saq_submission.id, "criterion": self.saq_c1.id, "mark": "7.00"},
            {"submission": self.saq_submission.id, "criterion": report_c1.id, "mark": "9.00"},
        ]}
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Atomic — the first item's Grade must NOT have been written.
        self.assertEqual(Grade.objects.count(), 0)


class ComponentMarkingListViewTests(_GradingFixture):
    """Table view for a single component — every group, submitted or not."""

    def setUp(self):
        self.client = APIClient()
        # A second group without any submission to prove empty rows appear.
        self.other_group = Groups.objects.create(group_name="BTF-TEST-2")

    def test_non_staff_denied(self):
        self.client.force_authenticate(self.non_staff)
        resp = self.client.get(reverse("grading:component-list", kwargs={"code": "SAQ"}))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_component_returns_404(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.get(reverse("grading:component-list", kwargs={"code": "DOES_NOT_EXIST"}))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_table_shape_and_progress(self):
        # Mark one criterion on the first group's SAQ submission.
        Grade.objects.create(
            submission=self.saq_submission, criterion=self.saq_c1,
            mark=Decimal("7.00"), comment="",
        )
        # Also add a "null-mark" grade — must NOT be counted as graded.
        Grade.objects.create(
            submission=self.saq_submission, criterion=self.saq_c2,
            mark=None, comment="pending",
        )

        self.client.force_authenticate(self.staff)
        resp = self.client.get(
            reverse("grading:component-list", kwargs={"code": "SAQ"}) + "?year=2026"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        data = resp.json()

        self.assertEqual(data["component"]["code"], "SAQ")
        self.assertEqual(data["year"], 2026)
        self.assertEqual(data["criteria_total"], 2)  # saq_c1 + saq_c2

        rows_by_group = {r["group_name"]: r for r in data["rows"]}
        # Both groups appear even though only one has submitted.
        self.assertIn("BTF-TEST-1", rows_by_group)
        self.assertIn("BTF-TEST-2", rows_by_group)

        r1 = rows_by_group["BTF-TEST-1"]
        self.assertIsNotNone(r1["submission_id"])
        self.assertEqual(r1["criteria_graded"], 1)  # null-mark grade excluded

        r2 = rows_by_group["BTF-TEST-2"]
        self.assertIsNone(r2["submission_id"])
        self.assertEqual(r2["criteria_graded"], 0)


class GradeUpdateViewTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.grade = Grade.objects.create(
            submission=self.saq_submission,
            criterion=self.saq_c1,
            mark=Decimal("5.00"),
            comment="initial",
        )

    def test_patch_updates_mark_and_stamps_grader(self):
        self.client.force_authenticate(self.staff)
        url = reverse("grading:grade-detail", kwargs={"pk": self.grade.pk})
        resp = self.client.patch(url, {"mark": "6.50", "comment": "revised"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.grade.refresh_from_db()
        self.assertEqual(self.grade.mark, Decimal("6.50"))
        self.assertEqual(self.grade.comment, "revised")
        self.assertEqual(self.grade.graded_by_id, self.staff.id)

    def test_patch_denied_for_non_staff(self):
        self.client.force_authenticate(self.non_staff)
        url = reverse("grading:grade-detail", kwargs={"pk": self.grade.pk})
        resp = self.client.patch(url, {"mark": "6.50"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


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
        self.assertTrue(all(n.startswith("BTF-TEST-1/SAQ/") for n in names), names)

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


class BulkUploadMarksViewTests(_GradingFixture):
    """XLSX/CSV round-trip: parse → dry-run diff → commit."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.url = reverse("grading:component-bulk-upload", kwargs={"code": "SAQ"})

    def _make_csv(self, rows):
        header = "group_id,criterion_id,mark,comment\n"
        body = "\n".join(",".join(str(x) for x in r) for r in rows)
        return SimpleUploadedFile(
            "marks.csv", (header + body + "\n").encode("utf-8"), content_type="text/csv",
        )

    def _make_xlsx(self, rows):
        wb = Workbook()
        ws = wb.active
        ws.append(["group_id", "criterion_id", "mark", "comment"])
        for r in rows:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        return SimpleUploadedFile(
            "marks.xlsx", buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_missing_file_400(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_staff_denied(self):
        self.client.force_authenticate(self.non_staff)
        resp = self.client.post(self.url, {"file": self._make_csv([(self.group.id, self.saq_c1.id, 8, "ok")])})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_dry_run_csv_returns_diff_no_writes(self):
        resp = self.client.post(
            self.url,
            {"file": self._make_csv([
                (self.group.id, self.saq_c1.id, "8.00", "Great"),
            ]), "dry_run": "true"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        data = resp.json()
        self.assertEqual(data["summary"], {"creates": 1, "updates": 0, "unchanged": 0, "errors": 0})
        self.assertEqual(Grade.objects.count(), 0)

    def test_dry_run_xlsx_categorises_create_update_unchanged(self):
        # Seed one existing grade to force an "update" and one that matches to force "unchanged".
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c1, mark=Decimal("5"), comment="old")
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c2, mark=Decimal("4.50"), comment="same")

        upload = self._make_xlsx([
            (self.group.id, self.saq_c1.id, "7.00", "revised"),  # update (mark + comment changed)
            (self.group.id, self.saq_c2.id, "4.50", "same"),      # unchanged
        ])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        s = resp.json()["summary"]
        self.assertEqual(s, {"creates": 0, "updates": 1, "unchanged": 1, "errors": 0})

    def test_row_errors_reported(self):
        upload = self._make_csv([
            (self.group.id, self.saq_c1.id, "abc", ""),                  # non-numeric mark
            (self.group.id, self.saq_c1.id, "99", ""),                   # over max_mark
            (self.group.id, self.poster_c1.id, "5", ""),                 # wrong-component criterion
            (999_999, self.saq_c1.id, "5", ""),                          # group with no SAQ submission
            (self.group.id, self.saq_c1.id, "5", ""),                    # duplicate pair (second occurrence)
        ])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        errors = resp.json()["errors"]
        self.assertGreaterEqual(len(errors), 4)
        # Sanity: each error carries a 1-indexed row number matching the input.
        for e in errors:
            self.assertIn("row", e)
            self.assertIn("message", e)

    def test_commit_rejected_when_errors_exist(self):
        upload = self._make_csv([(self.group.id, self.saq_c1.id, "abc", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Grade.objects.count(), 0)

    def test_commit_persists_and_stamps_grader(self):
        upload = self._make_csv([
            (self.group.id, self.saq_c1.id, "9.00", "excellent"),
            (self.group.id, self.saq_c2.id, "3.50", "adequate"),
        ])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        payload = resp.json()
        self.assertTrue(payload["applied"])
        self.assertEqual(payload["written"], 2)
        self.assertEqual(Grade.objects.count(), 2)
        g = Grade.objects.get(submission=self.saq_submission, criterion=self.saq_c1)
        self.assertEqual(g.mark, Decimal("9.00"))
        self.assertEqual(g.graded_by_id, self.staff.id)


class SubmissionDeadlineViewTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("grading:deadline")

    def test_non_staff_denied(self):
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_get_null_when_unset(self):
        self.client.force_authenticate(self.staff)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.json()["deadline"])

    def test_post_creates_active_deadline(self):
        self.client.force_authenticate(self.staff)
        r = self.client.post(
            self.url,
            {"closes_at": "2026-10-30T13:00:00Z", "grace_hours": 6},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        deadline = r.json()["deadline"]
        self.assertTrue(deadline["is_open"])
        self.assertEqual(deadline["grace_hours"], 6)

        # Newest active row wins: setting again replaces what's in force.
        r2 = self.client.post(
            self.url, {"closes_at": "2020-01-01T00:00:00Z"}, format="json"
        )
        self.assertFalse(r2.json()["deadline"]["is_open"])

    def test_bad_payload_rejected(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(
            self.client.post(self.url, {"closes_at": "not-a-date"}, format="json").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(
                self.url, {"closes_at": "2026-10-30T13:00:00Z", "grace_hours": -1},
                format="json",
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class MarksReleaseViewTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()

    def test_non_staff_denied(self):
        self.client.force_authenticate(self.non_staff)
        resp = self.client.get(reverse("grading:release"))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_flip_on_then_off(self):
        self.client.force_authenticate(self.staff)
        r = self.client.post(reverse("grading:release"), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r.json()["released_at"])

        r = self.client.post(reverse("grading:release"), {"release": "false"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.json()["released_at"])


class GradingSettingsViewTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_get_and_patch_director_names(self):
        r = self.client.patch(
            reverse("grading:settings"),
            {"director_1_name": "Alice A", "director_2_name": "Bob B"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["director_1_name"], "Alice A")

        r2 = self.client.get(reverse("grading:settings"))
        self.assertEqual(r2.json()["director_2_name"], "Bob B")


class StudentReadViewsTests(_GradingFixture):
    """Release gate: pre-release → 403; post-release → own group only."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.student_user = User.objects.create_user(
            email="stud@example.com", first_name="Sam", last_name="Student",
            password="pw12345!", is_staff=False,
        )
        # Join the fixture group as a student.
        GroupMembership.objects.create(
            group=cls.group, user=cls.student_user,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        # Seed one released grade so the docx render has real numbers.
        Grade.objects.create(
            submission=cls.saq_submission, criterion=cls.saq_c1,
            mark=Decimal("8.00"), comment="Great",
        )

    def setUp(self):
        self.client = APIClient()
        MarksRelease.load()  # ensure row exists; released_at stays None by default

    def _release_now(self):
        rel = MarksRelease.load()
        rel.released_at = timezone.now()
        rel.released_by = self.staff
        rel.save()

    def _release_certificates_now(self):
        rel = CertificatesRelease.load()
        rel.released_at = timezone.now()
        rel.released_by = self.staff
        rel.save()

    def test_pre_release_denied(self):
        self.client.force_authenticate(self.student_user)
        r = self.client.get(reverse("grading:me-grades"))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_release_returns_own_grades(self):
        self._release_now()
        self.client.force_authenticate(self.student_user)
        r = self.client.get(reverse("grading:me-grades"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        data = r.json()
        self.assertEqual(data["group"]["id"], self.group.id)
        saq = next(c for c in data["components"] if c["code"] == "SAQ")
        self.assertEqual(saq["criteria"][0]["mark"], "8.00")

    def test_summary_docx_streams(self):
        self._release_now()
        self.client.force_authenticate(self.student_user)
        r = self.client.get(reverse("grading:me-summary"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("wordprocessingml", r["Content-Type"])
        # docx = zip file; magic bytes PK\x03\x04
        self.assertTrue(r.content[:4] == b"PK\x03\x04")

    def test_certificate_docx_streams(self):
        # Certificates have their own gate — marks being released is neither
        # necessary nor sufficient.
        self._release_now()
        self.client.force_authenticate(self.student_user)
        self.assertEqual(
            self.client.get(reverse("grading:me-certificate")).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self._release_certificates_now()
        r = self.client.get(reverse("grading:me-certificate"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.content[:4] == b"PK\x03\x04")

    @override_settings(GRADING_JOB_DISPATCH_SYNC=True)
    def test_supervisor_bundle_adapts_to_release_gates(self):
        from django.core.files.storage import default_storage

        from apps.users.models import StudentProfile, SupervisorProfile

        supervisor = User.objects.create_user(
            email="super@example.com", first_name="Sue", last_name="Pervisor",
            password="pw12345!",
        )
        profile = SupervisorProfile.objects.create(user=supervisor, school_name="Test School")
        StudentProfile.objects.create(
            user=self.student_user, pg_first_name="P", pg_last_name="G",
            supervisor=profile, school_name="Test School", year_lvl="11",
        )

        def bundle_names():
            resp = self.client.post(reverse("grading:supervisor-download"), {}, format="json")
            self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED, resp.content)
            job = GradingJob.objects.get(pk=resp.json()["job_id"])
            self.assertEqual(job.status, GradingJob.STATUS_DONE, job.error)
            with default_storage.open(job.result_url, "rb") as fh:
                return set(zipfile.ZipFile(io.BytesIO(fh.read())).namelist())

        self.client.force_authenticate(supervisor)

        # Neither gate open -> the endpoint itself refuses.
        self.assertEqual(
            self.client.post(reverse("grading:supervisor-download"), {}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        # Marks only -> summaries, no certificates.
        self._release_now()
        names = bundle_names()
        self.assertTrue(any(n.endswith("marks-summary.docx") for n in names), names)
        self.assertFalse(any(n.endswith("certificate.docx") for n in names), names)

        # Certificates too -> both documents.
        self._release_certificates_now()
        names = bundle_names()
        self.assertTrue(any(n.endswith("marks-summary.docx") for n in names), names)
        self.assertTrue(any(n.endswith("certificate.docx") for n in names), names)

    def test_certificates_release_toggle(self):
        self.client.force_authenticate(self.staff)
        url = reverse("grading:certificates-release")
        r = self.client.get(url)
        self.assertIsNone(r.json()["released_at"])

        r = self.client.post(url, {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r.json()["released_at"])
        # Marks gate untouched by the certificates toggle.
        self.assertIsNone(MarksRelease.load().released_at)

        r = self.client.post(url, {"release": "false"}, format="json")
        self.assertIsNone(r.json()["released_at"])


class FinalistToggleTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("grading:finalist-toggle", kwargs={"group_id": self.group.id})

    def test_non_staff_denied(self):
        self.client.force_authenticate(self.non_staff)
        r = self.client.post(self.url, {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_upsert_idempotent(self):
        self.client.force_authenticate(self.staff)
        r1 = self.client.post(self.url, {}, format="json")
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED, r1.content)
        r2 = self.client.post(self.url, {}, format="json")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(FinalistFlag.objects.filter(group=self.group).count(), 1)

    def test_delete_idempotent(self):
        self.client.force_authenticate(self.staff)
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        r1 = self.client.delete(self.url)
        self.assertEqual(r1.status_code, status.HTTP_204_NO_CONTENT)
        r2 = self.client.delete(self.url)  # already gone
        self.assertEqual(r2.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(FinalistFlag.objects.filter(group=self.group).exists())

    @override_settings(GRADING_FINALIST_EMAIL_ENABLED=True)
    def test_notify_all_emails_unnotified_flags_only(self):
        from django.core import mail

        member = User.objects.create_user(
            email="member@example.com", first_name="Mem", last_name="Ber", password="pw12345!",
        )
        GroupMembership.objects.create(
            group=self.group, user=member, membership_role="student",
        )
        already = Groups.objects.create(group_name="BTF-TEST-2")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        FinalistFlag.objects.create(group=already, flagged_by=self.staff, notified=True)

        self.client.force_authenticate(self.staff)
        url = reverse("grading:finalist-notify")
        r = self.client.post(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["sent"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("member@example.com", mail.outbox[0].to)
        notified_flag = FinalistFlag.objects.get(group=self.group)
        self.assertTrue(notified_flag.notified)
        self.assertIsNotNone(notified_flag.notified_at)

        # Second press: everything already notified (or has no recipients) — no new mail.
        r2 = self.client.post(url)
        self.assertEqual(r2.json()["sent"], 0)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(GRADING_FINALIST_EMAIL_ENABLED=True)
    def test_notify_with_group_ids_targets_only_those(self):
        from django.core import mail

        member = User.objects.create_user(
            email="member@example.com", first_name="Mem", last_name="Ber", password="pw12345!",
        )
        GroupMembership.objects.create(group=self.group, user=member, membership_role="student")
        other_group = Groups.objects.create(group_name="BTF-TEST-3")
        other_member = User.objects.create_user(
            email="other@example.com", first_name="Oth", last_name="Er", password="pw12345!",
        )
        GroupMembership.objects.create(group=other_group, user=other_member, membership_role="student")
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        FinalistFlag.objects.create(group=other_group, flagged_by=self.staff)

        self.client.force_authenticate(self.staff)
        url = reverse("grading:finalist-notify")
        r = self.client.post(url, {"group_ids": [self.group.id]}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json()["sent"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("member@example.com", mail.outbox[0].to)
        self.assertFalse(FinalistFlag.objects.get(group=other_group).notified)

        # Malformed group_ids is a 400, not a mass send.
        r_bad = self.client.post(url, {"group_ids": "1,2"}, format="json")
        self.assertEqual(r_bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_candidates_totals_markers_and_finalist_state(self):
        Grade.objects.create(
            submission=self.saq_submission, criterion=self.saq_c1,
            mark=Decimal("8.00"), graded_by=self.staff,
        )
        Grade.objects.create(
            submission=self.saq_submission, criterion=self.saq_c2,
            mark=Decimal("4.50"), graded_by=self.staff,
        )
        Grade.objects.create(
            submission=self.poster_submission, criterion=self.poster_c1,
            mark=Decimal("7.00"), graded_by=self.staff,
        )
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        ungraded = Groups.objects.create(group_name="BTF-UNGRADED")

        self.client.force_authenticate(self.staff)
        r = self.client.get(reverse("grading:finalist-candidates"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        body = r.json()
        self.assertEqual([c["code"] for c in body["components"]][:2], ["SAQ", "POSTER"])

        # Only components whose active rubric has criteria appear as columns;
        # REPORT/PROTOTYPE carry no criteria so they are omitted entirely.
        self.assertEqual([c["code"] for c in body["components"]], ["SAQ", "POSTER"])

        rows = {row["group_id"]: row for row in body["rows"]}
        graded = rows[self.group.id]
        self.assertEqual(graded["marks"]["SAQ"], "12.50")
        self.assertEqual(graded["marks"]["POSTER"], "7.00")
        self.assertNotIn("REPORT", graded["marks"])
        self.assertEqual(graded["total"], "19.50")
        # Fixture submits before any deadline exists -> not late, no label.
        self.assertFalse(graded["is_late"])
        self.assertIsNone(graded["late_by"])
        self.assertEqual(graded["markers"], ["Ada Grader"])
        self.assertTrue(graded["is_finalist"])
        # Graded group ranks above the ungraded one.
        self.assertEqual(body["rows"][0]["group_id"], self.group.id)
        self.assertIsNone(rows[ungraded.id]["total"])
        self.assertFalse(rows[ungraded.id]["is_finalist"])
        self.assertTrue(graded["has_submission"])
        self.assertFalse(rows[ungraded.id]["has_submission"])

    def test_candidates_late_column(self):
        from datetime import timedelta

        from apps.submissions.models import Deadline

        # Deadline 3h12m before the fixture's submit time -> "3h 12m" late.
        Deadline.objects.create(
            closes_at=self.submission.submitted_at - timedelta(hours=3, minutes=12),
            is_active=True,
        )
        Submission.objects.filter(pk=self.submission.pk).update(is_late=True)

        self.client.force_authenticate(self.staff)
        r = self.client.get(reverse("grading:finalist-candidates"))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        row = next(x for x in r.json()["rows"] if x["group_id"] == self.group.id)
        self.assertTrue(row["is_late"])
        self.assertEqual(row["late_by"], "3h 12m")

    def test_notify_all_denied_for_non_staff(self):
        self.client.force_authenticate(self.non_staff)
        r = self.client.post(reverse("grading:finalist-notify"))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_returns_flagged_groups(self):
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        self.client.force_authenticate(self.staff)
        r = self.client.get(reverse("grading:finalist-list"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        rows = r.json()["finalists"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["group_id"], self.group.id)

    @override_settings(GRADING_FINALIST_EMAIL_ENABLED=True)
    def test_notify_flag_marks_notified_when_recipients_exist(self):
        from django.core import mail
        # Fixture staff user is is_staff=True; add as a member so they get the mail.
        GroupMembership.objects.create(
            group=self.group, user=self.staff,
            membership_role=GroupMembership.MembershipRoleChoices.STUDENT,
        )
        self.client.force_authenticate(self.staff)
        r = self.client.post(self.url, {"notify": True}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self.assertTrue(r.json()["notified"])
        self.assertGreaterEqual(len(mail.outbox), 1)

    def test_notify_off_by_default(self):
        # Env flag OFF → notify=true is honoured as a request but the helper is a no-op.
        self.client.force_authenticate(self.staff)
        r = self.client.post(self.url, {"notify": True}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertFalse(r.json()["notified"])


class ComponentAnalyticsTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("grading:component-analytics", kwargs={"code": "SAQ"})

    def test_non_staff_denied(self):
        self.client.force_authenticate(self.non_staff)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_component_returns_404(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(
            self.client.get(reverse("grading:component-analytics", kwargs={"code": "MISSING"})).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_aggregates_match_hand_computation(self):
        # Second group without a submission — should count as pending / unmarked.
        Groups.objects.create(group_name="BTF-TEST-2")

        # Fully mark fixture group's SAQ submission across both criteria.
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c1, mark=Decimal("8.00"))
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c2, mark=Decimal("4.00"))

        self.client.force_authenticate(self.staff)
        r = self.client.get(self.url + "?year=2026")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        data = r.json()

        self.assertEqual(data["component"]["code"], "SAQ")
        self.assertEqual(data["year"], 2026)
        self.assertEqual(data["criteria_total"], 2)
        self.assertEqual(data["groups_total"], 2)
        self.assertEqual(data["submissions"], {"submitted": 1, "pending": 1})
        self.assertEqual(data["grading"], {"fully_marked": 1, "partially_marked": 0, "unmarked": 0})
        self.assertEqual(data["marks"]["count"], 1)
        self.assertEqual(data["marks"]["mean"], 12.0)
        self.assertEqual(data["marks"]["min"], 12.0)
        self.assertEqual(data["marks"]["max"], 12.0)

        rankings = data["rankings"]
        self.assertEqual(len(rankings), 1)
        self.assertEqual(rankings[0]["group_name"], "BTF-TEST-1")
        self.assertEqual(rankings[0]["total"], 12.0)

    def test_no_grades_yields_null_stats(self):
        self.client.force_authenticate(self.staff)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        marks = r.json()["marks"]
        self.assertEqual(marks["count"], 0)
        self.assertIsNone(marks["mean"])
        self.assertEqual(marks["histogram"], [])


class ClientDocxTemplateTests(_GradingFixture):
    """The client's real 2025 templates (bundled fallbacks) render correctly.

    The marks release template uses <<[Field]>> tokens; the merit certificate
    uses Word content controls with aliases. Both must come back with tokens
    replaced and our data in place.
    """

    @staticmethod
    def _document_xml(data: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return z.read("word/document.xml").decode("utf8")

    def test_marks_release_tokens_filled(self):
        from apps.grading.services.docx import marks_summary_context, render_marks_summary
        from apps.grading.views.student import _grades_payload

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
        self.assertNotIn("&lt;&lt;[", xml)
        self.assertNotIn("<<[", xml)
        self.assertIn("BTF-TEST-1", xml)      # TeamCode
        self.assertIn("4.00", xml)            # S1 mark
        self.assertIn("Nice claim.", xml)     # S1 comment
        self.assertIn("7.50", xml)            # CombinedTotal = 4.00 + 3.50
        self.assertIn("Strong poster overall.", xml)  # PosterComment

    def test_certificate_content_controls_filled(self):
        from apps.grading.services.docx import (
            certificate_context,
            render_participation_certificate,
        )

        data = render_participation_certificate(
            certificate_context(
                "Ada Grader", "BTF-TEST-1", 2026, first_name="Ada", last_name="Grader",
            )
        )
        xml = self._document_xml(data)
        self.assertIn("Ada", xml)
        self.assertIn("Grader", xml)
        self.assertIn("BTF-TEST-1", xml)      # projectTitle falls back to group name
