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

    # Export shape: one row per criterion position.
    HEADER = ["group_id", "group_name", "answer", "criteria_no", "mark", "comment", "overall_comment"]

    def _make_csv(self, rows, header=None):
        header_line = ",".join(header or self.HEADER) + "\n"
        body = "\n".join(",".join(str(x) for x in r) for r in rows)
        return SimpleUploadedFile(
            "marks.csv", (header_line + body + "\n").encode("utf-8"), content_type="text/csv",
        )

    def _make_xlsx(self, rows, header=None):
        wb = Workbook()
        ws = wb.active
        ws.append(header or self.HEADER)
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
        resp = self.client.post(self.url, {"file": self._make_csv([(self.group.id, "BTF-TEST-1", "", 1, 8, "ok", "")])})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_dry_run_csv_returns_diff_no_writes(self):
        resp = self.client.post(
            self.url,
            {"file": self._make_csv([
                (self.group.id, "BTF-TEST-1", "", 1, "8.00", "Great", ""),
                (self.group.id, "BTF-TEST-1", "", 2, "", "", ""),
            ]), "dry_run": "true"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        data = resp.json()
        # Criterion 2 is blank with no existing grade -> untouched, not a create.
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
            (self.group.id, "BTF-TEST-1", "", 1, "7.00", "revised", ""),
            (self.group.id, "BTF-TEST-1", "", 2, "4.50", "same", ""),
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
        self.assertEqual(upd["criteria_no"], 1)
        self.assertEqual(upd["columns"], ["mark", "comment"])

    def test_row_errors_reported(self):
        upload = self._make_csv([
            (self.group.id, "BTF-TEST-1", "", 1, "abc", "", ""),   # non-numeric mark
            (999_999, "x", "", 1, "5", "", ""),                    # group with no SAQ submission
            (self.group.id, "BTF-TEST-1", "", 1, "99", "", ""),    # duplicate criterion row (also over max)
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
        upload = self._make_csv([(self.group.id, "BTF-TEST-1", "", 1, "99", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["summary"]["errors"], 1)

    def test_missing_criteria_no_column_rejected(self):
        header = ["group_id", "mark"]
        upload = self._make_csv([(self.group.id, "5")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        errors = resp.json()["errors"]
        self.assertEqual(len(errors), 1)
        self.assertIn("criteria_no", errors[0]["message"])

    def test_wrong_group_name_rejected(self):
        # A row whose id points at a different group than its name says.
        upload = self._make_csv([(self.group.id, "SOME-OTHER-GROUP", "", 1, "5", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body["checks"]["bad_group_rows"][0]["row"], 2)
        self.assertIn("name should be", body["checks"]["bad_group_rows"][0]["reason"])
        self.assertIn("group_name", body["errors"][0]["message"])

    def test_typoed_header_rejected(self):
        # "commen" must fail loudly, reported by the expected name it
        # displaced — never silently dropped.
        header = ["group_id", "criteria_no", "commen"]
        upload = self._make_csv([(self.group.id, 1, "fine")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(len(body["errors"]), 1)
        self.assertIn("comment", body["errors"][0]["message"])
        self.assertEqual(body["checks"]["missing_headers"], ["comment"])

    def test_criteria_beyond_rubric_with_mark_rejected(self):
        upload = self._make_csv([(self.group.id, "BTF-TEST-1", "", 9, "5", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        errors = resp.json()["errors"]
        self.assertEqual(len(errors), 1)
        self.assertIn("9", errors[0]["message"])

    def test_criteria_beyond_rubric_blank_is_ignored(self):
        # A hand-typed criteria_no beyond the rubric is fine while its
        # mark/comment stay blank.
        upload = self._make_csv([(self.group.id, "BTF-TEST-1", "an extra answer", 9, "", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(
            resp.json()["summary"],
            {"creates": 0, "updates": 0, "unchanged": 0, "overall_comments": 0, "errors": 0},
        )

    def test_blank_criteria_no_answer_row_is_ignored(self):
        # The export writes answer-only rows with a blank criteria_no when
        # there are more questions than criteria; they must upload back
        # without a diff.
        upload = self._make_csv([(self.group.id, "BTF-TEST-1", "an extra answer", "", "", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(
            resp.json()["summary"],
            {"creates": 0, "updates": 0, "unchanged": 0, "overall_comments": 0, "errors": 0},
        )

    def test_blank_criteria_no_with_mark_rejected(self):
        # A mark typed onto an answer-only row has no criterion to land on.
        upload = self._make_csv([(self.group.id, "BTF-TEST-1", "an extra answer", "", "5", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        errors = resp.json()["errors"]
        self.assertEqual(len(errors), 1)
        self.assertIn("criteria_no", errors[0]["message"])

    def test_commit_rejected_when_errors_exist(self):
        upload = self._make_csv([(self.group.id, "BTF-TEST-1", "", 1, "abc", "", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Grade.objects.count(), 0)

    def test_commit_persists_and_stamps_grader(self):
        upload = self._make_csv([
            (self.group.id, "BTF-TEST-1", "", 1, "9.00", "excellent", "Solid entry overall."),
            (self.group.id, "BTF-TEST-1", "", 2, "3.50", "adequate", ""),
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

    def test_missing_criteria_rows_leave_grades_alone(self):
        # A sheet carrying only the criterion 1 row must not clear criterion 2's grade.
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c2, mark=Decimal("4.00"), comment="keep")
        upload = self._make_csv([(self.group.id, "BTF-TEST-1", "", 1, "9.00", "fine", "")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        g2 = Grade.objects.get(submission=self.saq_submission, criterion=self.saq_c2)
        self.assertEqual(g2.mark, Decimal("4.00"))
        self.assertEqual(g2.comment, "keep")

    def test_absent_mark_columns_leave_grades_alone(self):
        # A sheet without mark/comment columns never touches grades.
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c1, mark=Decimal("6.00"), comment="keep")
        header = ["group_id", "criteria_no", "answer"]
        upload = self._make_csv([(self.group.id, 1, "just context")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        g1 = Grade.objects.get(submission=self.saq_submission, criterion=self.saq_c1)
        self.assertEqual(g1.mark, Decimal("6.00"))
        self.assertEqual(g1.comment, "keep")

    def test_absent_overall_comment_column_leaves_feedback_alone(self):
        ComponentFeedback.objects.create(group=self.group, component=self.saq, comment="keep me")
        header = ["group_id", "criteria_no", "mark", "comment"]
        upload = self._make_csv([(self.group.id, 1, "9.00", "fine")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(
            ComponentFeedback.objects.get(group=self.group, component=self.saq).comment,
            "keep me",
        )

    def test_blank_group_id_continues_previous_group(self):
        # The export writes group_id/group_name on each group's first row
        # only; blank cells continue the group above.
        upload = self._make_csv([
            (self.group.id, "BTF-TEST-1", "", 1, "9.00", "fine", ""),
            ("", "", "", 2, "3.50", "ok", ""),
        ])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(Grade.objects.count(), 2)
        g2 = Grade.objects.get(submission=self.saq_submission, criterion=self.saq_c2)
        self.assertEqual(g2.mark, Decimal("3.50"))
        self.assertEqual(g2.comment, "ok")

    def test_overall_comment_read_from_first_row_only(self):
        # The export writes the overall comment on each group's first row;
        # the blank cells on later rows must not read as a "clear".
        ComponentFeedback.objects.create(group=self.group, component=self.saq, comment="old note")
        upload = self._make_csv([
            (self.group.id, "BTF-TEST-1", "", 1, "", "", "New note"),
            (self.group.id, "BTF-TEST-1", "", 2, "", "", ""),
        ])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(
            ComponentFeedback.objects.get(group=self.group, component=self.saq).comment,
            "New note",
        )


class BulkUploadWideFormatTests(_GradingFixture):
    """POSTER/REPORT/PROTOTYPE keep the legacy wide shape: one row per
    group, a type column, and rN_mark/rN_comment per criterion."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.url = reverse("grading:component-bulk-upload", kwargs={"code": "POSTER"})

    WIDE_HEADER = ["group_id", "group_name", "type", "r1_mark", "r1_comment", "overall_comment"]

    def _make_csv(self, rows, header=None):
        header_line = ",".join(header or self.WIDE_HEADER) + "\n"
        body = "\n".join(",".join(str(x) for x in r) for r in rows)
        return SimpleUploadedFile(
            "marks.csv", (header_line + body + "\n").encode("utf-8"), content_type="text/csv",
        )

    def test_dry_run_wide_shape_with_type_check(self):
        resp = self.client.post(
            self.url,
            {"file": self._make_csv([(self.group.id, "BTF-TEST-1", "Poster", "7.00", "nice", "")]),
             "dry_run": "true"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        body = resp.json()
        self.assertTrue(body["checks"]["type_ok"])
        self.assertEqual(
            body["summary"],
            {"creates": 1, "updates": 0, "unchanged": 0, "overall_comments": 0, "errors": 0},
        )

    def test_wrong_type_rejected(self):
        resp = self.client.post(
            self.url,
            {"file": self._make_csv([(self.group.id, "BTF-TEST-1", "SAQs", "7.00", "", "")]),
             "dry_run": "true"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertFalse(body["checks"]["type_ok"])
        self.assertEqual(body["checks"]["found_type"], "SAQs")
        self.assertEqual(body["summary"]["errors"], 1)

    def test_commit_persists_wide_marks(self):
        Grade.objects.create(submission=self.poster_submission, criterion=self.poster_c1, mark=Decimal("5"), comment="old")
        resp = self.client.post(
            self.url,
            {"file": self._make_csv([(self.group.id, "BTF-TEST-1", "Poster", "9.00", "great", "")]),
             "dry_run": "false"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        g = Grade.objects.get(submission=self.poster_submission, criterion=self.poster_c1)
        self.assertEqual(g.mark, Decimal("9.00"))
        self.assertEqual(g.comment, "great")
