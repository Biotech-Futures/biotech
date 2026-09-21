"""Marker-facing read views: URL mounts, the group marking page, the
per-component table, its analytics panel, and group categories."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import Grade
from apps.groups.models.groups import Groups
from apps.users.models import AdminScope, User

from .fixtures import _GradingFixture


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


class GroupCategoriesViewTests(_GradingFixture):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_defaults_empty(self):
        r = self.client.get(reverse("grading:group-categories", kwargs={"group_id": self.group.id}))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(r.json(), {
            "product_categories": [],
            "product_category_other": "",
            "solution_category": "",
            "solution_category_other": "",
        })

    def test_save_and_round_trip(self):
        url = reverse("grading:group-categories", kwargs={"group_id": self.group.id})
        body = {
            "product_categories": ["Health and Medicine", "Other"],
            "product_category_other": "Bioinformatics",
            "solution_category": "Product/Device",
            "solution_category_other": "",
        }
        r = self.client.post(url, body, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertEqual(self.client.get(url).json(), body)

    def test_rejects_non_list_products(self):
        url = reverse("grading:group-categories", kwargs={"group_id": self.group.id})
        r = self.client.post(url, {"product_categories": "Health"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_grader(self):
        self.client.force_authenticate(self.non_staff)
        r = self.client.get(reverse("grading:group-categories", kwargs={"group_id": self.group.id}))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
