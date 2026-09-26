"""Bulk marks upload: the XLSX/CSV round-trip — parse → dry-run diff → commit."""
import io
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import ComponentFeedback, Grade, GroupMarkingCategories

from .fixtures import _GradingFixture


class BulkUploadMarksViewTests(_GradingFixture):
    """SAQ sheets: the export's one-row-per-group shape, parse → dry-run
    diff → commit. The fixture's SAQ rubric has two criteria."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.url = reverse("grading:component-bulk-upload", kwargs={"code": "SAQ"})

    # Export shape: one row per group, answers in qN (never parsed).
    HEADER = [
        "group_id", "group_name", "type", "q1",
        "r1_mark", "r1_comment", "r2_mark", "r2_comment", "overall_comment",
    ]

    def _row(self, r1_mark="", r1_comment="", r2_mark="", r2_comment="", overall="",
             group_id=None, group_name="BTF-TEST-1", row_type="SAQs", answer=""):
        return (
            self.group.id if group_id is None else group_id, group_name, row_type, answer,
            r1_mark, r1_comment, r2_mark, r2_comment, overall,
        )

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
        resp = self.client.post(self.url, {"file": self._make_csv([self._row("8", "ok")])})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_dry_run_csv_returns_diff_no_writes(self):
        resp = self.client.post(
            self.url, {"file": self._make_csv([self._row("8.00", "Great")]), "dry_run": "true"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        # Criterion 2 is blank with no existing grade -> untouched, not a create.
        self.assertEqual(
            resp.json()["summary"],
            {"creates": 1, "updates": 0, "unchanged": 0, "overall_comments": 0, "marking_categories": 0, "errors": 0},
        )
        self.assertEqual(Grade.objects.count(), 0)

    def test_dry_run_xlsx_categorises_create_update_unchanged(self):
        # One existing grade to force an "update", one that matches to force "unchanged".
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c1, mark=Decimal("5"), comment="old")
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c2, mark=Decimal("4.50"), comment="same")

        upload = self._make_xlsx([self._row("7.00", "revised", "4.50", "same")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(
            resp.json()["summary"],
            {"creates": 0, "updates": 1, "unchanged": 1, "overall_comments": 0, "marking_categories": 0, "errors": 0},
        )
        # Updates name their group and the columns whose values differ,
        # so the preview can say what an overwrite touches.
        upd = resp.json()["updates"][0]
        self.assertEqual(upd["group_name"], "BTF-TEST-1")
        self.assertEqual(upd["columns"], ["r1_mark", "r1_comment"])

    def test_answer_columns_are_never_parsed(self):
        # The qN answers are informational: editing them changes nothing.
        upload = self._make_csv([self._row(answer="an edited answer")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(
            resp.json()["summary"],
            {"creates": 0, "updates": 0, "unchanged": 0, "overall_comments": 0, "marking_categories": 0, "errors": 0},
        )

    def test_row_errors_reported(self):
        upload = self._make_csv([
            self._row("abc"),                                  # non-numeric mark
            self._row("5", group_id=999_999, group_name="x"),  # group with no SAQ submission
            self._row("5"),                                    # duplicate row for the group
        ])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        errors = resp.json()["errors"]
        self.assertGreaterEqual(len(errors), 3)
        for e in errors:
            self.assertIn("row", e)
            self.assertIn("message", e)

    def test_over_max_mark_rejected(self):
        upload = self._make_csv([self._row("99")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["summary"]["errors"], 1)

    def test_wrong_type_rejected(self):
        # A Poster sheet uploaded on the SAQ tab is refused, not misfiled.
        upload = self._make_csv([self._row("5", row_type="Poster")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertFalse(body["checks"]["type_ok"])
        self.assertEqual(body["checks"]["expected_type"], "SAQs")
        self.assertEqual(body["summary"]["errors"], 1)

    def test_missing_mark_columns_rejected(self):
        # Every criterion's mark/comment pair is required, so the old
        # one-row-per-criterion sheet is refused up front.
        header = ["group_id", "group_name", "type", "r1_mark"]
        upload = self._make_csv([(self.group.id, "BTF-TEST-1", "SAQs", "5")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resp.json()["checks"]["missing_headers"], ["r1_comment", "r2_mark", "r2_comment"]
        )

    def test_wrong_group_name_rejected(self):
        # A row whose id points at a different group than its name says.
        upload = self._make_csv([self._row("5", group_name="SOME-OTHER-GROUP")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.json()
        self.assertEqual(body["checks"]["bad_group_rows"][0]["row"], 2)
        self.assertIn("name should be", body["checks"]["bad_group_rows"][0]["reason"])
        self.assertIn("group_name", body["errors"][0]["message"])

    def test_unrecognised_columns_are_ignored(self):
        # Missing means missing: an unknown column is not reported as a
        # missing header, it is simply skipped.
        header = self.HEADER + ["commen", "something_else"]
        upload = self._make_csv([self._row() + ("fine", "x")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        body = resp.json()
        self.assertEqual(body["checks"]["missing_headers"], [])
        self.assertEqual(body["summary"]["errors"], 0)

    def test_commit_rejected_when_errors_exist(self):
        upload = self._make_csv([self._row("abc")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Grade.objects.count(), 0)

    def test_commit_persists_and_stamps_grader(self):
        upload = self._make_csv([
            self._row("9.00", "excellent", "3.50", "adequate", "Solid entry overall."),
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
        g2 = Grade.objects.get(submission=self.saq_submission, criterion=self.saq_c2)
        self.assertEqual(g2.mark, Decimal("3.50"))
        self.assertEqual(g2.comment, "adequate")
        feedback = ComponentFeedback.objects.get(group=self.group, component=self.saq)
        self.assertEqual(feedback.comment, "Solid entry overall.")
        self.assertEqual(feedback.updated_by_id, self.staff.id)

    def test_blank_cells_clear_an_existing_grade(self):
        # The sheet is the truth for every cell it carries.
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c2, mark=Decimal("4.00"), comment="old")
        upload = self._make_csv([self._row("9.00", "fine")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        g2 = Grade.objects.get(submission=self.saq_submission, criterion=self.saq_c2)
        self.assertIsNone(g2.mark)
        self.assertEqual(g2.comment, "")

    def test_absent_overall_comment_column_leaves_feedback_alone(self):
        ComponentFeedback.objects.create(group=self.group, component=self.saq, comment="keep me")
        header = self.HEADER[:-1]
        upload = self._make_csv([self._row("9.00", "fine")[:-1]], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(
            ComponentFeedback.objects.get(group=self.group, component=self.saq).comment,
            "keep me",
        )

    def test_marking_categories_uploaded(self):
        # product_category / category_of_solution parse back from the
        # export's own formatting and land on the group's marking key.
        upload = self._make_xlsx(
            [self._row() + ("Health and Medicine, Wearables", "App")],
            header=self.HEADER + ["product_category", "category_of_solution"],
        )
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        cats = GroupMarkingCategories.objects.get(group=self.group)
        self.assertEqual(cats.product_categories, ["Health and Medicine", "Other"])
        self.assertEqual(cats.product_category_other, "Wearables")
        self.assertEqual(cats.solution_category, "Other")
        self.assertEqual(cats.solution_category_other, "App")
        self.assertEqual(cats.updated_by_id, self.staff.id)

    def test_unknown_category_values_land_in_other(self):
        # Values that match no fixed option are stored as Other detail so
        # nothing the sheet carries can become invisible in the UI. Known
        # labels match case-insensitively to their canonical casing.
        upload = self._make_xlsx(
            [self._row() + ("sustainable environment, sadfasd", "asdfasdf")],
            header=self.HEADER + ["product_category", "category_of_solution"],
        )
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        cats = GroupMarkingCategories.objects.get(group=self.group)
        self.assertEqual(cats.product_categories, ["Sustainable Environment", "Other"])
        self.assertEqual(cats.product_category_other, "sadfasd")
        self.assertEqual(cats.solution_category, "Other")
        self.assertEqual(cats.solution_category_other, "asdfasdf")

    def test_bare_other_ticks_other_and_the_other_prefix_is_plain_text(self):
        # "Other" alone ticks Other with no text; "Other: X" has no special
        # meaning any more, so it is kept whole as the Other text.
        upload = self._make_xlsx(
            [self._row() + ("Other", "Other: App")],
            header=self.HEADER + ["product_category", "category_of_solution"],
        )
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        cats = GroupMarkingCategories.objects.get(group=self.group)
        self.assertEqual(cats.product_categories, ["Other"])
        self.assertEqual(cats.product_category_other, "")
        self.assertEqual(cats.solution_category, "Other")
        self.assertEqual(cats.solution_category_other, "Other: App")

    def test_reordered_product_categories_are_no_change(self):
        GroupMarkingCategories.objects.create(
            group=self.group,
            product_categories=["Health and Medicine", "Sustainable Environment"],
            solution_category="Treatment",
        )
        upload = self._make_xlsx(
            [self._row() + ("Sustainable Environment, Health and Medicine", "Treatment")],
            header=self.HEADER + ["product_category", "category_of_solution"],
        )
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(resp.json()["marking_categories"], [])

    def test_category_change_names_the_columns_it_overwrites(self):
        # Product had a stored value (overwritten); solution was blank (new).
        GroupMarkingCategories.objects.create(
            group=self.group, product_categories=["Emerging Technologies"],
        )
        upload = self._make_xlsx(
            [self._row() + ("Health and Medicine", "Treatment")],
            header=self.HEADER + ["product_category", "category_of_solution"],
        )
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        [entry] = resp.json()["marking_categories"]
        self.assertEqual(entry["group_name"], "BTF-TEST-1")
        self.assertEqual(entry["columns"], ["product_category", "category_of_solution"])
        self.assertEqual(entry["overwritten_columns"], ["product_category"])

    def test_first_categories_overwrite_nothing(self):
        upload = self._make_xlsx(
            [self._row() + ("Health and Medicine", "Treatment")],
            header=self.HEADER + ["product_category", "category_of_solution"],
        )
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        [entry] = resp.json()["marking_categories"]
        self.assertEqual(entry["overwritten_columns"], [])

    def test_absent_category_column_keeps_its_stored_half(self):
        GroupMarkingCategories.objects.create(
            group=self.group, product_categories=["Emerging Technologies"],
            solution_category="Treatment",
        )
        upload = self._make_xlsx(
            [self._row() + ("Health and Medicine",)],
            header=self.HEADER + ["product_category"],
        )
        resp = self.client.post(self.url, {"file": upload, "dry_run": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        cats = GroupMarkingCategories.objects.get(group=self.group)
        self.assertEqual(cats.product_categories, ["Health and Medicine"])
        self.assertEqual(cats.solution_category, "Treatment")

    def test_preview_names_the_group_of_a_cleared_overall_comment(self):
        # A blank cell clears the stored comment; the preview must say which
        # group loses it, so the dialog can list it as an overwrite.
        ComponentFeedback.objects.create(group=self.group, component=self.saq, comment="old note")
        upload = self._make_csv([self._row()])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        [entry] = resp.json()["overall_comments"]
        self.assertEqual(entry["group_name"], "BTF-TEST-1")
        self.assertEqual(entry["old_comment"], "old note")
        self.assertEqual(entry["comment"], "")


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
            {"creates": 1, "updates": 0, "unchanged": 0, "overall_comments": 0, "marking_categories": 0, "errors": 0},
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

    def test_missing_rn_columns_rejected(self):
        # Every rubric position's mark/comment pair is required — a sheet
        # without them (e.g. an SAQ export on this tab) is refused up front.
        header = ["group_id", "group_name", "type", "overall_comment"]
        upload = self._make_csv([(self.group.id, "BTF-TEST-1", "Poster", "")], header=header)
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["checks"]["missing_headers"], ["r1_mark", "r1_comment"])

    def test_preview_names_the_group_of_a_replaced_overall_comment(self):
        ComponentFeedback.objects.create(group=self.group, component=self.poster, comment="old note")
        upload = self._make_csv([(self.group.id, "BTF-TEST-1", "Poster", "", "", "new note")])
        resp = self.client.post(self.url, {"file": upload, "dry_run": "true"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        [entry] = resp.json()["overall_comments"]
        self.assertEqual(entry["group_name"], "BTF-TEST-1")
        self.assertEqual(entry["old_comment"], "old note")
        self.assertEqual(entry["comment"], "new note")

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
