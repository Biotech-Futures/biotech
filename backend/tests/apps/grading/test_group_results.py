"""The Results section on a group's page: what shows once marks or
certificates are released, and who can see it."""
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.grading.models import CertificatesRelease, FinalistFlag, Grade, MarksRelease
from apps.groups.models import GroupMembership, Groups
from apps.users.models import User

from .fixtures import _GradingFixture, _seed_doc_templates


def _member(email, group, role="student"):
    first, last = email.split("@")[0].split(".")
    user = User.objects.create_user(
        email=email, first_name=first.title(), last_name=last.title(), password="pw12345!"
    )
    GroupMembership.objects.create(user=user, group=group, membership_role=role)
    return user


def _release(model, **fields):
    row = model.load()
    row.released_at = timezone.now()
    for name, value in fields.items():
        setattr(row, name, value)
    row.save()


class GroupResultsTests(_GradingFixture):
    def setUp(self):
        _seed_doc_templates()
        self.amy = _member("amy.chen@example.com", self.group)
        self.zoe = _member("zoe.lee@example.com", self.group)
        self.mo = _member("mo.mentor@example.com", self.group, role="mentor")
        self.sam = _member("sam.lee@example.com", self.group, role="supervisor")
        Grade.objects.create(
            submission=self.submission, criterion=self.saq_c1, mark=Decimal("8.00"),
            comment="Clear claim.", graded_by=self.staff,
        )

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def _results(self, user=None):
        r = self._client(user or self.amy).get(reverse("grading:group-results", args=[self.group.id]))
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        return r.json()

    def _summary(self, user=None):
        return self._client(user or self.amy).get(reverse("grading:group-results-summary", args=[self.group.id]))

    def _certificate(self, holder, user=None):
        return self._client(user or self.amy).get(
            reverse("grading:group-results-certificate", args=[self.group.id, holder.id])
        )

    def test_nothing_shows_before_anything_is_released(self):
        body = self._results()
        self.assertEqual(
            (body["marks_released"], body["certificates_released"], body["components"], body["certificates"]),
            (False, False, [], []),
        )
        self.assertEqual(self._summary().status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self._certificate(self.amy).status_code, status.HTTP_403_FORBIDDEN)

    def test_released_marks_show_with_the_marks_summary(self):
        from apps.grading.models import Rubric, RubricCriterion, SubmissionComponent

        # A marked report still stays out, as on the marks summary.
        report = SubmissionComponent.objects.get(code="REPORT")
        RubricCriterion.objects.create(
            rubric=Rubric.objects.create(component=report, year=self.group.year, active=True),
            name="Structure", max_mark=Decimal("5.00"), order=1,
        )
        _release(MarksRelease)
        body = self._results()
        self.assertTrue(body["marks_released"])
        self.assertEqual([c["code"] for c in body["components"]], ["SAQ", "POSTER"])
        saq = next(c for c in body["components"] if c["code"] == "SAQ")
        self.assertEqual((saq["criteria"][0]["mark"], saq["criteria"][0]["comment"]), ("8", "Clear claim."))
        year = self.group.year
        self.assertEqual(body["summary_file_name"], f"{year}_BTF_Marks_BTF-TEST-1.docx")
        r = self._summary()
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn(f"{year}_BTF_Marks_BTF-TEST-1.docx", r["Content-Disposition"])
        # Certificates still wait for their own release.
        self.assertEqual(body["certificates"], [])
        self.assertEqual(self._certificate(self.amy).status_code, status.HTTP_403_FORBIDDEN)

    def test_released_certificates_list_every_student_then_mentor(self):
        _release(CertificatesRelease)
        body = self._results()
        year = self.group.year
        self.assertEqual(
            [(c["name"], c["kind"], c["file_name"]) for c in body["certificates"]],
            [
                ("Amy Chen", "student", f"{year}_BTF_Student_Certificate_Amy_Chen.docx"),
                ("Zoe Lee", "student", f"{year}_BTF_Student_Certificate_Zoe_Lee.docx"),
                ("Mo Mentor", "mentor", f"{year}_BTF_Mentor_Certificate_Mo_Mentor.docx"),
            ],
        )
        # Anyone in the group can download any of them, as the email carries them all.
        r = self._certificate(self.mo, user=self.zoe)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn(f"{year}_BTF_Mentor_Certificate_Mo_Mentor.docx", r["Content-Disposition"])
        # The supervisor has no certificate here.
        self.assertEqual(self._certificate(self.sam).status_code, status.HTTP_404_NOT_FOUND)
        # Marks still wait for theirs.
        self.assertEqual((body["marks_released"], body["components"]), (False, []))

    def test_the_marks_come_with_the_summarys_details_and_combined_mark(self):
        from apps.grading.models import ComponentFeedback, GroupMarkingCategories
        from apps.submissions.models import Submission

        Submission.objects.filter(group=self.group).update(submitted_project_title="Plant Sensors")
        GroupMarkingCategories.objects.create(
            group=self.group, product_categories=["Health and Medicine", "Agriculture"], solution_category="App",
        )
        ComponentFeedback.objects.create(group=self.group, component=self.poster, comment="Strong poster overall.")
        Grade.objects.create(
            submission=self.submission, criterion=self.poster_c1, mark=Decimal("6.50"), graded_by=self.staff,
        )
        _release(MarksRelease)
        body = self._results()
        # As the marks summary words them; the heading plural for two categories.
        self.assertEqual(body["summary"], {
            "project_title": "Plant Sensors",
            "project_category_heading": "Project Categories",
            "project_category": "Health and Medicine, Agriculture",
            "solution_category": "App",
            # 8 (SAQ) + 6.5 (Poster), out of every SAQ and Poster criterion's most.
            "combined_total": "14.5",
            "combined_max": "25",
        })
        poster = next(c for c in body["components"] if c["code"] == "POSTER")
        self.assertEqual(poster["overall_comment"], "Strong poster overall.")
        # Each table's Subtotal row: its marks, out of its criteria's most.
        subtotals = {c["code"]: (c["subtotal"], c["subtotal_max"]) for c in body["components"]}
        self.assertEqual(subtotals, {"SAQ": ("8", "15"), "POSTER": ("6.5", "10")})

    def test_no_summary_before_marks_are_released(self):
        _release(CertificatesRelease)
        self.assertIsNone(self._results()["summary"])

    def test_a_finalists_certificates_are_held_back_while_certificates_exclude_them(self):
        FinalistFlag.objects.create(group=self.group, flagged_by=self.staff)
        _release(CertificatesRelease, exclude_finalists=True)
        body = self._results()
        self.assertEqual((body["certificates_withheld"], body["certificates"]), (True, []))
        self.assertEqual(self._certificate(self.amy).status_code, status.HTTP_403_FORBIDDEN)

    def test_a_group_that_did_not_submit_has_no_results(self):
        empty = Groups.objects.create(group_name="BTF-EMPTY")
        student = _member("nia.ng@example.com", empty)
        _release(MarksRelease)
        _release(CertificatesRelease)
        r = self._client(student).get(reverse("grading:group-results", args=[empty.id]))
        body = r.json()
        self.assertEqual((body["has_submission"], body["components"], body["certificates"]), (False, [], []))

    def test_members_and_admins_only(self):
        _release(MarksRelease)
        for user in (self.amy, self.mo, self.sam, self.staff):
            with self.subTest(user=user.email):
                self.assertEqual(self._results(user)["marks_released"], True)
        outsider = User.objects.create_user(email="out.sider@example.com", password="pw12345!")
        r = self._client(outsider).get(reverse("grading:group-results", args=[self.group.id]))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self._summary(outsider).status_code, status.HTTP_403_FORBIDDEN)
