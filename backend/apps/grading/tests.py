from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.groups.models.groups import Groups
from apps.grading.models import Grade, Rubric, RubricCriterion
from apps.submissions.models import Submission, SubmissionComponent
from apps.users.models import User


@override_settings(GRADING_ENABLED=True)
class GradingURLsMountedTests(TestCase):
    """Sanity: the grading URLs must resolve when the feature flag is on."""

    def test_urls_resolve(self):
        self.assertEqual(reverse("grading:group-marking", kwargs={"group_id": 1}), "/api/v1/grading/groups/1/")
        self.assertEqual(reverse("grading:grade-bulk"), "/api/v1/grading/grades/bulk/")
        self.assertEqual(reverse("grading:grade-detail", kwargs={"pk": 1}), "/api/v1/grading/grades/1/")
        self.assertEqual(reverse("grading:component-list", kwargs={"code": "SAQ"}), "/api/v1/grading/components/SAQ/")


class _GradingFixture(TestCase):
    """Shared setup: one group, four seeded components, four active rubrics, one staff user."""

    @classmethod
    def setUpTestData(cls):
        cls.group = Groups.objects.create(group_name="BTF-TEST-1")
        cls.saq = SubmissionComponent.objects.get(code="SAQ")
        cls.poster = SubmissionComponent.objects.get(code="POSTER")

        cls.saq_rubric = Rubric.objects.create(component=cls.saq, year=2026, active=True)
        cls.poster_rubric = Rubric.objects.create(component=cls.poster, year=2026, active=True)

        cls.saq_c1 = RubricCriterion.objects.create(rubric=cls.saq_rubric, name="Content", max_mark=Decimal("10.00"), order=10)
        cls.saq_c2 = RubricCriterion.objects.create(rubric=cls.saq_rubric, name="Clarity", max_mark=Decimal("5.00"), order=20)
        cls.poster_c1 = RubricCriterion.objects.create(rubric=cls.poster_rubric, name="Design", max_mark=Decimal("10.00"), order=10)

        cls.saq_submission = Submission.objects.create(
            group=cls.group, component=cls.saq, text="Some student answers.",
        )
        cls.poster_submission = Submission.objects.create(
            group=cls.group, component=cls.poster,
        )

        cls.staff = User.objects.create_user(
            email="grader@example.com", first_name="Ada", last_name="Grader",
            password="pw12345!", is_staff=True,
        )
        cls.non_staff = User.objects.create_user(
            email="student@example.com", first_name="Stu", last_name="Dent",
            password="pw12345!", is_staff=False,
        )


@override_settings(GRADING_ENABLED=True)
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
        self.assertEqual(saq_block["submission"]["text"], "Some student answers.")
        self.assertEqual(len(saq_block["criteria"]), 2)
        self.assertEqual(saq_block["grades"], [])
        # REPORT has no submission and no rubric — should still render as an empty slot.
        report_block = next(c for c in data["components"] if c["component"]["code"] == "REPORT")
        self.assertIsNone(report_block["submission"])
        self.assertEqual(report_block["criteria"], [])


@override_settings(GRADING_ENABLED=True)
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

    def test_component_mismatch_rejected_atomically(self):
        url = reverse("grading:grade-bulk")
        # First item is fine; second binds a POSTER criterion to the SAQ submission.
        payload = {"items": [
            {"submission": self.saq_submission.id, "criterion": self.saq_c1.id, "mark": "7.00"},
            {"submission": self.saq_submission.id, "criterion": self.poster_c1.id, "mark": "9.00"},
        ]}
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Atomic — the first item's Grade must NOT have been written.
        self.assertEqual(Grade.objects.count(), 0)


@override_settings(GRADING_ENABLED=True)
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


@override_settings(GRADING_ENABLED=True)
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
