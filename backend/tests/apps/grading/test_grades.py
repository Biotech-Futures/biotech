"""Writing marks: the bulk upsert endpoint and single-grade PATCH."""
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import ComponentFeedback, Grade, Rubric, RubricCriterion, SubmissionComponent

from .fixtures import _GradingFixture


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

    def test_untouched_criteria_create_no_grades(self):
        # The form sends the whole rubric; blank criteria must not become
        # Grade rows attributed to the saver.
        url = reverse("grading:grade-bulk")
        payload = {"items": [
            {"submission": self.saq_submission.id, "criterion": self.saq_c1.id, "mark": "8.00", "comment": ""},
            {"submission": self.saq_submission.id, "criterion": self.saq_c2.id, "mark": None, "comment": ""},
        ]}
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(Grade.objects.count(), 1)
        self.assertFalse(
            Grade.objects.filter(submission=self.saq_submission, criterion=self.saq_c2).exists()
        )

    def test_unchanged_values_keep_the_original_marker(self):
        # Re-saving the same value is a no-op, not a new attribution.
        other = type(self.staff).objects.create_user(
            email="first.marker@example.com", first_name="First", last_name="Marker",
            password="pw12345!", is_staff=True,
        )
        Grade.objects.create(
            submission=self.saq_submission, criterion=self.saq_c1,
            mark=Decimal("8.00"), comment="Great.", graded_by=other,
        )
        url = reverse("grading:grade-bulk")
        payload = {"items": [
            {"submission": self.saq_submission.id, "criterion": self.saq_c1.id, "mark": "8.00", "comment": "Great."},
        ]}
        resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        g = Grade.objects.get(submission=self.saq_submission, criterion=self.saq_c1)
        self.assertEqual(g.graded_by_id, other.id)

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

    def _other_marker_saves(self, criterion, mark, comment=""):
        from apps.users.models import User

        other = User.objects.create_user(email="other.marker@example.com", password="pw12345!", is_staff=True)
        Grade.objects.update_or_create(
            submission=self.saq_submission, criterion=criterion,
            defaults={"mark": Decimal(mark) if mark else None, "comment": comment, "graded_by": other},
        )
        return other

    def test_a_save_started_from_what_is_stored_goes_ahead(self):
        Grade.objects.create(submission=self.saq_submission, criterion=self.saq_c1, mark=Decimal("7.00"), graded_by=self.staff)
        resp = self.client.post(reverse("grading:grade-bulk"), {"items": [
            {"submission": self.saq_submission.id, "criterion": self.saq_c1.id, "mark": "8.00", "comment": "Better.",
             "expected_mark": "7", "expected_comment": ""},
            # Nothing stored yet, and the marker started from nothing.
            {"submission": self.saq_submission.id, "criterion": self.saq_c2.id, "mark": "3.00", "comment": "",
             "expected_mark": None, "expected_comment": ""},
        ]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(Grade.objects.get(criterion=self.saq_c1).mark, Decimal("8.00"))
        self.assertEqual(Grade.objects.get(criterion=self.saq_c2).mark, Decimal("3.00"))

    def test_a_save_over_another_markers_change_is_refused_and_writes_nothing(self):
        # Opened with Content empty; another marker has since given it 8.
        other = self._other_marker_saves(self.saq_c1, "8.00")
        resp = self.client.post(reverse("grading:grade-bulk"), {"items": [
            {"submission": self.saq_submission.id, "criterion": self.saq_c1.id, "mark": "5.00", "comment": "",
             "expected_mark": None, "expected_comment": ""},
            {"submission": self.saq_submission.id, "criterion": self.saq_c2.id, "mark": "3.00", "comment": "",
             "expected_mark": None, "expected_comment": ""},
        ]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            resp.json()["detail"],
            "Another marker changed Content since you opened this group. Reload to see their marks.",
        )
        self.assertEqual(resp.json()["changed"], ["Content"])
        grade = Grade.objects.get(criterion=self.saq_c1)
        self.assertEqual((grade.mark, grade.graded_by), (Decimal("8.00"), other))
        # All or nothing: the other row wasn't written either.
        self.assertFalse(Grade.objects.filter(criterion=self.saq_c2).exists())

    def test_a_changed_comment_and_overall_comment_are_caught_too(self):
        self._other_marker_saves(self.poster_c1, "", comment="Their comment.")
        ComponentFeedback.objects.create(group=self.group, component=self.poster, comment="Their overall.")
        resp = self.client.post(reverse("grading:grade-bulk"), {
            "items": [
                {"submission": self.poster_submission.id, "criterion": self.poster_c1.id, "mark": "6.00",
                 "comment": "", "expected_mark": None, "expected_comment": ""},
            ],
            "overall_comments": [
                {"submission": self.poster_submission.id, "component": "POSTER", "comment": "Mine.",
                 "expected_comment": ""},
            ],
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            resp.json()["detail"],
            "Another marker changed Design and the overall comment since you opened this group. "
            "Reload to see their marks.",
        )
        self.assertEqual(ComponentFeedback.objects.get(component=self.poster).comment, "Their overall.")

    def test_a_save_without_starting_values_is_not_checked(self):
        # The bulk upload and older clients send marks without them.
        self._other_marker_saves(self.saq_c1, "8.00")
        resp = self.client.post(reverse("grading:grade-bulk"), {"items": [
            {"submission": self.saq_submission.id, "criterion": self.saq_c1.id, "mark": "5.00", "comment": ""},
        ]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(Grade.objects.get(criterion=self.saq_c1).mark, Decimal("5.00"))

    def test_component_mismatch_rejected_atomically(self):
        url = reverse("grading:grade-bulk")
        # A REPORT criterion exists but the entry has no submitted report, so
        # binding it to this submission is a client bug and must be rejected.
        report = SubmissionComponent.objects.get(code="REPORT")
        report_rubric = Rubric.objects.create(component=report, year=self.year, active=True)
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
