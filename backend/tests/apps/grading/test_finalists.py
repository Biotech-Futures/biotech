"""Finalist selection: the toggle, the candidates table and the finalist
list. Telling the teams is Management's (tests/apps/management)."""
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import FinalistFlag, Grade
from apps.groups.models.groups import Groups
from apps.submissions.models import Submission

from .fixtures import _GradingFixture


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

    def test_candidates_flag_parts_not_marked_completely(self):
        from apps.grading.models import Rubric, RubricCriterion, SubmissionComponent

        # A two-criterion report rubric makes REPORT a column; the fixture
        # team hands in a report with only one of its criteria marked.
        report = SubmissionComponent.objects.get(code="REPORT")
        rubric = Rubric.objects.create(component=report, year=self.year, active=True)
        method = RubricCriterion.objects.create(
            rubric=rubric, name="Method", max_mark=Decimal("5"), order=1
        )
        results = RubricCriterion.objects.create(
            rubric=rubric, name="Results", max_mark=Decimal("5"), order=2
        )
        Submission.objects.filter(pk=self.submission.pk).update(submitted_report={
            "storage_key": "2026/01/01/fixture/report.pdf", "name": "report.pdf",
            "mime": "application/pdf", "size": 42,
        })
        for criterion, mark in ((self.saq_c1, "8"), (self.saq_c2, "4"), (method, "3")):
            Grade.objects.create(
                submission=self.submission, criterion=criterion,
                mark=Decimal(mark), graded_by=self.staff,
            )
        empty = Groups.objects.create(group_name="BTF-EMPTY")
        self.client.force_authenticate(self.staff)

        def rows():
            body = self.client.get(reverse("grading:finalist-candidates")).json()
            return {row["group_id"]: row for row in body["rows"]}

        team = rows()[self.group.id]
        # SAQ fully marked; poster not started; report one of two.
        self.assertEqual(team["incomplete"], ["POSTER", "REPORT"])
        self.assertEqual(team["marks"]["REPORT"], "3.00")
        self.assertEqual(rows()[empty.id]["incomplete"], [])

        Grade.objects.create(
            submission=self.submission, criterion=results, mark=Decimal("2"), graded_by=self.staff,
        )
        self.assertEqual(rows()[self.group.id]["incomplete"], ["POSTER"])

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

    def test_candidates_carry_the_submitted_title_and_marking_key_categories(self):
        from apps.grading.models import GroupMarkingCategories

        GroupMarkingCategories.objects.create(
            group=self.group,
            product_categories=["Health and Medicine", "Other"],
            product_category_other="Wearables",
            solution_category="Other",
            solution_category_other="App",
        )
        bare = Groups.objects.create(group_name="BTF-BARE")
        self.client.force_authenticate(self.staff)
        rows = {
            row["group_id"]: row
            for row in self.client.get(reverse("grading:finalist-candidates")).json()["rows"]
        }
        team = rows[self.group.id]
        self.assertEqual(team["project_category"], "Health and Medicine, Wearables")
        self.assertEqual(team["solution_category"], "App")
        self.assertEqual(team["project_title"], "")
        # The title the team submitted, not one typed since.
        Submission.objects.filter(group=self.group).update(
            submitted_project_title="Plant Sensors", project_title="A Later Draft"
        )
        rows = {
            row["group_id"]: row
            for row in self.client.get(reverse("grading:finalist-candidates")).json()["rows"]
        }
        self.assertEqual(rows[self.group.id]["project_title"], "Plant Sensors")
        # A group with nothing picked reads blank.
        self.assertEqual(rows[bare.id]["project_category"], "")
        self.assertEqual(rows[bare.id]["solution_category"], "")

    def test_late_label_drops_minutes_past_a_day(self):
        from datetime import timedelta

        from apps.grading.services.content import late_by_label

        # Day-scale lateness drops the minutes; smaller scales keep them.
        self.assertEqual(late_by_label(timedelta(days=5, hours=1, minutes=58)), "5d 1h")
        self.assertEqual(late_by_label(timedelta(hours=22, minutes=54)), "22h 54m")
        self.assertEqual(late_by_label(timedelta(minutes=45)), "45m")

    def test_list_returns_flagged_groups(self):
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        self.client.force_authenticate(self.staff)
        r = self.client.get(reverse("grading:finalist-list"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        rows = r.json()["finalists"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["group_id"], self.group.id)
