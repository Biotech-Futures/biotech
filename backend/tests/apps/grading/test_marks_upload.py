"""Bulk marks upload: the XLSX/CSV round-trip — parse → dry-run diff → commit."""
import io
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import ComponentFeedback, Grade

from .fixtures import _GradingFixture


class BulkUploadMarksViewTests(_GradingFixture):
    """XLSX/CSV round-trip: parse → dry-run diff → commit."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.url = reverse("grading:component-bulk-upload", kwargs={"code": "SAQ"})

    # Wide export shape: one row per group, criteria by rubric position.
    WIDE_HEADER = ["group_id", "group_name", "type", "r1_mark", "r1_comment", "r2_mark", "r2_comment", "overall_comment"]

    def _make_csv(self, rows, header=None):
        header_line = ",".join(header or self.WIDE_HEADER) + "\n"
        body = "\n".join(",".join(str(x) for x in r) for r in rows)
        return SimpleUploadedFile(
            "marks.csv", (header_line + body + "\n").encode("utf-8"), content_type="text/csv",
        )

    def _make_xlsx(self, rows, header=None):
        wb = Workbook()
        ws = wb.active
        ws.append(header or self.WIDE_HEADER)
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
        resp = self.client.post(self.url, {"file": self._make_csv([(self.group.id, "BTF-TEST-1","SAQs", 8, "ok", "", "", "")])})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_dry_run_csv_returns_diff_no_writes(self):
        resp = self.client.post(
            self.url,
            {"file": self._make_csv([
                (self.group.id, "BTF-TEST-1","SAQs", "8.00", "Great", "", "", ""),
            ]), "dry_run": "true"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        data = resp.json()
        # r2 is blank with no existing grade -> untouched, not a create.
        self.assertEqual(
            data["summary"],
            {"creates": 1, "updates": 0, "unchanged": 0, "overall_comments": 0, "errors": 0},
        )
        self.assertEqual(Grade.objects.count(), 0)

    def test_dry_run_xlsx_categorises_create_update_unchanged(self):
        # Seed one existing grade to force an "update" and one that matches to force "unchanged".
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c1, mark=Decimal("5"), comment="old")
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c2, mark=Decimal("4.50"), comment="same")

        upload = self._make_xlsx([
            (self.group.id, "BTF-TEST-1","SAQs", "7.00", "revised", "4.50", "same", ""),
        ])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        s = resp.json()["summary"]
        self.assertEqual(
            s, {"creates": 0, "updates": 1, "unchanged": 1, "overall_comments": 0, "errors": 0}
        )
        # Updates name their group and the columns whose values differ,
        # so the preview can say what an overwrite touches.
        upd = resp.json()["updates"][0]
        self.assertEqual(upd["group_name"], "BTF-TEST-1")
        self.assertEqual(upd["columns"], ["r1_mark", "r1_comment"])

    def test_row_errors_reported(self):
        upload = self._make_csv([
            (self.group.id, "BTF-TEST-1","SAQs", "abc", "", "", "", ""),   # non-numeric mark
            (999_999, "x", "SAQs", "5", "", "", "", ""),           # group with no SAQ submission
            (self.group.id, "BTF-TEST-1","SAQs", "99", "", "", "", ""),    # duplicate group row (also over max)
        ])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        errors = resp.json()["errors"]
        self.assertGreaterEqual(len(errors), 3)
        # Sanity: each error carries a 1-indexed row number matching the input.
        for e in errors:
            self.assertIn("row", e)
            self.assertIn("message", e)

    def test_over_max_mark_rejected(self):
        upload = self._make_csv([(self.group.id, "BTF-TEST-1","SAQs", "99", "", "", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["summary"]["errors"], 1)

    def test_bare_code_type_rejected(self):
        # Only the export's label ("SAQs") passes — a bare "SAQ" is wrong.
        upload = self._make_csv([(self.group.id, "BTF-TEST-1", "SAQ", "5", "", "", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertFalse(body["checks"]["type_ok"])
        self.assertEqual(body["checks"]["found_type"], "SAQ")

    def test_wrong_type_rejected(self):
        upload = self._make_csv([(self.group.id, "BTF-TEST-1","POSTER", "5", "", "", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        errors = resp.json()["errors"]
        self.assertEqual(len(errors), 1)
        self.assertIn("type", errors[0]["message"])

    def test_missing_type_column_rejected(self):
        header = ["group_id", "r1_mark"]
        upload = self._make_csv([(self.group.id, "5")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        errors = resp.json()["errors"]
        self.assertEqual(len(errors), 1)
        self.assertIn("type", errors[0]["message"])

    def test_wrong_group_name_rejected(self):
        # A row whose id points at a different group than its name says.
        upload = self._make_csv([(self.group.id, "SOME-OTHER-GROUP", "SAQs", "5", "", "", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body["checks"]["bad_group_rows"][0]["row"], 2)
        self.assertIn("name should be", body["checks"]["bad_group_rows"][0]["reason"])
        self.assertIn("group_name", body["errors"][0]["message"])

    def test_typoed_header_rejected(self):
        # "r1_commen" must fail loudly, reported by the expected name it
        # displaced — never silently dropped.
        header = ["group_id", "type", "r1_commen"]
        upload = self._make_csv([(self.group.id, "SAQs", "fine")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(len(body["errors"]), 1)
        self.assertIn("r1_comment", body["errors"][0]["message"])
        self.assertEqual(body["checks"]["missing_headers"], ["r1_comment"])

    def test_unknown_criterion_position_rejected(self):
        header = ["group_id", "type", "r9_mark"]
        upload = self._make_csv([(self.group.id, "SAQs", "5")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        errors = resp.json()["errors"]
        self.assertEqual(len(errors), 1)
        self.assertIn("r9", errors[0]["message"])

    def test_commit_rejected_when_errors_exist(self):
        upload = self._make_csv([(self.group.id, "BTF-TEST-1","SAQs", "abc", "", "", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Grade.objects.count(), 0)

    def test_commit_persists_and_stamps_grader(self):
        upload = self._make_csv([
            (self.group.id, "BTF-TEST-1","SAQs", "9.00", "excellent", "3.50", "adequate", "Solid entry overall."),
        ])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        payload = resp.json()
        self.assertTrue(payload["applied"])
        # Two grades plus the overall comment.
        self.assertEqual(payload["written"], 3)
        self.assertEqual(Grade.objects.count(), 2)
        g = Grade.objects.get(submission=self.saq_submission, criterion=self.saq_c1)
        self.assertEqual(g.mark, Decimal("9.00"))
        self.assertEqual(g.graded_by_id, self.staff.id)
        feedback = ComponentFeedback.objects.get(group=self.group, component=self.saq)
        self.assertEqual(feedback.comment, "Solid entry overall.")
        self.assertEqual(feedback.updated_by_id, self.staff.id)

    def test_absent_criterion_columns_leave_grades_alone(self):
        # A sheet carrying only r1 columns must not clear existing r2 grades.
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c2, mark=Decimal("4.00"), comment="keep")
        header = ["group_id", "type", "r1_mark", "r1_comment"]
        upload = self._make_csv([(self.group.id, "SAQs", "9.00", "fine")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        g2 = Grade.objects.get(submission=self.saq_submission, criterion=self.saq_c2)
        self.assertEqual(g2.mark, Decimal("4.00"))
        self.assertEqual(g2.comment, "keep")

    def test_absent_overall_comment_column_leaves_feedback_alone(self):
        ComponentFeedback.objects.create(group=self.group, component=self.saq, comment="keep me")
        header = ["group_id", "type", "r1_mark", "r1_comment"]
        upload = self._make_csv([(self.group.id, "SAQs", "9.00", "fine")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(
            ComponentFeedback.objects.get(group=self.group, component=self.saq).comment,
            "keep me",
        )
